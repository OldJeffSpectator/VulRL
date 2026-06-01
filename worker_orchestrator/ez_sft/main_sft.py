"""SkyRL-backed SFT trainer for VulRL trajectories.

Trains a policy with cross-entropy loss on (prompt, response) pairs derived
from rollout trajectories, then exports an HF-format checkpoint that
``scripts/server/run_ctf_rl_training.sh`` can load as the RL starting point.

This module mirrors ``SkyRL/skyrl-train/examples/sft/sft_trainer.py`` but
plugs in a custom data loader for our parquet schema and writes HF
checkpoints at the end of training.

Run via :mod:`scripts.server.run_ctf_sft_training` (the launcher rsyncs this
package into ``SkyRL/skyrl-train/vulrl_inside_skyrl_v2_sft/`` so that
``uv run -m vulrl_inside_skyrl_v2_sft.main_sft`` resolves correctly).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import hydra
import ray
import torch
from loguru import logger
from omegaconf import DictConfig, OmegaConf
from ray.util.placement_group import placement_group
from tqdm import tqdm
from transformers import AutoTokenizer

from skyrl_train.entrypoints.main_base import config_dir
from skyrl_train.utils import get_ray_pg_ready_with_timeout
from skyrl_train.utils.utils import initialize_ray, validate_cfg
from skyrl_train.workers.fsdp.fsdp_worker import PolicyWorker
from skyrl_train.workers.worker import PPORayActorGroup
from skyrl_train.workers.worker_dispatch import WorkerDispatch

# Local imports (work both when run as a package and when rsynced to SkyRL)
try:
    from .data_module import iter_batches, load_and_tokenize_parquet
except ImportError:  # pragma: no cover — running as a script during dev
    from data_module import iter_batches, load_and_tokenize_parquet  # type: ignore


# ---------------------------------------------------------------------------
# Hydra config
# ---------------------------------------------------------------------------

def _parse_sft_args(argv):
    """Parse SFT-specific args. Everything else is forwarded to Hydra."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--sft-dataset",   type=str, required=True,
                   help="Path to SFT parquet produced by build_sft_dataset.py")
    p.add_argument("--sft-output-hf", type=str, required=True,
                   help="Directory to export the final HF-format model")
    p.add_argument("--sft-batch-size",       type=int,   default=4)
    p.add_argument("--sft-epochs",           type=int,   default=1)
    p.add_argument("--sft-max-length",       type=int,   default=4096)
    p.add_argument("--sft-learning-rate",    type=float, default=2e-5)
    p.add_argument("--sft-log-every",        type=int,   default=5)
    p.add_argument("--sft-max-samples",      type=int,   default=-1,
                   help="If >0, cap the dataset at this many samples (smoke testing).")
    args, remaining = p.parse_known_args(argv)
    return args, remaining


def _apply_sft_overrides(cfg: DictConfig, sft_args) -> DictConfig:
    """Apply the SFT-specific config overrides we always want."""
    # Force a sensible single-policy layout for SFT.
    cfg.trainer.placement.policy_num_nodes = 1
    cfg.trainer.policy.optimizer_config.lr = float(sft_args.sft_learning_rate)
    # SFT does not use reference / critic / inference engines.
    cfg.generator.run_engines_locally = False
    cfg.generator.num_inference_engines = 0
    # Make checkpointing happen only at the end (we save HF format ourselves).
    cfg.trainer.ckpt_interval = -1
    cfg.trainer.hf_save_interval = -1
    cfg.trainer.resume_mode = "none"
    validate_cfg(cfg)
    return cfg


def get_sft_config(sft_args) -> DictConfig:
    with hydra.initialize_config_dir(config_dir=config_dir, version_base=None):
        cfg = hydra.compose(config_name="ppo_base_config")
    return _apply_sft_overrides(cfg, sft_args)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def run_sft(cfg: DictConfig, sft_args) -> None:
    initialize_ray(cfg)

    model_path = cfg.trainer.policy.model.path
    logger.info(f"[SFT] base model path: {model_path}")

    logger.info("[SFT] loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    logger.info(f"[SFT] loading + tokenizing dataset from {sft_args.sft_dataset}")
    limit = sft_args.sft_max_samples if sft_args.sft_max_samples > 0 else None
    samples = load_and_tokenize_parquet(
        parquet_path=sft_args.sft_dataset,
        tokenizer=tokenizer,
        max_length=sft_args.sft_max_length,
        limit=limit,
    )
    if not samples:
        logger.error("[SFT] no samples after tokenization — aborting.")
        sys.exit(2)
    logger.info(f"[SFT] {len(samples)} samples ready (max_length={sft_args.sft_max_length})")

    # ---------------- Spin up policy actor ----------------
    num_gpus = cfg.trainer.placement.policy_num_gpus_per_node
    logger.info(f"[SFT] initializing policy worker on {num_gpus} GPUs...")
    pg = placement_group([{"GPU": num_gpus, "CPU": num_gpus}], strategy="PACK")
    get_ray_pg_ready_with_timeout(pg, timeout=60)

    actor_group = PPORayActorGroup(
        cfg,
        num_nodes=1,
        num_gpus_per_node=num_gpus,
        ray_actor_type=PolicyWorker,
        pg=pg,
        num_gpus_per_actor=0.75,
        colocate_all=False,
        sequence_parallel_size=cfg.trainer.policy.sequence_parallel_size,
    )
    ray.get(actor_group.async_init_model(model_path))
    dispatch = WorkerDispatch(cfg, policy_actor_group=actor_group)

    # ---------------- Training loop ----------------
    batch_size = sft_args.sft_batch_size
    epochs = sft_args.sft_epochs
    log_every = sft_args.sft_log_every
    total_steps_est = (len(samples) // batch_size) * epochs
    logger.info(f"[SFT] starting training: epochs={epochs}, batch_size={batch_size}, "
                f"~total_steps={total_steps_est}")

    global_step = 0
    t0 = time.time()

    for epoch in range(epochs):
        logger.info(f"[SFT] === Epoch {epoch + 1}/{epochs} ===")
        for batch in tqdm(iter_batches(samples, tokenizer, batch_size, shuffle=True, seed=42 + epoch),
                          total=len(samples) // batch_size,
                          desc=f"epoch {epoch + 1}"):
            global_step += 1
            metrics = dispatch.forward_backward("policy", batch, loss_fn="cross_entropy")
            grad_norm = dispatch.optim_step("policy")

            if global_step % log_every == 0 or global_step == 1:
                loss_val = metrics.get("final_loss", metrics.get("loss", float("nan")))
                if isinstance(loss_val, torch.Tensor):
                    loss_val = loss_val.item()
                elapsed = time.time() - t0
                logger.info(f"[SFT] step={global_step}  loss={loss_val:.4f}  "
                            f"grad_norm={grad_norm}  elapsed={elapsed:.0f}s")

    logger.info(f"[SFT] training complete after {global_step} steps "
                f"in {time.time() - t0:.0f}s")

    # ---------------- Export HF model ----------------
    export_dir = sft_args.sft_output_hf
    Path(export_dir).mkdir(parents=True, exist_ok=True)
    logger.info(f"[SFT] exporting HF model → {export_dir}")
    dispatch.save_hf_model("policy", export_dir, tokenizer)
    # Tokenizer is needed for downstream RL inference.
    tokenizer.save_pretrained(export_dir)
    logger.info("[SFT] export complete. Point trainer.policy.model.path to the export dir "
                "to warm-start RL training.")

    ray.shutdown()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # We bypass Hydra's @main decorator so we can layer custom CLI flags
    # without fighting Hydra's strict parser.
    sft_args, hydra_overrides = _parse_sft_args(sys.argv[1:])

    # Hand the residual args (e.g. `trainer.policy.model.path=...`) to Hydra.
    sys.argv = [sys.argv[0]] + hydra_overrides

    @hydra.main(config_path=config_dir, config_name="ppo_base_config", version_base=None)
    def _hydra_main(cfg: DictConfig) -> None:
        cfg = _apply_sft_overrides(cfg, sft_args)
        run_sft(cfg, sft_args)

    _hydra_main()


if __name__ == "__main__":
    main()
