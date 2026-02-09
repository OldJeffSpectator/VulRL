# src/vulrl/config/command_builder.py
"""
Command builder utilities.

Provides utilities for building complex command-line arguments
for training and evaluation scripts.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path

from .training_config import TrainingConfig
from .env_config import EnvConfig
from .reward_config import RewardConfig


class CommandBuilder:
    """
    Builder for constructing command-line arguments.
    
    Provides a fluent interface for building complex commands
    with proper escaping and formatting.
    """
    
    def __init__(self, base_command: List[str]):
        """
        Initialize command builder.
        
        Args:
            base_command: Base command as list of strings (e.g., ["python", "script.py"])
        """
        self.command = base_command.copy()
    
    def add_arg(self, flag: str, value: Any = None) -> "CommandBuilder":
        """
        Add a command-line argument.
        
        Args:
            flag: Argument flag (e.g., "--model")
            value: Argument value (None for boolean flags)
            
        Returns:
            Self for chaining
        """
        self.command.append(flag)
        if value is not None:
            self.command.append(str(value))
        return self
    
    def add_args(self, args_dict: Dict[str, Any]) -> "CommandBuilder":
        """
        Add multiple arguments from dictionary.
        
        Args:
            args_dict: Dictionary of flag -> value pairs
            
        Returns:
            Self for chaining
        """
        for flag, value in args_dict.items():
            if value is not None:
                if isinstance(value, bool):
                    if value:
                        self.add_arg(flag)
                else:
                    self.add_arg(flag, value)
        return self
    
    def build(self) -> List[str]:
        """
        Build final command.
        
        Returns:
            Command as list of strings
        """
        return self.command


def build_training_command(
    training_config: TrainingConfig,
    env_config: EnvConfig,
    reward_config: RewardConfig,
    script_path: str = "vulrl.scripts.rl_launcher"
) -> List[str]:
    """
    Build command for launching training.
    
    Args:
        training_config: Training configuration
        env_config: Environment configuration
        reward_config: Reward configuration
        script_path: Path to training script
        
    Returns:
        Command as list of strings
    """
    builder = CommandBuilder(["python", "-m", script_path])
    
    # Add training arguments
    builder.add_arg("--base-model", training_config.base_model)
    builder.add_arg("--model-name", training_config.model_name)
    builder.add_arg("--num-episodes", training_config.num_episodes)
    builder.add_arg("--batch-size", training_config.batch_size)
    builder.add_arg("--learning-rate", training_config.learning_rate)
    builder.add_arg("--max-steps", training_config.max_steps_per_episode)
    builder.add_arg("--algorithm", training_config.algorithm)
    builder.add_arg("--num-workers", training_config.num_workers)
    builder.add_arg("--checkpoint-dir", training_config.checkpoint_dir)
    builder.add_arg("--checkpoint-interval", training_config.checkpoint_interval)
    
    if training_config.ray_address:
        builder.add_arg("--ray-address", training_config.ray_address)
    
    builder.add_arg("--num-gpus", training_config.num_gpus)
    builder.add_arg("--num-cpus", training_config.num_cpus)
    builder.add_arg("--seed", training_config.seed)
    
    if training_config.wandb_project:
        builder.add_arg("--wandb-project", training_config.wandb_project)
    
    # Add environment arguments
    builder.add_arg("--task-id", env_config.task_id)
    builder.add_arg("--task-type", env_config.task_type)
    
    # Add reward arguments
    builder.add_arg("--step-weight", reward_config.step_weight)
    builder.add_arg("--trajectory-weight", reward_config.trajectory_weight)
    builder.add_arg("--visual-weight", reward_config.visual_weight)
    
    return builder.build()


def build_eval_command(
    checkpoint_path: str,
    task_file: str,
    model_name: str = "cve_lora",
    base_model: str = "Qwen/Qwen2.5-3B-Instruct",
    additional_args: Optional[Dict[str, Any]] = None
) -> List[str]:
    """
    Build command for launching evaluation with Inspect AI.
    
    Args:
        checkpoint_path: Path to model checkpoint
        task_file: Path to Inspect AI task file
        model_name: Model provider name
        base_model: Base model identifier
        additional_args: Additional arguments for inspect eval
        
    Returns:
        Command as list of strings
    """
    builder = CommandBuilder(["inspect", "eval", task_file])
    
    builder.add_arg("--model", model_name)
    builder.add_arg("-M", f"checkpoint_path={checkpoint_path}")
    builder.add_arg("-M", f"base_model={base_model}")
    
    if additional_args:
        builder.add_args(additional_args)
    
    return builder.build()
