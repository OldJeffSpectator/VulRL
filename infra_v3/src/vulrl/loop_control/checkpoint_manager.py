# src/vulrl/loop_control/checkpoint_manager.py
"""
Checkpoint management for RL training.

Handles saving and loading of model checkpoints, including
policy weights, optimizer state, and training metadata.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import json
import shutil

from vulrl.config import TrainingConfig


class CheckpointManager:
    """
    Checkpoint manager for saving and loading training state.
    
    Manages the lifecycle of model checkpoints, including
    saving, loading, and cleanup of checkpoint files.
    """
    
    def __init__(self, training_config: TrainingConfig):
        """
        Initialize checkpoint manager.
        
        Args:
            training_config: Training configuration
        """
        self.training_config = training_config
        self.checkpoint_dir = Path(training_config.checkpoint_dir)
        self.checkpoint_interval = training_config.checkpoint_interval
        
        # Create checkpoint directory
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def save(self, episode: int, metrics: Dict[str, Any]) -> str:
        """
        Save a checkpoint.
        
        Args:
            episode: Current episode number
            metrics: Training metrics to save with checkpoint
            
        Returns:
            Path to saved checkpoint
        """
        # TODO: Implement checkpoint saving
        # 1. Create checkpoint directory
        # 2. Save policy weights
        # 3. Save optimizer state
        # 4. Save training metadata
        
        checkpoint_name = f"checkpoint_episode_{episode}"
        checkpoint_path = self.checkpoint_dir / checkpoint_name
        checkpoint_path.mkdir(parents=True, exist_ok=True)
        
        # Save metadata
        metadata = {
            "episode": episode,
            "metrics": metrics,
            "config": self.training_config.to_dict()
        }
        
        metadata_path = checkpoint_path / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        print(f"[CheckpointManager] Saved checkpoint: {checkpoint_path}")
        
        return str(checkpoint_path)
    
    def load(self, checkpoint_path: str) -> Dict[str, Any]:
        """
        Load a checkpoint.
        
        Args:
            checkpoint_path: Path to checkpoint directory
            
        Returns:
            Dictionary containing loaded checkpoint data
        """
        # TODO: Implement checkpoint loading
        # 1. Load policy weights
        # 2. Load optimizer state
        # 3. Load training metadata
        
        checkpoint_path = Path(checkpoint_path)
        
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
        
        # Load metadata
        metadata_path = checkpoint_path / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
        else:
            metadata = {}
        
        print(f"[CheckpointManager] Loaded checkpoint: {checkpoint_path}")
        
        return metadata
    
    def find_latest_checkpoint(self) -> Optional[str]:
        """
        Find the latest checkpoint in the checkpoint directory.
        
        Returns:
            Path to latest checkpoint, or None if no checkpoints exist
        """
        if not self.checkpoint_dir.exists():
            return None
        
        checkpoints = sorted(
            self.checkpoint_dir.glob("checkpoint_episode_*"),
            key=lambda p: int(p.name.split("_")[-1]) if p.name.split("_")[-1].isdigit() else 0,
            reverse=True
        )
        
        if checkpoints:
            return str(checkpoints[0])
        
        return None
    
    def cleanup_old_checkpoints(self, keep_last_n: int = 5) -> None:
        """
        Remove old checkpoints, keeping only the most recent ones.
        
        Args:
            keep_last_n: Number of recent checkpoints to keep
        """
        if not self.checkpoint_dir.exists():
            return
        
        checkpoints = sorted(
            self.checkpoint_dir.glob("checkpoint_episode_*"),
            key=lambda p: int(p.name.split("_")[-1]) if p.name.split("_")[-1].isdigit() else 0,
            reverse=True
        )
        
        for checkpoint in checkpoints[keep_last_n:]:
            shutil.rmtree(checkpoint)
            print(f"[CheckpointManager] Removed old checkpoint: {checkpoint}")
