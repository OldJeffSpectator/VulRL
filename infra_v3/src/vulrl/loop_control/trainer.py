# src/vulrl/loop_control/trainer.py
"""
Main trainer orchestrator.

Coordinates the RL training loop by managing rollout collection,
batch processing, policy updates, and checkpointing.
"""

from typing import Dict, Any, Optional
from pathlib import Path

from vulrl.config import TrainingConfig, EnvConfig, RewardConfig
from .rollout_collector import RolloutCollector
from .batch_manager import BatchManager
from .policy_updater import PolicyUpdater
from .checkpoint_manager import CheckpointManager


class Trainer:
    """
    Main trainer orchestrator for VulRL.
    
    Coordinates the complete RL training loop, including:
    - Rollout collection from environments
    - Batch assembly and processing
    - Policy updates via RL algorithm
    - Checkpoint saving and management
    """
    
    def __init__(
        self,
        training_config: TrainingConfig,
        env_config: EnvConfig,
        reward_config: RewardConfig
    ):
        """
        Initialize trainer.
        
        Args:
            training_config: Training configuration
            env_config: Environment configuration
            reward_config: Reward configuration
        """
        self.training_config = training_config
        self.env_config = env_config
        self.reward_config = reward_config
        
        # Initialize components
        self.rollout_collector = RolloutCollector(training_config, env_config, reward_config)
        self.batch_manager = BatchManager(training_config)
        self.policy_updater = PolicyUpdater(training_config)
        self.checkpoint_manager = CheckpointManager(training_config)
        
        # Training state
        self.current_episode = 0
        self.total_steps = 0
        self.metrics = {}
    
    def train(self) -> Dict[str, Any]:
        """
        Run the complete training loop.
        
        Returns:
            Dictionary containing training metrics and final results
        """
        # TODO: Implement main training loop
        # 1. Initialize environments and policy
        # 2. For each episode:
        #    a. Collect rollouts
        #    b. Assemble batches
        #    c. Update policy
        #    d. Save checkpoints
        #    e. Log metrics
        # 3. Cleanup and return results
        
        print(f"[Trainer] Starting training for {self.training_config.num_episodes} episodes")
        
        for episode in range(self.training_config.num_episodes):
            self.current_episode = episode
            
            # Collect rollouts
            rollouts = self.rollout_collector.collect()
            
            # Assemble batches
            batches = self.batch_manager.create_batches(rollouts)
            
            # Update policy
            update_metrics = self.policy_updater.update(batches)
            
            # Save checkpoint
            if episode % self.training_config.checkpoint_interval == 0:
                self.checkpoint_manager.save(episode, update_metrics)
            
            # Update metrics
            self.metrics.update(update_metrics)
            
            print(f"[Trainer] Episode {episode}/{self.training_config.num_episodes} complete")
        
        print("[Trainer] Training complete")
        return self.metrics
    
    def resume_from_checkpoint(self, checkpoint_path: str) -> None:
        """
        Resume training from a checkpoint.
        
        Args:
            checkpoint_path: Path to checkpoint directory
        """
        # TODO: Implement checkpoint resumption
        print(f"[Trainer] Resuming from checkpoint: {checkpoint_path}")
        self.checkpoint_manager.load(checkpoint_path)
    
    def cleanup(self) -> None:
        """Cleanup trainer resources."""
        self.rollout_collector.cleanup()
        self.batch_manager.cleanup()
        self.policy_updater.cleanup()


def create_trainer(
    training_config: TrainingConfig,
    env_config: EnvConfig,
    reward_config: RewardConfig
) -> Trainer:
    """
    Factory function to create a trainer.
    
    Args:
        training_config: Training configuration
        env_config: Environment configuration
        reward_config: Reward configuration
        
    Returns:
        Configured Trainer instance
    """
    return Trainer(training_config, env_config, reward_config)
