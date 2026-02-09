# src/vulrl/config/training_config.py
"""
Training configuration management.

Defines configuration structures for RL training parameters,
including model settings, optimization parameters, and SkyRL-specific options.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
from pathlib import Path


@dataclass
class TrainingConfig:
    """
    Training configuration for VulRL.
    
    Attributes:
        # Model settings
        base_model: Base model identifier
        model_name: Name for the trained model
        
        # Training parameters
        num_episodes: Total number of training episodes
        batch_size: Batch size for training
        learning_rate: Learning rate for optimization
        max_steps_per_episode: Maximum steps per episode
        
        # SkyRL-specific
        algorithm: RL algorithm (grpo, ppo, etc.)
        advantage_estimator: Advantage estimation method (rloo, gae, etc.)
        num_workers: Number of parallel workers
        
        # Checkpointing
        checkpoint_dir: Directory for saving checkpoints
        checkpoint_interval: Episodes between checkpoints
        
        # Ray configuration
        ray_address: Ray cluster address (None for local)
        num_gpus: Number of GPUs to use
        num_cpus: Number of CPUs to use
        
        # Additional settings
        seed: Random seed
        log_dir: Directory for logs
        wandb_project: Weights & Biases project name
        extra_args: Additional arguments
    """
    # Model settings
    base_model: str = "Qwen/Qwen2.5-3B-Instruct"
    model_name: str = "vulrl_agent"
    
    # Training parameters
    num_episodes: int = 1000
    batch_size: int = 8
    learning_rate: float = 1e-5
    max_steps_per_episode: int = 30
    
    # SkyRL-specific
    algorithm: str = "grpo"
    advantage_estimator: str = "rloo"
    num_workers: int = 4
    
    # Checkpointing
    checkpoint_dir: str = "./checkpoints"
    checkpoint_interval: int = 100
    
    # Ray configuration
    ray_address: Optional[str] = None
    num_gpus: int = 1
    num_cpus: int = 4
    
    # Additional settings
    seed: int = 42
    log_dir: str = "./logs"
    wandb_project: Optional[str] = None
    extra_args: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrainingConfig":
        """Create configuration from dictionary."""
        return cls(**data)
    
    def validate(self) -> bool:
        """
        Validate configuration parameters.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        if self.num_episodes <= 0:
            raise ValueError("num_episodes must be positive")
        
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")
        
        if self.max_steps_per_episode <= 0:
            raise ValueError("max_steps_per_episode must be positive")
        
        if self.num_workers <= 0:
            raise ValueError("num_workers must be positive")
        
        return True


def create_training_config(
    base_model: str = "Qwen/Qwen2.5-3B-Instruct",
    **kwargs
) -> TrainingConfig:
    """
    Factory function to create training configuration.
    
    Args:
        base_model: Base model identifier
        **kwargs: Additional configuration parameters
        
    Returns:
        Configured TrainingConfig instance
    """
    config = TrainingConfig(
        base_model=base_model,
        **kwargs
    )
    config.validate()
    return config
