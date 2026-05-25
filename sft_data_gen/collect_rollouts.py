"""
Standalone rollout collector for SFT data generation.

Reads a parquet dataset, submits rollout requests to the Worker Router,
polls for results, and saves all trajectories to JSONL files.
Supports resume — already-collected (cve_id, trial_idx) pairs are skipped.
"""

import argparse
import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import aiohttp
import pandas as pd


# ---------------------------------------------------------------------------
# Minimal async HTTP client for Worker Router (avoids importing ez_generator)
# ---------------------------------------------------------------------------

class RouterClient:
    """Thin async HTTP client for the Worker Router API."""

    def __init__(self, base_url: str = "http://localhost:12345"):
        self.base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _session_get(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def health(self) -> bool:
        try:
            s = await self._session_get()
            async with s.get(f"{self.base_url}/health") as r:
                return r.status == 200
        except Exception:
            return False

    async def submit(self, request: Dict[str, Any]) -> str:
        s = await self._session_get()
        async with s.post(f"{self.base_url}/api/rollout/execute", json=request) as r:
            r.raise_for_status()
            data = await r.json()
            return data["task_id"]

    async def status(self, task_id: str) -> Dict[str, Any]:
        s = await self._session_get()
        async with s.get(f"{self.base_url}/api/rollout/status/{task_id}") as r:
            r.raise_for_status()
            return await r.json()

    async def wait(
        self, task_id: str, timeout: float = 600, poll_interval: float = 15
    ) -> Dict[str, Any]:
        t0 = time.time()
        max_net_retries = 5
        net_retries = 0
        while True:
            elapsed = time.time() - t0
            if elapsed > timeout:
                raise TimeoutError(f"task {task_id} not done in {timeout}s")
            try:
                result = await self.status(task_id)
                net_retries = 0
                st = result.get("status")
                if st == "completed":
                    return result
                if st == "failed":
                    raise RuntimeError(result.get("error") or "unknown error")
                if st == "timeout":
                    raise TimeoutError("worker-side timeout")
                await asyncio.sleep(poll_interval)
            except (aiohttp.ClientError, OSError) as exc:
                net_retries += 1
                if net_retries > max_net_retries:
                    raise RuntimeError(f"network error after {max_net_retries} retries: {exc}")
                await asyncio.sleep(poll_interval * (2 ** (net_retries - 1)))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_parquet(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    required = {"cve_id", "vulhub_path", "prompt", "max_steps", "metadata"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Parquet missing required columns: {missing}")
    return df


def load_completed(output_dir: Path) -> Set[Tuple[str, int]]:
    """Scan existing JSONL for already-collected (cve_id, trial_idx) pairs."""
    done: Set[Tuple[str, int]] = set()
    traj_file = output_dir / "trajectories.jsonl"
    if not traj_file.exists():
        return done
    with open(traj_file, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                done.add((rec["cve_id"], rec["trial_idx"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def build_request(
    row: pd.Series,
    trial_idx: int,
    llm_endpoint: str,
    model_name: str,
    api_key: Optional[str],
    temperature: float,
    max_tokens: int,
    rollout_timeout: int,
) -> Dict[str, Any]:
    metadata = row["metadata"]
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    metadata = dict(metadata)
    metadata["sft_gen_trial_idx"] = trial_idx

    req: Dict[str, Any] = {
        "cve_id": row["cve_id"],
        "vulhub_path": row["vulhub_path"],
        "prompt": row["prompt"],
        "max_steps": int(row["max_steps"]),
        "timeout": rollout_timeout,
        "llm_endpoint": llm_endpoint,
        "model_name": model_name,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "metadata": metadata,
    }
    if api_key:
        req["api_key"] = api_key
    return req


async def run_one(
    client: RouterClient,
    request: Dict[str, Any],
    cve_id: str,
    trial_idx: int,
    poll_interval: float,
    rollout_timeout: float,
) -> Tuple[str, int, Optional[Dict[str, Any]], Optional[str]]:
    """Submit → poll → return (cve_id, trial_idx, result|None, error|None)."""
    try:
        task_id = await client.submit(request)
    except Exception as exc:
        return cve_id, trial_idx, None, f"submit_failed: {exc}"
    try:
        result = await client.wait(task_id, timeout=rollout_timeout, poll_interval=poll_interval)
        return cve_id, trial_idx, result, None
    except TimeoutError as exc:
        return cve_id, trial_idx, None, f"timeout: {exc}"
    except RuntimeError as exc:
        return cve_id, trial_idx, None, f"runtime_error: {exc}"
    except Exception as exc:
        return cve_id, trial_idx, None, f"unexpected: {exc}"


# ---------------------------------------------------------------------------
# Main collection loop
# ---------------------------------------------------------------------------

async def collect(
    parquet_path: str,
    output_dir: Path,
    llm_endpoint: str,
    model_name: str,
    api_key: Optional[str],
    trials_per_case: int,
    max_concurrent: int,
    router_url: str,
    poll_interval: float,
    rollout_timeout: int,
    temperature: float,
    max_tokens: int,
):
    df = load_parquet(parquet_path)
    total_cases = len(df)
    print(f"Loaded {total_cases} cases from {parquet_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    traj_file = output_dir / "trajectories.jsonl"
    error_file = output_dir / "errors.log"

    done = load_completed(output_dir)
    print(f"Found {len(done)} already-completed rollouts (resume mode)")

    jobs: List[Tuple[int, pd.Series, int]] = []
    for row_idx, row in df.iterrows():
        for trial_idx in range(trials_per_case):
            if (row["cve_id"], trial_idx) not in done:
                jobs.append((row_idx, row, trial_idx))

    total_jobs = len(jobs)
    total_all = total_cases * trials_per_case
    print(f"Total rollouts: {total_all}, remaining: {total_jobs}, skipped: {total_all - total_jobs}")
    if total_jobs == 0:
        print("Nothing to do — all rollouts already collected.")
        return

    client = RouterClient(base_url=router_url)
    if not await client.health():
        print(f"ERROR: Worker Router at {router_url} is not healthy. Aborting.")
        await client.close()
        return
    print(f"Worker Router at {router_url} is healthy.\n")

    sem = asyncio.Semaphore(max_concurrent)
    completed_count = 0
    failed_count = 0
    t0 = time.time()

    traj_fh = open(traj_file, "a", encoding="utf-8")
    err_fh = open(error_file, "a", encoding="utf-8")

    async def _run(row_idx: int, row: pd.Series, trial_idx: int):
        nonlocal completed_count, failed_count
        async with sem:
            req = build_request(
                row, trial_idx, llm_endpoint, model_name,
                api_key, temperature, max_tokens, rollout_timeout,
            )
            cve_id, t_idx, result, error = await run_one(
                client, req, row["cve_id"], trial_idx,
                poll_interval, rollout_timeout,
            )
            elapsed = time.time() - t0

            if error:
                failed_count += 1
                ts = datetime.now().isoformat()
                err_fh.write(f"[{ts}] cve_id={cve_id} trial={t_idx} error={error}\n")
                err_fh.flush()
                n = completed_count + failed_count
                print(f"[{n}/{total_jobs}] FAIL  {cve_id} trial={t_idx}  ({elapsed:.0f}s)  {error[:150]}")
            else:
                completed_count += 1
                traj = result.get("trajectory")
                steps = len(traj) if traj else 0
                rw = result.get("reward")
                rw_s = f"{rw:.2f}" if rw is not None else "N/A"
                n = completed_count + failed_count

                if result.get("status") != "completed" or not traj:
                    reason = result.get("status", "unknown") if result.get("status") != "completed" else "empty_trajectory"
                    ts = datetime.now().isoformat()
                    err_fh.write(f"[{ts}] cve_id={cve_id} trial={t_idx} skipped={reason}\n")
                    err_fh.flush()
                    print(f"[{n}/{total_jobs}] SKIP  {cve_id} trial={t_idx}  reward={rw_s} steps={steps}  ({elapsed:.0f}s)  {reason}")
                else:
                    record = {
                        "cve_id": cve_id,
                        "trial_idx": t_idx,
                        "reward": rw,
                        "success": result.get("success"),
                        "status": result.get("status"),
                        "duration": result.get("duration"),
                        "trajectory": traj,
                        "metadata": result.get("metadata"),
                        "model_name": model_name,
                        "llm_endpoint": llm_endpoint,
                        "timestamp": datetime.now().isoformat(),
                    }
                    traj_fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                    traj_fh.flush()
                    print(f"[{n}/{total_jobs}] OK    {cve_id} trial={t_idx}  reward={rw_s} steps={steps}  ({elapsed:.0f}s)")

    tasks = [_run(ri, row, ti) for ri, row, ti in jobs]
    await asyncio.gather(*tasks)

    traj_fh.close()
    err_fh.close()
    await client.close()

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"Collection complete.")
    print(f"  Total time:   {elapsed:.0f}s ({elapsed/3600:.1f}h)")
    print(f"  Completed:    {completed_count}")
    print(f"  Failed:       {failed_count}")
    print(f"  Trajectories: {traj_file}")
    print(f"  Error log:    {error_file}")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="VulRL SFT rollout collector")
    p.add_argument("--parquet", required=True, help="Path to training parquet")
    p.add_argument("--output-dir", required=True, help="Output directory")
    p.add_argument("--llm-endpoint", required=True, help="LLM API base URL (OpenAI-compatible)")
    p.add_argument("--model-name", required=True, help="Model name for /v1/chat/completions")
    p.add_argument("--api-key", default=None, help="API key for LLM endpoint")
    p.add_argument("--trials", type=int, default=20, help="Trials per case")
    p.add_argument("--max-concurrent", type=int, default=5, help="Max concurrent rollouts")
    p.add_argument("--router-url", default="http://localhost:12345", help="Worker Router URL")
    p.add_argument("--poll-interval", type=float, default=15.0, help="Poll interval (seconds)")
    p.add_argument("--rollout-timeout", type=int, default=1800, help="Per-rollout timeout (seconds)")
    p.add_argument("--temperature", type=float, default=0.7, help="LLM temperature")
    p.add_argument("--max-tokens", type=int, default=4096, help="LLM max tokens per turn")
    args = p.parse_args()

    api_key = args.api_key or os.environ.get("LLM_API_KEY")

    asyncio.run(collect(
        parquet_path=args.parquet,
        output_dir=Path(args.output_dir),
        llm_endpoint=args.llm_endpoint,
        model_name=args.model_name,
        api_key=api_key,
        trials_per_case=args.trials,
        max_concurrent=args.max_concurrent,
        router_url=args.router_url,
        poll_interval=args.poll_interval,
        rollout_timeout=args.rollout_timeout,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    ))


if __name__ == "__main__":
    main()
