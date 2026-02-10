#!/usr/bin/env python3
"""
VulRL Training Launcher

Entry point for RL training with the VulRL framework.
Supports Vulhub, CVE-bench, and Xbow environments.

Usage:
    python -m vulrl.scripts.rl_launcher --task-type vulhub --task-id jenkins/CVE-2018-1000861
    python -m vulrl.scripts.rl_launcher --config training_config.yaml
"""

import os
import sys
import argparse
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
import json

from vulrl.config import (
    TrainingConfig,
    EnvConfig,
    RewardConfig,
    create_training_config,
    create_env_config,
)
from vulrl.env_manage.docker_manager import DockerManager


class RLLauncher:
    """
    RL Training Launcher for VulRL.
    
    Manages prerequisites, environment setup, and training launch.
    """
    
    def __init__(self, args):
        """
        Initialize launcher with command-line arguments.
        
        Args:
            args: Parsed command-line arguments
        """
        self.args = args
        
        # Paths
        self.project_root = Path(__file__).parent.parent.parent.parent.parent.resolve()  # Go up to repo root
        self.skyrl_dir = Path.home() / "SkyRL" / "skyrl-train"
        self.vulhub_dir = Path.home() / "vulhub"
        self.checkpoint_dir = Path(args.checkpoint_dir).expanduser()
        self.data_dir = self.project_root / "dataset" / args.dataset_name
        
        # Configurations
        self.training_config: Optional[TrainingConfig] = None
        self.env_config: Optional[EnvConfig] = None
        self.reward_config: Optional[RewardConfig] = None
    
    def check_prerequisites(self) -> bool:
        """
        Check all prerequisites for training.
        
        Returns:
            True if all prerequisites are met
        """
        print("=" * 60)
        print("Checking Prerequisites")
        print("=" * 60)
        
        checks = []
        
        # SkyRL
        if self.skyrl_dir.exists():
            print(f"✓ SkyRL: {self.skyrl_dir}")
            checks.append(True)
        else:
            print(f"✗ SkyRL not found at {self.skyrl_dir}")
            print(f"  Please install SkyRL: git clone https://github.com/PKU-Alignment/SkyRL.git ~/SkyRL")
            checks.append(False)
        
        # Vulhub (if using Vulhub environment)
        if self.args.task_type == "vulhub":
            if self.vulhub_dir.exists():
                print(f"✓ Vulhub: {self.vulhub_dir}")
                checks.append(True)
            else:
                print(f"✗ Vulhub not found at {self.vulhub_dir}")
                print(f"  Please install Vulhub: git clone https://github.com/vulhub/vulhub.git ~/vulhub")
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
        
        # Training data
        train_data = self.data_dir / "train.parquet"
        if train_data.exists():
            print(f"✓ Training data: {train_data}")
            checks.append(True)
        else:
            print(f"✗ Training data not found at {train_data}")
            print(f"  Please prepare dataset in {self.data_dir}")
            checks.append(False)
        
        # Python dependencies
        try:
            import docker
            print("✓ Python docker library installed")
            checks.append(True)
        except ImportError:
            print("✗ Python docker library not found")
            print("  Install: pip install docker")
            checks.append(False)
        
        return all(checks)
    
    def prepare_environment(self):
        """Prepare training environment."""
        print("\n" + "=" * 60)
        print("Preparing Environment")
        print("=" * 60)
        
        # Create checkpoint directory
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ Checkpoint dir: {self.checkpoint_dir}")
        
        # Build attacker Docker image (using centralized DockerManager)
        try:
            DockerManager.ensure_attacker_image()
            print("✓ Attacker image ready")
        except Exception as e:
            print(f"Warning: Failed to ensure attacker image: {e}")
        
        # Set environment variables
        os.environ["PYTHONPATH"] = str(self.skyrl_dir)
        os.environ["RAY_EXPERIMENTAL_NOSET_CUDA_VISIBLE_DEVICES"] = "1"
        
        # Set UV cache directory if needed
        if sys.platform != "win32":
            uv_cache_dir = "/data1/.cache/uv" if Path("/data1").exists() else Path.home() / ".cache" / "uv"
            os.makedirs(uv_cache_dir, exist_ok=True)
            os.environ["UV_CACHE_DIR"] = str(uv_cache_dir)
            print(f"✓ UV cache: {uv_cache_dir}")
        
        print(f"✓ PYTHONPATH: {os.environ['PYTHONPATH']}")
    
    def build_configs(self):
        """Build configuration objects."""
        print("\n" + "=" * 60)
        print("Building Configurations")
        print("=" * 60)
        
        # Training configuration
        self.training_config = create_training_config(
            base_model=self.args.base_model,
            num_episodes=self.args.num_episodes,
            batch_size=self.args.batch_size,
            learning_rate=self.args.learning_rate,
            max_steps_per_episode=self.args.max_steps,
            algorithm=self.args.algorithm,
            num_workers=self.args.num_workers,
            checkpoint_dir=str(self.checkpoint_dir),
            checkpoint_interval=self.args.checkpoint_interval,
            num_gpus=self.args.num_gpus,
            num_cpus=self.args.num_cpus,
            seed=self.args.seed,
        )
        
        # Environment configuration
        backend_config = {}
        if self.args.task_type == "vulhub":
            backend_config["vulhub_path"] = self.args.task_id
        elif self.args.task_type == "cvebench":
            backend_config["compose_path"] = self.args.compose_path
            backend_config["eval_config_path"] = self.args.eval_config_path
        elif self.args.task_type == "xbow":
            backend_config["compose_path"] = self.args.compose_path
            backend_config["benchmark_id"] = self.args.benchmark_id
        
        self.env_config = create_env_config(
            task_id=self.args.task_id,
            task_type=self.args.task_type,
            max_steps=self.args.max_steps,
            backend_config=backend_config,
        )
        
        # Reward configuration
        self.reward_config = RewardConfig(
            step_weight=self.args.step_weight,
            trajectory_weight=self.args.trajectory_weight,
            visual_weight=self.args.visual_weight,
        )
        
        print(f"✓ Training config: {self.args.algorithm} algorithm, {self.args.num_episodes} episodes")
        print(f"✓ Environment config: {self.args.task_type} - {self.args.task_id}")
        print(f"✓ Reward config: step={self.args.step_weight}, traj={self.args.trajectory_weight}, vis={self.args.visual_weight}")
    
    def build_skyrl_command(self) -> list:
        """
        Build SkyRL training command.
        
        Returns:
            Command as list of strings
        """
        cmd = [
            "uv", "run", "--isolated", "--extra", "vllm",
            "--with", "docker",
            "--with", "requests",
            "--with", "Pillow",
            "python", "main_training.py"
        ]
        
        # Data parameters
        train_data_path = str(self.data_dir / "train.parquet")
        params = [
            f"++data.train_data=['{train_data_path}']",
            "++data.val_data=null",
        ]
        
        # Algorithm parameters
        params.extend([
            f"++trainer.algorithm.name={self.training_config.algorithm}",
            f"++trainer.algorithm.advantage_estimator={self.training_config.advantage_estimator}",
            "++trainer.algorithm.kl_coef=0.0",
            "++trainer.algorithm.entropy_coef=0.0",
            "++trainer.algorithm.normalize_advantage=False",
        ])
        
        # Training parameters
        params.extend([
            f"++trainer.train_batch_size={self.training_config.batch_size}",
            f"++trainer.policy_mini_batch_size={self.training_config.batch_size}",
            f"++trainer.rollout_batch_size={self.training_config.batch_size}",
            f"++trainer.rollouts_per_task={self.args.rollouts_per_task}",
            f"++trainer.learning_rate={self.training_config.learning_rate}",
            f"++trainer.epochs={self.args.epochs}",
            "++trainer.eval_interval=-1",
        ])
        
        # Checkpoint parameters
        params.extend([
            f"++trainer.checkpoint_dir={self.training_config.checkpoint_dir}",
            f"++trainer.save_interval={self.training_config.checkpoint_interval}",
        ])
        
        # Model parameters
        params.extend([
            f"++trainer.policy.model.path={self.training_config.base_model}",
            "++trainer.policy.model.lora.rank=16",
            "++trainer.policy.model.lora.alpha=32",
            "++trainer.policy.model.lora.dropout=0.05",
            "++trainer.policy.model.lora.target_modules=all-linear",
        ])
        
        # GPU placement (single GPU colocated)
        params.extend([
            "++trainer.placement.colocate_all=true",
            "++trainer.placement.policy_num_nodes=1",
            f"++trainer.placement.policy_num_gpus_per_node={self.training_config.num_gpus}",
            "++trainer.placement.ref_num_nodes=1",
            f"++trainer.placement.ref_num_gpus_per_node={self.training_config.num_gpus}",
            "++trainer.placement.critic_num_nodes=1",
            f"++trainer.placement.critic_num_gpus_per_node={self.training_config.num_gpus}",
            "++trainer.placement.reward_num_nodes=1",
            f"++trainer.placement.reward_num_gpus_per_node={self.training_config.num_gpus}",
        ])
        
        # Generator parameters
        params.extend([
            "++generator.num_inference_engines=1",
            "++generator.inference_backend=vllm",
            "++generator.inference_engine_tensor_parallel_size=1",
            "++generator.gpu_memory_utilization=0.5",
            "+generator.engine_init_kwargs.max_model_len=4096",
        ])
        
        # Dispatcher
        params.append("++dispatcher.strategy=async_pipeline")
        
        # Logging
        params.append("++logging.backend=local")
        
        # Max turns for multi-step interaction
        params.append(f"++generator.max_turns={self.training_config.max_steps_per_episode}")
        
        cmd.extend(params)
        return cmd
    
    def launch_training(self):
        """Launch the training process."""
        print("\n" + "=" * 60)
        print("Launching Training")
        print("=" * 60)
        
        print(f"\nModel: {self.training_config.base_model}")
        print(f"Algorithm: {self.training_config.algorithm}")
        print(f"Task: {self.env_config.task_type} - {self.env_config.task_id}")
        print(f"Episodes: {self.training_config.num_episodes}")
        print(f"Batch Size: {self.training_config.batch_size}")
        print(f"Learning Rate: {self.training_config.learning_rate}")
        
        cmd = self.build_skyrl_command()
        
        print("\n" + "=" * 60)
        print("Command:")
        print(" \\\n  ".join(cmd))
        print("=" * 60)
        
        # Change to SkyRL directory
        os.chdir(self.skyrl_dir)
        
        try:
            result = subprocess.run(" ".join(cmd), shell=True, env=os.environ.copy())
            if result.returncode == 0:
                print("\n✓ Training completed!")
                return 0
            else:
                print(f"\n✗ Training failed with code {result.returncode}")
                return result.returncode
        except KeyboardInterrupt:
            print("\n\nTraining interrupted by user")
            return 130
        except Exception as e:
            print(f"\n✗ Error: {e}")
            return 1
    
    def run(self) -> int:
        """
        Run the complete training pipeline.
        
        Returns:
            Exit code (0 for success)
        """
        if not self.check_prerequisites():
            print("\n✗ Prerequisites not met")
            return 1
        
        self.prepare_environment()
        
        # Check if parallel training mode
        if self.args.task_ids_file or (hasattr(self.args, 'task_ids') and self.args.task_ids):
            return self.run_parallel_training()
        
        self.build_configs()
        return self.launch_training()
    
    def run_parallel_training(self) -> int:
        """
        Run training on multiple task-ids in parallel.
        
        Returns:
            Exit code (0 for success)
        """
        print("\n" + "=" * 60)
        print("Parallel Training Mode")
        print("=" * 60)
        
        # Load task IDs
        task_ids = []
        if self.args.task_ids_file:
            task_ids_file = Path(self.args.task_ids_file).expanduser()
            if not task_ids_file.exists():
                print(f"✗ Task IDs file not found: {task_ids_file}")
                return 1
            
            with open(task_ids_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        task_ids.append(line)
        elif hasattr(self.args, 'task_ids') and self.args.task_ids:
            task_ids = self.args.task_ids.split(',')
        
        if not task_ids:
            print("✗ No task IDs provided")
            return 1
        
        print(f"Task IDs: {len(task_ids)}")
        print(f"Max workers: {self.args.max_workers}")
        print(f"Task type: {self.args.task_type}")
        
        # Create task-specific configurations
        task_configs = []
        for task_id in task_ids:
            task_config = {
                'task_id': task_id,
                'task_type': self.args.task_type,
                'checkpoint_dir': str(self.checkpoint_dir / task_id.replace('/', '_')),
                'base_model': self.args.base_model,
                'num_episodes': self.args.num_episodes,
                'batch_size': self.args.batch_size,
                'learning_rate': self.args.learning_rate,
                'max_steps': self.args.max_steps,
                'algorithm': self.args.algorithm,
                'num_workers': 1,  # Each parallel task uses 1 worker
                'rollouts_per_task': self.args.rollouts_per_task,
                'epochs': self.args.epochs,
                'num_gpus': self.args.num_gpus // self.args.max_workers if self.args.num_gpus > 1 else 1,
                'seed': self.args.seed,
            }
            task_configs.append(task_config)
        
        # Run tasks in parallel
        results = []
        
        def run_single_task(config: Dict[str, Any]) -> Dict[str, Any]:
            """Run training for a single task."""
            task_id = config['task_id']
            try:
                print(f"\n[Worker] Starting task: {task_id}")
                start_time = time.time()
                
                # Create task-specific launcher
                task_args = argparse.Namespace(**{
                    **vars(self.args),
                    'task_id': task_id,
                    'checkpoint_dir': config['checkpoint_dir'],
                    'num_workers': config['num_workers'],
                    'num_gpus': config['num_gpus'],
                })
                
                task_launcher = RLLauncher(task_args)
                task_launcher.build_configs()
                return_code = task_launcher.launch_training()
                
                elapsed = time.time() - start_time
                print(f"[Worker] Completed task: {task_id} (elapsed: {elapsed:.1f}s)")
                
                return {
                    'task_id': task_id,
                    'return_code': return_code,
                    'elapsed_time': elapsed,
                    'checkpoint_dir': config['checkpoint_dir'],
                }
            except Exception as e:
                print(f"[Worker] Error in task {task_id}: {e}")
                return {
                    'task_id': task_id,
                    'return_code': 1,
                    'error': str(e),
                }
        
        # Use ProcessPoolExecutor for CPU-bound tasks
        with ProcessPoolExecutor(max_workers=self.args.max_workers) as executor:
            future_to_task = {
                executor.submit(run_single_task, config): config['task_id']
                for config in task_configs
            }
            
            for future in as_completed(future_to_task):
                task_id = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"\n✗ Exception for task {task_id}: {e}")
                    results.append({
                        'task_id': task_id,
                        'return_code': 1,
                        'error': str(e),
                    })
        
        # Generate summary report
        print("\n" + "=" * 60)
        print("Parallel Training Summary")
        print("=" * 60)
        
        successful = sum(1 for r in results if r.get('return_code') == 0)
        failed = sum(1 for r in results if r.get('return_code') != 0)
        
        print(f"Total tasks: {len(results)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        
        # Save summary
        summary_file = self.checkpoint_dir / "parallel_training_summary.json"
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_file, 'w') as f:
            json.dump({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'task_type': self.args.task_type,
                'max_workers': self.args.max_workers,
                'total_tasks': len(results),
                'successful': successful,
                'failed': failed,
                'results': results,
            }, f, indent=2)
        print(f"\n✓ Summary saved to {summary_file}")
        
        return 0 if successful > 0 else 1


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="VulRL Training Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train on Vulhub
  python -m vulrl.scripts.rl_launcher --task-type vulhub --task-id jenkins/CVE-2018-1000861

  # Train on CVE-bench
  python -m vulrl.scripts.rl_launcher --task-type cvebench --task-id CVE-2024-2624

  # Custom configuration
  python -m vulrl.scripts.rl_launcher --batch-size 8 --num-episodes 2000 --learning-rate 5e-6
        """
    )
    
    # Environment arguments
    env_group = parser.add_argument_group("Environment")
    env_group.add_argument("--task-type", type=str, default="vulhub",
                          choices=["vulhub", "cvebench", "xbow"],
                          help="Type of environment (default: vulhub)")
    env_group.add_argument("--task-id", type=str, default=None,
                          help="Task identifier (e.g., jenkins/CVE-2018-1000861)")
    env_group.add_argument("--task-ids", type=str, default=None,
                          help="Comma-separated task IDs for parallel training")
    env_group.add_argument("--task-ids-file", type=str, default=None,
                          help="File containing task IDs (one per line) for parallel training")
    env_group.add_argument("--max-steps", type=int, default=30,
                          help="Maximum steps per episode (default: 30)")
    env_group.add_argument("--compose-path", type=str, default=None,
                          help="Path to docker-compose.yml (for cvebench/xbow)")
    env_group.add_argument("--eval-config-path", type=str, default=None,
                          help="Path to evaluation config (for cvebench)")
    env_group.add_argument("--benchmark-id", type=str, default=None,
                          help="Benchmark identifier (for xbow)")
    
    # Training arguments
    train_group = parser.add_argument_group("Training")
    train_group.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-3B-Instruct",
                            help="Base model path (default: Qwen/Qwen2.5-3B-Instruct)")
    train_group.add_argument("--num-episodes", type=int, default=1000,
                            help="Number of training episodes (default: 1000)")
    train_group.add_argument("--batch-size", type=int, default=4,
                            help="Training batch size (default: 4)")
    train_group.add_argument("--learning-rate", type=float, default=1e-6,
                            help="Learning rate (default: 1e-6)")
    train_group.add_argument("--algorithm", type=str, default="grpo",
                            choices=["grpo", "ppo"],
                            help="RL algorithm (default: grpo)")
    train_group.add_argument("--num-workers", type=int, default=4,
                            help="Number of parallel workers (default: 4)")
    train_group.add_argument("--rollouts-per-task", type=int, default=4,
                            help="Rollouts per task (default: 4)")
    train_group.add_argument("--epochs", type=int, default=20,
                            help="Training epochs (default: 20)")
    
    # System arguments
    sys_group = parser.add_argument_group("System")
    sys_group.add_argument("--checkpoint-dir", type=str, default="~/checkpoints/vulrl_agent",
                          help="Checkpoint directory (default: ~/checkpoints/vulrl_agent)")
    sys_group.add_argument("--checkpoint-interval", type=int, default=100,
                          help="Save checkpoint every N steps (default: 100)")
    sys_group.add_argument("--num-gpus", type=int, default=1,
                          help="Number of GPUs (default: 1)")
    sys_group.add_argument("--num-cpus", type=int, default=4,
                          help="Number of CPUs (default: 4)")
    sys_group.add_argument("--seed", type=int, default=42,
                          help="Random seed (default: 42)")
    sys_group.add_argument("--dataset-name", type=str, default="cve_vulhub",
                          help="Dataset name (default: cve_vulhub)")
    
    # Reward arguments
    reward_group = parser.add_argument_group("Reward")
    reward_group.add_argument("--step-weight", type=float, default=0.3,
                             help="Step reward weight (default: 0.3)")
    reward_group.add_argument("--trajectory-weight", type=float, default=0.4,
                             help="Trajectory reward weight (default: 0.4)")
    reward_group.add_argument("--visual-weight", type=float, default=0.3,
                             help="Visual reward weight (default: 0.3)")
    
    # Parallel execution arguments
    parallel_group = parser.add_argument_group("Parallel Execution")
    parallel_group.add_argument("--max-workers", type=int, default=4,
                               help="Maximum number of parallel workers (default: 4)")
    
    args = parser.parse_args()
    
    # Validate that either task-id or task-ids/task-ids-file is provided
    if not args.task_id and not args.task_ids and not args.task_ids_file:
        parser.error("One of --task-id, --task-ids, or --task-ids-file is required")
    
    return args


def main():
    """Main entry point."""
    args = parse_args()
    launcher = RLLauncher(args)
    return launcher.run()


if __name__ == "__main__":
    sys.exit(main())
