# src/vulrl/reward/__init__.py
"""
Reward computation module for VulRL.

Provides a hierarchical reward system with multiple layers:
- Step-level rewards (immediate feedback)
- Trajectory-level rewards (episode-based evaluation)
- Visual rewards (screenshot-based assessment)
- Composite rewards (orchestrated multi-layer rewards)
"""

from .base_reward import BaseReward, RewardResult
from .step_reward import StepReward
from .trajectory_reward import TrajectoryReward
from .visual_reward import VisualReward
from .composite_reward import CompositeReward

__all__ = [
    "BaseReward",
    "RewardResult",
    "StepReward",
    "TrajectoryReward",
    "VisualReward",
    "CompositeReward",
]
