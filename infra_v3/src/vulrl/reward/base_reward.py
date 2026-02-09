# src/vulrl/reward/base_reward.py
"""
Abstract base class for all reward functions in VulRL.

Defines the universal interface that all reward implementations must follow.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class RewardResult:
    """
    Standardized reward computation result.
    
    Attributes:
        reward: The numerical reward value
        done: Whether the episode should terminate
        info: Additional information about the reward computation
    """
    reward: float
    done: bool
    info: Dict[str, Any]


class BaseReward(ABC):
    """
    Abstract base class for all reward functions.
    
    All reward implementations must inherit from this class and implement
    the compute() method with the standardized signature.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the reward function with configuration.
        
        Args:
            config: Configuration dictionary containing reward-specific parameters
        """
        self.config = config
    
    @abstractmethod
    def compute(
        self,
        observation: str,
        action: Dict[str, Any],
        next_observation: str,
        step_info: Dict[str, Any],
        episode_history: Optional[List[Dict[str, Any]]] = None
    ) -> RewardResult:
        """
        Universal entry point for reward computation.
        
        Args:
            observation: The observation before the action
            action: The action taken by the agent
            next_observation: The observation after the action
            step_info: Additional information about the step
            episode_history: Optional history of the episode for trajectory-based rewards
            
        Returns:
            RewardResult containing reward value, termination flag, and additional info
        """
        pass
    
    def reset(self) -> None:
        """
        Reset the reward function state (if stateful).
        Called at the beginning of each episode.
        """
        pass
    
    def cleanup(self) -> None:
        """
        Cleanup resources used by the reward function.
        Called when the reward function is no longer needed.
        """
        pass
