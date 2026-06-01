#!/bin/bash
# ============================================================================
# CTF SFT Training (warm-start for RL)
#
# Pipeline:
#     sft_data_gen/results/<run>/trajectories.jsonl                 (collect)
#         → sft_data_gen/sft_dataset/<run>.parquet                  (build)
#             → outputs/sft_ckpts/<run>/policy/huggingface/         (this script)
#                 → run_ctf_rl_training.sh  MODEL_PATH=<above dir>  (RL warm-start)
#
# This script:
#   1. Validates inputs (trajectories file or pre-built sft parquet, base model)
#   2. (Optional) Builds the sft parquet from trajectories.jsonl
#   3. rsyncs worker_orchestrator/ez_sft/ → SkyRL/skyrl-train/vulrl_inside_skyrl_v2_sft/
#   4. Launches  uv run -m vulrl_inside_skyrl_v2_sft.main_sft  with SkyRL deps
#   5. Reports the final HF export path (point MODEL_PATH at it for RL)
#
# Required env / args (override on the command line as VAR=value):
#   TRAJECTORIES   path to trajectories.jsonl  (or directory containing one)
#                  — required unless SFT_DATASET already exists.
#   SFT_DATASET    path to SFT parquet (built from TRAJECTORIES if absent).
#   BASE_MODEL     path to base HF model dir (defaults to repo-local qwen2.5-1.5b)
#
# Optional knobs (sane defaults provided):
#   REWARD_THRESHOLD=0.0   filter for build_sft_dataset.py
#   MIN_STEPS=1            filter for build_sft_dataset.py
#   EPOCHS=1
#   BATCH_SIZE=4
#   MAX_LENGTH=4096
#   LEARNING_RATE=2e-5
#   NUM_GPUS=1
#   LOG_EVERY=5
#   MAX_SAMPLES=-1         cap dataset (smoke testing)
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SKYRL_PATH="$REPO_ROOT/SkyRL/skyrl-train"
EZ_SRC="$REPO_ROOT/worker_orchestrator/ez_sft"
SYNC_TARGET="$SKYRL_PATH/vulrl_inside_skyrl_v2_sft"

LOG_DIR="$REPO_ROOT/logs/server"
OUTPUT_ROOT="$REPO_ROOT/outputs"
SFT_DATA_DIR="$REPO_ROOT/sft_data_gen/sft_dataset"

mkdir -p "$LOG_DIR" "$OUTPUT_ROOT/sft_ckpts" "$SFT_DATA_DIR"

# ---- run identity ----
RUN_NAME="${RUN_NAME:-ctf_sft_$(date +%Y%m%d_%H%M%S)}"
TRAIN_LOG="$LOG_DIR/sft_${RUN_NAME}.log"
LATEST_TRAIN_LOG="$LOG_DIR/sft_latest.log"

# ---- I/O ----
TRAJECTORIES="${TRAJECTORIES:-}"
SFT_DATASET="${SFT_DATASET:-$SFT_DATA_DIR/${RUN_NAME}.parquet}"
SFT_OUTPUT_HF="${SFT_OUTPUT_HF:-$OUTPUT_ROOT/sft_ckpts/$RUN_NAME/huggingface}"
HYDRA_OUTPUT_DIR="${HYDRA_OUTPUT_DIR:-$OUTPUT_ROOT/sft_ckpts/$RUN_NAME/hydra}"

# ---- model ----
MODEL_PATH="${MODEL_PATH:-${BASE_MODEL:-$REPO_ROOT/worker_orchestrator/qwen2.5-1.5b}}"
MODEL_NAME="${MODEL_NAME:-Qwen/Qwen2.5-1.5B}"

# ---- training knobs ----
REWARD_THRESHOLD="${REWARD_THRESHOLD:-0.0}"
MIN_STEPS="${MIN_STEPS:-1}"
EPOCHS="${EPOCHS:-1}"
BATCH_SIZE="${BATCH_SIZE:-4}"
MAX_LENGTH="${MAX_LENGTH:-4096}"
LEARNING_RATE="${LEARNING_RATE:-2e-5}"
NUM_GPUS="${NUM_GPUS:-1}"
LOG_EVERY="${LOG_EVERY:-5}"
MAX_SAMPLES="${MAX_SAMPLES:--1}"

# ---- choose python ----
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "[run_ctf_sft_training] ERROR: python3/python not on PATH."
  exit 1
fi

ln -sfn "$TRAIN_LOG" "$LATEST_TRAIN_LOG"
exec > >(tee -a "$TRAIN_LOG") 2>&1

# ---- structural checks ----
if [ ! -d "$SKYRL_PATH" ]; then
  echo "[run_ctf_sft_training] SkyRL path not found: $SKYRL_PATH"
  exit 1
fi
if [ ! -d "$EZ_SRC" ]; then
  echo "[run_ctf_sft_training] ez_sft path not found: $EZ_SRC"
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "[run_ctf_sft_training] ERROR: uv not on PATH."
  exit 1
fi

# ---- resolve model path ----
if [ -e "$MODEL_PATH" ]; then
  MODEL_TO_USE="$MODEL_PATH"
else
  MODEL_TO_USE="$MODEL_NAME"
fi

# ---- step 1: build SFT parquet if needed ----
if [ ! -f "$SFT_DATASET" ]; then
  if [ -z "$TRAJECTORIES" ]; then
    echo "[run_ctf_sft_training] ERROR: no SFT_DATASET ($SFT_DATASET) and no TRAJECTORIES provided."
    echo "Either:"
    echo "  TRAJECTORIES=/path/to/trajectories.jsonl  bash $0"
    echo "  SFT_DATASET=/path/to/existing.parquet      bash $0"
    exit 1
  fi
  if [ ! -e "$TRAJECTORIES" ]; then
    echo "[run_ctf_sft_training] ERROR: TRAJECTORIES path does not exist: $TRAJECTORIES"
    exit 1
  fi
  echo "[run_ctf_sft_training] building SFT parquet from $TRAJECTORIES ..."
  "$PYTHON_BIN" "$REPO_ROOT/sft_data_gen/build_sft_dataset.py" \
    --input "$TRAJECTORIES" \
    --output "$SFT_DATASET" \
    --reward-threshold "$REWARD_THRESHOLD" \
    --min-steps "$MIN_STEPS"
fi

# ---- step 2: sync ez_sft → SkyRL ----
echo "[run_ctf_sft_training] syncing $EZ_SRC → $SYNC_TARGET"
rm -rf "$SYNC_TARGET"
mkdir -p "$SYNC_TARGET"
cp -R "$EZ_SRC"/. "$SYNC_TARGET"/
test -f "$SYNC_TARGET/main_sft.py" || { echo "ERR: sync missing main_sft.py"; exit 1; }
test -f "$SYNC_TARGET/data_module.py" || { echo "ERR: sync missing data_module.py"; exit 1; }
test -f "$SYNC_TARGET/__init__.py" || { echo "ERR: sync missing __init__.py"; exit 1; }

# ---- step 3: env ----
export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$SKYRL_PATH:${PYTHONPATH:-}"
export RAY_EXPERIMENTAL_NOSET_CUDA_VISIBLE_DEVICES=1
export WANDB_MODE=disabled

mkdir -p "$SFT_OUTPUT_HF" "$HYDRA_OUTPUT_DIR"

# ---- step 4: banner ----
echo "============================================================"
echo "CTF SFT Training (SkyRL backed)"
echo "============================================================"
echo "Run name        : $RUN_NAME"
echo "Base model      : $MODEL_TO_USE"
echo "SFT parquet     : $SFT_DATASET"
echo "HF export       : $SFT_OUTPUT_HF"
echo "Hydra dir       : $HYDRA_OUTPUT_DIR"
echo "GPUs            : $NUM_GPUS"
echo "Epochs          : $EPOCHS"
echo "Batch size      : $BATCH_SIZE"
echo "Max length      : $MAX_LENGTH"
echo "Learning rate   : $LEARNING_RATE"
echo "Reward filter   : $REWARD_THRESHOLD"
echo "Train log       : $TRAIN_LOG"
echo "============================================================"

# ---- step 5: launch ----
cd "$SKYRL_PATH"

uv run --extra vllm \
  --with pandas \
  --with pyyaml \
  -m vulrl_inside_skyrl_v2_sft.main_sft \
    --sft-dataset       "$SFT_DATASET" \
    --sft-output-hf     "$SFT_OUTPUT_HF" \
    --sft-batch-size    "$BATCH_SIZE" \
    --sft-epochs        "$EPOCHS" \
    --sft-max-length    "$MAX_LENGTH" \
    --sft-learning-rate "$LEARNING_RATE" \
    --sft-log-every     "$LOG_EVERY" \
    --sft-max-samples   "$MAX_SAMPLES" \
    trainer.policy.model.path="$MODEL_TO_USE" \
    trainer.placement.policy_num_gpus_per_node="$NUM_GPUS" \
    trainer.placement.policy_num_nodes=1 \
    trainer.policy.sequence_parallel_size=1 \
    trainer.strategy=fsdp2 \
    trainer.logger=console \
    trainer.run_name="$RUN_NAME" \
    hydra.run.dir="$HYDRA_OUTPUT_DIR" \
    "$@"

echo
echo "============================================================"
echo "SFT complete."
echo "HF model exported to: $SFT_OUTPUT_HF"
echo
echo "To warm-start RL with this checkpoint:"
echo "  MODEL_PATH=\"$SFT_OUTPUT_HF\" bash $REPO_ROOT/scripts/server/run_ctf_rl_training.sh"
echo "============================================================"
