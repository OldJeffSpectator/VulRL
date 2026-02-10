#!/usr/bin/env python3
"""
VulRL Evaluation Launcher

Entry point for model evaluation using Inspect AI with CVE-bench.
Evaluates trained LoRA models on real-world CVE challenges.

Usage:
    python -m vulrl.scripts.test_launcher --checkpoint ~/checkpoints/vulrl_agent/global_step_100
    python -m vulrl.scripts.test_launcher --variants zero_day,one_day
    python -m vulrl.scripts.test_launcher --challenges CVE-2024-2624,CVE-2024-2771
"""

import os
import sys
import json
import argparse
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import time


class TestLauncher:
    """
    Evaluation Launcher for VulRL.
    
    Manages CVE-bench setup and model evaluation.
    """
    
    def __init__(self, args):
        """
        Initialize launcher with command-line arguments.
        
        Args:
            args: Parsed command-line arguments
        """
        self.args = args
        
        # Paths
        self.project_root = Path(__file__).parent.parent.parent.parent.parent.resolve()
        self.cvebench_dir = self.project_root / "benchmark" / "cve-bench"
        self.checkpoint_dir = Path(args.checkpoint_dir).expanduser() if args.checkpoint_dir else Path.home() / "checkpoints" / "vulrl_agent"
        self.results_dir = self.project_root / "infra_v3" / "eval_results"
        
        # VulRL models module path (for model provider registration)
        self.vulrl_models_dir = self.project_root / "infra_v3" / "src" / "vulrl" / "models"
    
    def check_prerequisites(self, skip_checkpoint_check: bool = False) -> bool:
        """
        Check all prerequisites for evaluation.
        
        Args:
            skip_checkpoint_check: Skip checkpoint validation if explicit path provided
            
        Returns:
            True if all prerequisites are met
        """
        print("=" * 60)
        print("Checking Prerequisites")
        print("=" * 60)
        
        checks = []
        
        # CVE-bench
        if self.cvebench_dir.exists():
            print(f"✓ CVE-bench: {self.cvebench_dir}")
            checks.append(True)
        else:
            print(f"✗ CVE-bench not found at {self.cvebench_dir}")
            print(f"  Please run: git clone https://github.com/uiuc-kang-lab/cve-bench.git {self.cvebench_dir}")
            checks.append(False)
        
        # Docker
        try:
            result = subprocess.run(["docker", "--version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                print(f"✓ Docker: {result.stdout.decode().strip()}")
                checks.append(True)
            else:
                print("✗ Docker not working")
                checks.append(False)
        except Exception as e:
            print(f"✗ Docker not found: {e}")
            checks.append(False)
        
        # Checkpoints
        if skip_checkpoint_check:
            print(f"○ Checkpoint check skipped (will use specified path)")
            checks.append(True)
        elif self.checkpoint_dir.exists():
            checkpoints = list(self.checkpoint_dir.glob("global_step_*")) + list(self.checkpoint_dir.glob("checkpoint_episode_*"))
            if checkpoints:
                print(f"✓ Checkpoints: {len(checkpoints)} found in {self.checkpoint_dir}")
                checks.append(True)
            else:
                print(f"✗ No checkpoints found in {self.checkpoint_dir}")
                checks.append(False)
        else:
            print(f"✗ Checkpoint directory not found: {self.checkpoint_dir}")
            checks.append(False)
        
        # VulRL model provider
        provider_file = self.vulrl_models_dir / "model_provider.py"
        if provider_file.exists():
            print(f"✓ Model provider: {provider_file}")
            checks.append(True)
        else:
            print(f"✗ Model provider not found: {provider_file}")
            checks.append(False)
        
        # Inspect AI
        try:
            result = subprocess.run(["inspect", "--version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                print(f"✓ Inspect AI: {result.stdout.decode().strip()}")
                checks.append(True)
            else:
                print("✗ Inspect AI not working")
                checks.append(False)
        except Exception as e:
            print(f"✗ Inspect AI not found: {e}")
            print("  Install: pip install inspect-ai")
            checks.append(False)
        
        return all(checks)
    
    def find_latest_checkpoint(self) -> Optional[Path]:
        """
        Find the latest checkpoint in checkpoint directory.
        
        Returns:
            Path to latest checkpoint, or None if not found
        """
        if not self.checkpoint_dir.exists():
            return None
        
        # Look for both SkyRL format (global_step_*) and VulRL format (checkpoint_episode_*)
        checkpoints = (
            list(self.checkpoint_dir.glob("global_step_*")) +
            list(self.checkpoint_dir.glob("checkpoint_episode_*"))
        )
        
        if not checkpoints:
            return None
        
        def get_step(p):
            try:
                # Extract number from either format
                if "global_step_" in p.name:
                    return int(p.name.split("_")[-1])
                elif "checkpoint_episode_" in p.name:
                    return int(p.name.split("_")[-1])
                return 0
            except:
                return 0
        
        checkpoints.sort(key=get_step, reverse=True)
        return checkpoints[0]
    
    def setup_cvebench(self):
        """Setup CVE-bench environment and register model provider."""
        print("\n" + "=" * 60)
        print("Setting up CVE-bench")
        print("=" * 60)
        
        # Ensure CVE-bench exists
        if not self.cvebench_dir.exists():
            print("Cloning CVE-bench...")
            subprocess.run(
                ["git", "clone", "https://github.com/uiuc-kang-lab/cve-bench.git", str(self.cvebench_dir)],
                check=True
            )
        
        # Install dependencies
        print("Installing CVE-bench dependencies...")
        try:
            subprocess.run(
                ["uv", "sync", "--dev"],
                cwd=self.cvebench_dir,
                check=True
            )
        except subprocess.CalledProcessError:
            print("Warning: uv sync failed, trying pip install...")
            subprocess.run(
                ["pip", "install", "-e", "."],
                cwd=self.cvebench_dir,
                check=True
            )
        
        # Copy model provider to CVE-bench
        src_provider = self.vulrl_models_dir / "model_provider.py"
        dst_provider = self.cvebench_dir / "src" / "cvebench" / "lora_model_provider.py"
        
        if src_provider.exists():
            shutil.copy(src_provider, dst_provider)
            print(f"✓ Copied model provider to {dst_provider}")
        else:
            print(f"✗ Model provider not found at {src_provider}")
            return False
        
        # Copy model registry
        src_registry = self.vulrl_models_dir / "model_registry.py"
        dst_registry = self.cvebench_dir / "src" / "cvebench" / "_registry.py"
        
        if src_registry.exists():
            # Create a simplified registry that imports from the model provider
            registry_content = '''"""Model provider registry for Inspect AI"""
from .lora_model_provider import cve_lora_provider
'''
            dst_registry.write_text(registry_content)
            print(f"✓ Created registry at {dst_registry}")
        
        print("✓ CVE-bench setup complete")
        return True
    
    def run_evaluation(
        self,
        checkpoint: str,
        variants: List[str] = None,
        challenges: List[str] = None,
        max_messages: int = 30,
        base_model: str = "Qwen/Qwen2.5-3B-Instruct",
    ) -> Dict[str, Any]:
        """
        Run evaluation on CVE-bench.
        
        Args:
            checkpoint: Path to checkpoint directory
            variants: List of CVE variants to test (e.g., ["zero_day", "one_day"])
            challenges: List of specific CVE challenges to test
            max_messages: Maximum messages per conversation
            base_model: Base model identifier
            
        Returns:
            Dictionary containing evaluation results
        """
        print("\n" + "=" * 60)
        print("Running Evaluation")
        print("=" * 60)
        
        if variants is None:
            variants = ["zero_day", "one_day"]
        
        # Build Inspect AI command
        cmd = [
            "uv", "run", "inspect", "eval",
            "src/cvebench/cvebench.py@cvebench",
            f"--model=cve_lora/model",
            f"-M", f"checkpoint_path={checkpoint}",
            f"-M", f"base_model={base_model}",
            f"-M", f"max_messages={max_messages}",
        ]
        
        # Add variants
        if variants:
            cmd.extend(["-T", f"variants={','.join(variants)}"])
        
        # Add specific challenges
        if challenges:
            cmd.extend(["-T", f"challenges={','.join(challenges)}"])
        
        print(f"\nCommand: {' '.join(cmd)}")
        print(f"Checkpoint: {checkpoint}")
        print(f"Base Model: {base_model}")
        print(f"Variants: {variants}")
        if challenges:
            print(f"Challenges: {challenges}")
        print()
        
        # Create results directory
        self.results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = self.results_dir / f"eval_{timestamp}.json"
        
        # Run evaluation
        try:
            result = subprocess.run(
                cmd,
                cwd=self.cvebench_dir,
                capture_output=True,
                text=True,
            )
            
            print("STDOUT:")
            print(result.stdout)
            
            if result.stderr:
                print("STDERR:")
                print(result.stderr)
            
            # Parse results
            eval_result = {
                "timestamp": timestamp,
                "checkpoint": checkpoint,
                "base_model": base_model,
                "variants": variants,
                "challenges": challenges,
                "max_messages": max_messages,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
            
            # Save results
            with open(result_file, 'w') as f:
                json.dump(eval_result, f, indent=2)
            print(f"\n✓ Results saved to {result_file}")
            
            if result.returncode == 0:
                print("\n✓ Evaluation completed successfully")
            else:
                print(f"\n✗ Evaluation failed with code {result.returncode}")
            
            return eval_result
            
        except Exception as e:
            print(f"\n✗ Evaluation failed: {e}")
            return {"error": str(e)}
    
    def run_single_challenge(
        self,
        checkpoint: str,
        challenge: str,
        variant: str = "zero_day",
        base_model: str = "Qwen/Qwen2.5-3B-Instruct",
    ) -> Dict[str, Any]:
        """
        Run evaluation on a single challenge (useful for debugging).
        
        Args:
            checkpoint: Path to checkpoint directory
            challenge: CVE challenge ID (e.g., "CVE-2024-2624")
            variant: CVE variant (e.g., "zero_day")
            base_model: Base model identifier
            
        Returns:
            Dictionary containing evaluation results
        """
        print(f"\nRunning single challenge: {challenge} ({variant})")
        
        # Start container
        print("Starting container...")
        try:
            subprocess.run(
                ["./run", "up", challenge],
                cwd=self.cvebench_dir,
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"Warning: Container start failed: {e}")
        
        try:
            # Run evaluation
            result = self.run_evaluation(
                checkpoint=checkpoint,
                variants=[variant],
                challenges=[challenge],
                base_model=base_model,
            )
            return result
        finally:
            # Stop container
            print("\nStopping container...")
            subprocess.run(
                ["./run", "down", challenge],
                cwd=self.cvebench_dir
            )
    
    def generate_report(self, results: List[Dict[str, Any]]) -> str:
        """
        Generate evaluation report from results.
        
        Args:
            results: List of evaluation result dictionaries
            
        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 60)
        report.append("CVE-bench Evaluation Report")
        report.append("=" * 60)
        
        for result in results:
            report.append(f"\nCheckpoint: {result.get('checkpoint', 'N/A')}")
            report.append(f"Base Model: {result.get('base_model', 'N/A')}")
            report.append(f"Variants: {result.get('variants', 'N/A')}")
            report.append(f"Return code: {result.get('returncode', 'N/A')}")
            
            if "error" in result:
                report.append(f"Error: {result['error']}")
        
        return "\n".join(report)
    
    def run_parallel_evaluations(
        self,
        checkpoint: str,
        challenges: List[str],
        variants: List[str],
        max_workers: int = 4,
    ) -> List[Dict[str, Any]]:
        """
        Run evaluations on multiple challenges in parallel.
        
        Args:
            checkpoint: Path to checkpoint directory
            challenges: List of CVE challenge IDs
            variants: List of CVE variants
            max_workers: Maximum number of parallel workers
            
        Returns:
            List of evaluation result dictionaries
        """
        print("\n" + "=" * 60)
        print(f"Running Parallel Evaluations ({max_workers} workers)")
        print("=" * 60)
        print(f"Checkpoint: {checkpoint}")
        print(f"Challenges: {len(challenges)}")
        print(f"Variants: {variants}")
        
        results = []
        
        def run_single_eval(challenge: str) -> Dict[str, Any]:
            """Run evaluation for a single challenge."""
            try:
                print(f"\n[Worker] Starting challenge: {challenge}")
                result = self.run_single_challenge(
                    checkpoint=checkpoint,
                    challenge=challenge,
                    variant=variants[0] if variants else "zero_day",
                    base_model=self.args.base_model,
                )
                print(f"[Worker] Completed challenge: {challenge}")
                return result
            except Exception as e:
                print(f"[Worker] Error in challenge {challenge}: {e}")
                return {
                    "challenge": challenge,
                    "error": str(e),
                    "returncode": 1
                }
        
        # Use ThreadPoolExecutor for I/O-bound tasks (Docker operations)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_challenge = {
                executor.submit(run_single_eval, challenge): challenge
                for challenge in challenges
            }
            
            for future in as_completed(future_to_challenge):
                challenge = future_to_challenge[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"\n✗ Exception for challenge {challenge}: {e}")
                    results.append({
                        "challenge": challenge,
                        "error": str(e),
                        "returncode": 1
                    })
        
        # Generate summary report
        print("\n" + "=" * 60)
        print("Parallel Evaluation Summary")
        print("=" * 60)
        
        successful = sum(1 for r in results if r.get("returncode") == 0)
        failed = sum(1 for r in results if r.get("returncode") != 0)
        
        print(f"Total challenges: {len(results)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        
        return results
    
    def run(self) -> int:
        """
        Run the complete evaluation pipeline.
        
        Returns:
            Exit code (0 for success)
        """
        # Check if explicit checkpoint path is provided
        skip_checkpoint_check = bool(self.args.checkpoint)
        
        if not self.check_prerequisites(skip_checkpoint_check=skip_checkpoint_check):
            print("\n✗ Prerequisites not met")
            return 1
        
        # Setup CVE-bench
        if not self.setup_cvebench():
            print("\n✗ CVE-bench setup failed")
            return 1
        
        # Determine checkpoint to use
        if self.args.checkpoint:
            checkpoint = Path(self.args.checkpoint).expanduser()
        else:
            checkpoint = self.find_latest_checkpoint()
        
        if not checkpoint:
            print("\n✗ No checkpoint found")
            return 1
        
        if not checkpoint.exists():
            print(f"\n✗ Checkpoint not found: {checkpoint}")
            return 1
        
        print(f"\nUsing checkpoint: {checkpoint}")
        
        # Parse variants and challenges
        variants = self.args.variants.split(",") if self.args.variants else ["zero_day", "one_day"]
        challenges = self.args.challenges.split(",") if self.args.challenges else None
        
        # Run evaluation
        if self.args.single_challenge:
            # Single challenge mode (for debugging)
            result = self.run_single_challenge(
                checkpoint=str(checkpoint),
                challenge=self.args.single_challenge,
                variant=variants[0] if variants else "zero_day",
                base_model=self.args.base_model,
            )
            if "error" in result:
                return 1
            return result.get("returncode", 1)
        
        elif self.args.parallel and challenges:
            # Parallel evaluation mode
            results = self.run_parallel_evaluations(
                checkpoint=str(checkpoint),
                challenges=challenges,
                variants=variants,
                max_workers=self.args.max_workers,
            )
            
            # Save aggregated results
            self.results_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_file = self.results_dir / f"eval_parallel_{timestamp}.json"
            
            with open(result_file, 'w') as f:
                json.dump({
                    "timestamp": timestamp,
                    "checkpoint": str(checkpoint),
                    "mode": "parallel",
                    "max_workers": self.args.max_workers,
                    "results": results
                }, f, indent=2)
            print(f"\n✓ Aggregated results saved to {result_file}")
            
            # Return success if at least one succeeded
            return 0 if any(r.get("returncode") == 0 for r in results) else 1
        
        else:
            # Full evaluation mode (sequential)
            result = self.run_evaluation(
                checkpoint=str(checkpoint),
                variants=variants,
                challenges=challenges,
                max_messages=self.args.max_messages,
                base_model=self.args.base_model,
            )
            
            if "error" in result:
                return 1
            
            return result.get("returncode", 1)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="VulRL Evaluation Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Evaluate latest checkpoint
  python -m vulrl.scripts.test_launcher

  # Evaluate specific checkpoint
  python -m vulrl.scripts.test_launcher --checkpoint ~/checkpoints/vulrl_agent/global_step_100

  # Test specific variants
  python -m vulrl.scripts.test_launcher --variants zero_day,one_day

  # Test specific challenges
  python -m vulrl.scripts.test_launcher --challenges CVE-2024-2624,CVE-2024-2771

  # Debug single challenge
  python -m vulrl.scripts.test_launcher --single-challenge CVE-2024-2624
        """
    )
    
    # Checkpoint arguments
    ckpt_group = parser.add_argument_group("Checkpoint")
    ckpt_group.add_argument("--checkpoint", type=str, default=None,
                           help="Path to checkpoint directory (default: latest in checkpoint-dir)")
    ckpt_group.add_argument("--checkpoint-dir", type=str, default=None,
                           help="Checkpoint base directory (default: ~/checkpoints/vulrl_agent)")
    
    # Evaluation arguments
    eval_group = parser.add_argument_group("Evaluation")
    eval_group.add_argument("--variants", type=str, default="zero_day,one_day",
                           help="Comma-separated list of variants (default: zero_day,one_day)")
    eval_group.add_argument("--challenges", type=str, default=None,
                           help="Comma-separated list of specific CVE challenges")
    eval_group.add_argument("--max-messages", type=int, default=30,
                           help="Maximum messages per conversation (default: 30)")
    eval_group.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-3B-Instruct",
                           help="Base model identifier (default: Qwen/Qwen2.5-3B-Instruct)")
    
    # Debug arguments
    debug_group = parser.add_argument_group("Debug")
    debug_group.add_argument("--single-challenge", type=str, default=None,
                            help="Run single challenge for debugging (e.g., CVE-2024-2624)")
    
    # Parallel execution arguments
    parallel_group = parser.add_argument_group("Parallel Execution")
    parallel_group.add_argument("--parallel", action="store_true",
                               help="Run multiple challenges in parallel")
    parallel_group.add_argument("--max-workers", type=int, default=4,
                               help="Maximum number of parallel workers (default: 4)")
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    launcher = TestLauncher(args)
    return launcher.run()


if __name__ == "__main__":
    sys.exit(main())
