# src/vulrl/reward/trajectory_reward.py
"""
Trajectory-level reward computation (episode-based evaluation).

Evaluates the entire episode trajectory to provide holistic feedback.
"""

from typing import Any, Dict, List, Optional

from .base_reward import BaseReward, RewardResult


class TrajectoryReward(BaseReward):
    """
    Trajectory-level reward function for episode-based evaluation.
    
    Evaluates the entire sequence of actions and observations to provide
    holistic feedback on strategy, coherence, and overall success.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # TODO: Initialize LLM client or other resources for trajectory evaluation
    
    def compute(
        self,
        observation: str,
        action: Dict[str, Any],
        next_observation: str,
        step_info: Dict[str, Any],
        episode_history: Optional[List[Dict[str, Any]]] = None
    ) -> RewardResult:
        """
        Compute trajectory-level reward based on episode history.
        
        Args:
            observation: The observation before the action
            action: The action taken by the agent
            next_observation: The observation after the action
            step_info: Additional information about the step
            episode_history: Full episode history for trajectory analysis (required)
            
        Returns:
            RewardResult with trajectory-level reward
        """
        # TODO: Implement trajectory-level reward computation
        # - Analyze overall strategy coherence
        # - Evaluate progress towards goal
        # - Check for efficient action sequences
        # - Assess learning and adaptation
        
        reward = 0.0
        done = False
        info = {
            "reward_type": "trajectory",
            "episode_length": len(episode_history) if episode_history else 0
        }
        
        return RewardResult(reward=reward, done=done, info=info)
