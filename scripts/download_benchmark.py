#!/usr/bin/env python3
"""Download the private VulRL benchmark dataset from Hugging Face."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

try:
    from huggingface_hub import snapshot_download
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: huggingface_hub\n"
        "Run via ./scripts/download_benchmark.sh, or install it with:\n"
        "  pip install huggingface_hub"
    ) from exc


DEFAULT_REPO_ID = "Elfsong/vulrl-benchmark"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "benchmark"


def parse_dotenv_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_hf_token(env_file: Path) -> str | None:
    token = os.environ.get("HF_TOKEN")
    if token:
        return token

    if not env_file.exists():
        return None

    for raw_line in env_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if not line.startswith("HF_TOKEN="):
            continue
        return parse_dotenv_value(line.split("=", 1)[1])

    return None


def ensure_output_dir(path: Path, force: bool) -> None:
    if not path.exists():
        return

    if not path.is_dir():
        raise SystemExit(f"Output path exists and is not a directory: {path}")

    has_files = any(path.iterdir())
    if not has_files:
        return

    if not force:
        raise SystemExit(
            f"Output directory is not empty: {path}\n"
            "Use --force to delete it before downloading again."
        )

    shutil.rmtree(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the VulRL benchmark dataset from Hugging Face."
    )
    parser.add_argument(
        "--repo-id",
        default=DEFAULT_REPO_ID,
        help=f"Hugging Face dataset repo id. Default: {DEFAULT_REPO_ID}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Download destination. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--revision",
        default="main",
        help="Dataset revision, branch, tag, or commit. Default: main",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=REPO_ROOT / ".env",
        help="Path to .env containing HF_TOKEN. Default: repo .env",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete a non-empty output directory before downloading.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    env_file = args.env_file.expanduser().resolve()

    token = load_hf_token(env_file)
    if not token:
        print(
            "HF_TOKEN not found. Set HF_TOKEN in the environment or in .env.",
            file=sys.stderr,
        )
        return 1

    ensure_output_dir(output_dir, force=args.force)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading dataset: {args.repo_id}")
    print(f"Revision: {args.revision}")
    print(f"Destination: {output_dir}")

    snapshot_download(
        repo_id=args.repo_id,
        repo_type="dataset",
        revision=args.revision,
        token=token,
        local_dir=output_dir,
        local_dir_use_symlinks=False,
        resume_download=True,
    )

    print("Download complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
