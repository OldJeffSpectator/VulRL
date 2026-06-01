#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -x ".venv/bin/python" ]] && ".venv/bin/python" -c "import huggingface_hub" >/dev/null 2>&1; then
  exec ".venv/bin/python" scripts/download_benchmark.py "$@"
fi

if command -v uv >/dev/null 2>&1; then
  exec uv run --with huggingface_hub python scripts/download_benchmark.py "$@"
fi

exec python3 scripts/download_benchmark.py "$@"
