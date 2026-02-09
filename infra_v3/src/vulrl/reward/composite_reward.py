# src/vulrl/reward/composite_reward.py
"""
Composite reward orchestrator.

Combines multiple reward signals (step, trajectory, visual) into a unified reward.
"""

from typing import Any, Dict, List, Optional

from .base_reward import BaseReward, RewardResult
from .step_reward import StepReward
from .trajectory_reward import TrajectoryReward
from .visual_reward import VisualReward


class CompositeReward(BaseReward):
    """
    Composite reward orchestrator that combines multiple reward signals.
    
    Manages and combines step-level, trajectory-level, and visual rewards
    into a unified reward signal with configurable weighting.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Initialize individual reward components
        self.step_reward = StepReward(config.get("step_reward_config", {}))
        self.trajectory_reward = TrajectoryReward(config.get("trajectory_reward_config", {}))
        self.visual_reward = VisualReward(config.get("visual_reward_config", {}))
        
        # Reward weights (configurable)
        self.step_weight = config.get("step_weight", 0.3)
        self.trajectory_weight = config.get("trajectory_weight", 0.4)
        self.visual_weight = config.get("visual_weight", 0.3)
        
        # Enable/disable individual components
        self.enable_step = config.get("enable_step_reward", True)
        self.enable_trajectory = config.get("enable_trajectory_reward", True)
        self.enable_visual = config.get("enable_visual_reward", True)
    
    def compute(
        self,
        observation: str,
        action: Dict[str, Any],
        next_observation: str,
        step_info: Dict[str, Any],
        episode_history: Optional[List[Dict[str, Any]]] = None
    ) -> RewardResult:
        """
        Compute composite reward by combining multiple reward signals.
        
        Args:
            observation: The observation before the action
            action: The action taken by the agent
            next_observation: The observation after the action
            step_info: Additional information about the step
            episode_history: Episode history for trajectory-based rewards
            
        Returns:
            RewardResult with combined reward
        """
        # TODO: Implement composite reward orchestration
        # - Compute individual rewards
        # - Combine with configured weights
        # - Handle termination conditions
        # - Aggregate info from all components
        
        total_reward = 0.0
        done = False
        info = {
            "reward_type": "composite",
            "components": {}
        }
        
        # Step reward
        if self.enable_step:
            step_result = self.step_reward.compute(
                observation, action, next_observation, step_info, episode_history
            )
            total_reward += self.step_weight * step_result.reward
            info["components"]["step"] = step_result.info
            done = done or step_result.done
        
        # Trajectory reward
        if self.enable_trajectory and episode_history:
            traj_result = self.trajectory_reward.compute(
                observation, action, next_observation, step_info, episode_history
            )
            total_reward += self.trajectory_weight * traj_result.reward
            info["components"]["trajectory"] = traj_result.info
            done = done or traj_result.done
        
        # Visual reward
        if self.enable_visual:
            visual_result = self.visual_reward.compute(
                observation, action, next_observation, step_info, episode_history
            )
            total_reward += self.visual_weight * visual_result.reward
            info["components"]["visual"] = visual_result.info
            done = done or visual_result.done
        
        info["total_reward"] = total_reward
        
        return RewardResult(reward=total_reward, done=done, info=info)
    
    def reset(self) -> None:
        """Reset all reward components."""
        self.step_reward.reset()
        self.trajectory_reward.reset()
        self.visual_reward.reset()
    
    def cleanup(self) -> None:
        """Cleanup all reward components."""
        self.step_reward.cleanup()
        self.trajectory_reward.cleanup()
        self.visual_reward.cleanup()
