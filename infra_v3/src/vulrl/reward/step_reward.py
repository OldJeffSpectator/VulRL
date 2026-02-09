# src/vulrl/reward/step_reward.py
"""
Step-level reward computation (immediate feedback).

Provides immediate reward signals based on individual action outcomes.
"""

from typing import Any, Dict, List, Optional

from .base_reward import BaseReward, RewardResult


class StepReward(BaseReward):
    """
    Step-level reward function for immediate feedback.
    
    Evaluates individual actions and provides immediate reward signals
    based on action outcomes, tool usage patterns, and progress indicators.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # TODO: Initialize LLM client or other resources for step evaluation
    
    def compute(
        self,
        observation: str,
        action: Dict[str, Any],
        next_observation: str,
        step_info: Dict[str, Any],
        episode_history: Optional[List[Dict[str, Any]]] = None
    ) -> RewardResult:
        """
        Compute step-level reward based on immediate action outcomes.
        
        Args:
            observation: The observation before the action
            action: The action taken by the agent
            next_observation: The observation after the action
            step_info: Additional information about the step
            episode_history: Optional episode history (not typically used for step rewards)
            
        Returns:
            RewardResult with step-level reward
        """
        # TODO: Implement step-level reward computation
        # - Analyze action appropriateness
        # - Check for progress indicators
        # - Evaluate tool usage patterns
        # - Detect errors or failures
        
        reward = 0.0
        done = False
        info = {
            "reward_type": "step",
            "action_type": action.get("action_type", "unknown")
        }
        
        return RewardResult(reward=reward, done=done, info=info)
