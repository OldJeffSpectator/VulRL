# src/vulrl/config/reward_config.py
"""
Reward configuration management.

Defines configuration structures for the multi-layer reward system,
including weights, LLM settings, and component-specific parameters.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional


@dataclass
class RewardConfig:
    """
    Reward configuration for VulRL.
    
    Attributes:
        # Reward weights
        step_weight: Weight for step-level rewards
        trajectory_weight: Weight for trajectory-level rewards
        visual_weight: Weight for visual rewards
        
        # Component enablement
        enable_step_reward: Enable step-level rewards
        enable_trajectory_reward: Enable trajectory-level rewards
        enable_visual_reward: Enable visual rewards
        
        # LLM settings for reward computation
        step_llm_model: LLM model for step evaluation
        trajectory_llm_model: LLM model for trajectory evaluation
        visual_llm_model: LLM model for visual evaluation
        
        # API keys and endpoints
        openai_api_key: OpenAI API key
        openai_base_url: OpenAI API base URL
        
        # Component-specific configs
        step_reward_config: Configuration for step rewards
        trajectory_reward_config: Configuration for trajectory rewards
        visual_reward_config: Configuration for visual rewards
    """
    # Reward weights
    step_weight: float = 0.3
    trajectory_weight: float = 0.4
    visual_weight: float = 0.3
    
    # Component enablement
    enable_step_reward: bool = True
    enable_trajectory_reward: bool = True
    enable_visual_reward: bool = True
    
    # LLM settings
    step_llm_model: str = "gpt-4o-mini"
    trajectory_llm_model: str = "gpt-4o"
    visual_llm_model: str = "gpt-4o"
    
    # API settings
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    
    # Component-specific configs
    step_reward_config: Dict[str, Any] = field(default_factory=dict)
    trajectory_reward_config: Dict[str, Any] = field(default_factory=dict)
    visual_reward_config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RewardConfig":
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
        # Validate weights
        if self.step_weight < 0 or self.trajectory_weight < 0 or self.visual_weight < 0:
            raise ValueError("Reward weights must be non-negative")
        
        total_weight = self.step_weight + self.trajectory_weight + self.visual_weight
        if total_weight <= 0:
            raise ValueError("At least one reward weight must be positive")
        
        # Validate LLM models
        if self.enable_step_reward and not self.step_llm_model:
            raise ValueError("step_llm_model is required when step rewards are enabled")
        
        if self.enable_trajectory_reward and not self.trajectory_llm_model:
            raise ValueError("trajectory_llm_model is required when trajectory rewards are enabled")
        
        if self.enable_visual_reward and not self.visual_llm_model:
            raise ValueError("visual_llm_model is required when visual rewards are enabled")
        
        return True


def create_reward_config(**kwargs) -> RewardConfig:
    """
    Factory function to create reward configuration.
    
    Args:
        **kwargs: Configuration parameters
        
    Returns:
        Configured RewardConfig instance
    """
    config = RewardConfig(**kwargs)
    config.validate()
    return config
