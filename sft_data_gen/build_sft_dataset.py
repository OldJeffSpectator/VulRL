"""
Convert collected rollout trajectories.jsonl into an SFT training parquet.

Pipeline:
    sft_data_gen/results/<run>/trajectories.jsonl
        ↓ (this script)
    sft_data_gen/sft_dataset/<run>.parquet  (multi-turn messages, per trajectory)

Each trajectory is rebuilt into a chat-formatted conversation that mirrors
what the enigma (CTFMix) agent actually sent to the LLM during rollout:

    [system]    rendered system_template from the agent YAML
    [user]      initial task prompt (request.prompt from the rollout)
    [assistant] raw LLM response of step 0  (← SFT supervision target)
    [user]      observation 0 wrapped in next_step_template
    [assistant] raw LLM response of step 1
    [user]      observation 1 wrapped in next_step_template
    ...

Agent config selection mirrors rollout_executor.py:
    reward_type ∈ {"vulhub_rce", "vulhub_read"}  →  default_empty.yaml
    everything else                              →  default_ctf.yaml

Filtering:
    --reward-threshold T  drops trajectories with reward < T (default 0.0 = keep all)

Snapshotting:
    The agent YAML(s) actually used are copied next to the output parquet
    as <agent>.yaml.snapshot. This protects against YAML drift between
    rollout collection time and SFT training time, and again between SFT
    and downstream RL training time.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_CONFIG_DIR = REPO_ROOT / "worker_orchestrator" / "worker_unit" / "agent" / "config"

DEFAULT_AGENT_CONFIGS = {
    "default_empty": AGENT_CONFIG_DIR / "default_empty.yaml",
    "default_ctf":   AGENT_CONFIG_DIR / "default_ctf.yaml",
}

# Reward-type → agent YAML name, mirrors rollout_executor.py:332.
REWARD_TYPE_TO_CONFIG = {
    "vulhub_rce":  "default_empty",
    "vulhub_read": "default_empty",
}
DEFAULT_CONFIG_NAME = "default_ctf"


# ---------------------------------------------------------------------------
# Agent YAML loading and template rendering
# ---------------------------------------------------------------------------

def load_agent_config(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    # The CTFMix YAMLs are usually wrapped under an "agent:" key.
    return cfg.get("agent", cfg)


def safe_format(template: str, mapping: Dict[str, Any]) -> str:
    """`str.format` that tolerates missing keys (renders them as blanks)."""

    class _Defaulting(dict):
        def __missing__(self, key):
            return ""

    try:
        return template.format_map(_Defaulting(mapping))
    except (IndexError, ValueError):
        # Fall back to manual replacement if template contains stray {} that
        # are not valid format placeholders (rare in our YAMLs but defensive).
        out = template
        for k, v in mapping.items():
            out = out.replace("{" + k + "}", str(v))
        return out


def default_template_vars(record: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort guess at the {placeholders} CTFMix would have used."""
    meta = record.get("metadata") or {}
    challenge_info = meta.get("challenge_info") or {}
    return {
        # Used by system_template / instance_template
        "flag_format":       meta.get("flag_format") or challenge_info.get("flag_format") or "flag{...}",
        "command_docs":      "",  # snapshot omitted; model already learned the action format from trajectories
        "name":              meta.get("challenge_name") or record.get("cve_id") or "challenge",
        "category_friendly": (challenge_info.get("category") or "security").replace("_", " "),
        "category":          challenge_info.get("category") or "security",
        "points":            str(challenge_info.get("points") or "n/a"),
        "description":       record.get("prompt") or "",
        "files":             ", ".join(challenge_info.get("files") or []) or "n/a",
        "server_description": meta.get("server_description") or "",
        # Used by *_step_template
        "observation":          "",
        "open_file":            "n/a",
        "working_dir":          ".",
        "interactive_session":  "n/a",
    }


def render_system_message(agent_cfg: Dict[str, Any], record: Dict[str, Any]) -> str:
    tmpl = agent_cfg.get("system_template", "")
    if not tmpl:
        return ""
    return safe_format(tmpl, default_template_vars(record))


def render_user_observation(
    agent_cfg: Dict[str, Any], record: Dict[str, Any], observation: str
) -> str:
    """Render a follow-up user turn the way CTFMix would have rendered it."""
    if observation is None or str(observation).strip() == "":
        tmpl = agent_cfg.get("next_step_no_output_template") or agent_cfg.get("next_step_template", "")
    else:
        tmpl = agent_cfg.get("next_step_template", "")

    if not tmpl:
        # Defensive fallback so SFT never crashes on a degenerate YAML.
        return str(observation) if observation is not None else ""

    vars_ = default_template_vars(record)
    vars_["observation"] = observation if observation is not None else ""
    return safe_format(tmpl, vars_)


# ---------------------------------------------------------------------------
# Trajectory → messages
# ---------------------------------------------------------------------------

def extract_assistant_response(step: Dict[str, Any]) -> str:
    """Get the raw LLM response the model produced at this step.

    Trajectories produced by CTFAgent store the raw LLM output in
    `step.metadata.response`. If missing (e.g. DemoAgent), fall back to
    reconstructing from (thought + action).
    """
    meta = step.get("metadata") or {}
    response = meta.get("response")
    if response:
        return response

    thought = meta.get("thought") or ""
    action = step.get("action") or ""
    if thought and action:
        return f"DISCUSSION\n{thought}\n```\n{action}\n```"
    if action:
        return f"```\n{action}\n```"
    return thought or ""


def initial_user_content(record: Dict[str, Any]) -> str:
    """Reproduce the initial user message the rollout actually sent."""
    prompt = record.get("prompt")
    if prompt is None:
        return ""
    if not isinstance(prompt, str):
        return str(prompt)
    # The CTF parquet builder packs prompt as JSON like
    # [{"role": "user", "content": "..."}]; unpack if so.
    stripped = prompt.strip()
    if stripped.startswith("[") and '"role"' in stripped:
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list) and parsed:
                # Concatenate all non-empty contents in order so we don't lose
                # any of the prompt the rollout actually used.
                parts = [
                    str(m.get("content", "")).strip()
                    for m in parsed
                    if isinstance(m, dict) and m.get("content")
                ]
                if parts:
                    return "\n\n".join(parts)
        except json.JSONDecodeError:
            pass
    return prompt


def build_messages(
    record: Dict[str, Any],
    agent_cfg: Dict[str, Any],
    *,
    include_system: bool = True,
) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = []

    if include_system:
        sys_msg = render_system_message(agent_cfg, record)
        if sys_msg:
            messages.append({"role": "system", "content": sys_msg})

    user_content = initial_user_content(record)
    if user_content:
        messages.append({"role": "user", "content": user_content})

    trajectory = record.get("trajectory") or []
    for i, step in enumerate(trajectory):
        response = extract_assistant_response(step)
        if not response:
            # Skip degenerate steps: nothing useful to learn from a turn where
            # the model produced empty output.
            continue
        messages.append({"role": "assistant", "content": response})

        # Add the user observation for the next turn, unless this is the
        # final step or the trajectory marked itself done at this step.
        is_last = (i == len(trajectory) - 1) or bool(step.get("done"))
        if not is_last:
            obs = step.get("observation") or ""
            user_msg = render_user_observation(agent_cfg, record, obs)
            messages.append({"role": "user", "content": user_msg})

    return messages


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def iter_records(input_path: Path) -> Iterable[Dict[str, Any]]:
    """Yield JSONL records. Accepts a single file or a directory of jsonls."""
    if input_path.is_dir():
        files = sorted(input_path.rglob("trajectories.jsonl"))
        if not files:
            files = sorted(input_path.rglob("*.jsonl"))
    else:
        files = [input_path]

    for fp in files:
        with open(fp, "r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    print(f"[warn] {fp}:{line_no} JSON error: {exc}", file=sys.stderr)


def select_agent_config_name(record: Dict[str, Any]) -> str:
    meta = record.get("metadata") or {}
    reward_type = meta.get("reward_type")
    if reward_type and reward_type in REWARD_TYPE_TO_CONFIG:
        return REWARD_TYPE_TO_CONFIG[reward_type]
    return DEFAULT_CONFIG_NAME


def build(
    input_path: Path,
    output_path: Path,
    reward_threshold: float,
    min_steps: int,
    include_system: bool,
    agent_config_overrides: Dict[str, Path],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve agent configs (overridable via CLI)
    config_paths = dict(DEFAULT_AGENT_CONFIGS)
    config_paths.update(agent_config_overrides)
    agent_configs = {name: load_agent_config(p) for name, p in config_paths.items()}

    rows: List[Dict[str, Any]] = []
    stats = Counter()

    for record in iter_records(input_path):
        stats["total"] += 1
        reward = record.get("reward")
        if reward is None or float(reward) < reward_threshold:
            stats["dropped_low_reward"] += 1
            continue

        trajectory = record.get("trajectory") or []
        if len(trajectory) < min_steps:
            stats["dropped_too_short"] += 1
            continue

        cfg_name = select_agent_config_name(record)
        agent_cfg = agent_configs[cfg_name]

        messages = build_messages(record, agent_cfg, include_system=include_system)
        n_assistant = sum(1 for m in messages if m["role"] == "assistant")
        if n_assistant == 0:
            stats["dropped_no_assistant"] += 1
            continue

        rows.append({
            "messages":             json.dumps(messages, ensure_ascii=False),
            "n_messages":           len(messages),
            "n_assistant_turns":    n_assistant,
            "source_cve_id":        record.get("cve_id"),
            "source_trial_idx":     record.get("trial_idx"),
            "source_reward":        float(reward),
            "source_success":       bool(record.get("success") or False),
            "source_model_name":    record.get("model_name"),
            "source_timestamp":     record.get("timestamp"),
            "agent_config_name":    cfg_name,
        })
        stats["kept"] += 1

    if not rows:
        print(f"[build_sft_dataset] No samples passed filtering. Stats: {dict(stats)}")
        sys.exit(2)

    df = pd.DataFrame(rows)
    df.to_parquet(output_path, index=False)

    # Snapshot the agent YAMLs alongside the parquet (one per config actually used)
    used_configs = set(df["agent_config_name"].unique())
    snap_dir = output_path.parent / f"{output_path.stem}.agent_snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    for name in used_configs:
        shutil.copy(config_paths[name], snap_dir / f"{name}.yaml")

    # Build/append a small manifest with reproducibility info
    manifest = {
        "generated_at":      datetime.now(timezone.utc).isoformat(),
        "input":             str(input_path),
        "output":            str(output_path),
        "reward_threshold":  reward_threshold,
        "min_steps":         min_steps,
        "include_system":    include_system,
        "n_rows":            len(df),
        "stats":             dict(stats),
        "agent_configs":     {k: str(v) for k, v in config_paths.items() if k in used_configs},
        "snapshots_dir":     str(snap_dir),
    }
    with open(output_path.with_suffix(".manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"[build_sft_dataset] Wrote {len(df)} SFT samples → {output_path}")
    print(f"[build_sft_dataset] Stats: {dict(stats)}")
    print(f"[build_sft_dataset] Agent snapshots → {snap_dir}")
    print(f"[build_sft_dataset] Manifest → {output_path.with_suffix('.manifest.json')}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Convert collected SFT rollout trajectories into an SFT training parquet."
    )
    p.add_argument("--input", required=True,
                   help="Path to trajectories.jsonl (or a directory containing one or more).")
    p.add_argument("--output", required=True,
                   help="Path to the output .parquet file.")
    p.add_argument("--reward-threshold", type=float, default=0.0,
                   help="Drop trajectories whose reward is below this threshold (default 0.0 = keep all).")
    p.add_argument("--min-steps", type=int, default=1,
                   help="Drop trajectories with fewer steps than this (default 1).")
    p.add_argument("--no-system", action="store_true",
                   help="Do NOT prepend a rendered system message (default: include).")
    p.add_argument("--default-ctf-yaml", default=None,
                   help="Override path to default_ctf.yaml.")
    p.add_argument("--default-empty-yaml", default=None,
                   help="Override path to default_empty.yaml.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    overrides: Dict[str, Path] = {}
    if args.default_ctf_yaml:
        overrides["default_ctf"] = Path(args.default_ctf_yaml)
    if args.default_empty_yaml:
        overrides["default_empty"] = Path(args.default_empty_yaml)

    build(
        input_path=Path(args.input),
        output_path=Path(args.output),
        reward_threshold=args.reward_threshold,
        min_steps=args.min_steps,
        include_system=not args.no_system,
        agent_config_overrides=overrides,
    )


if __name__ == "__main__":
    main()
