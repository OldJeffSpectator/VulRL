# src/vulrl/config/env_config.py
"""
Environment configuration management.

Defines configuration structures for different environment types
(Vulhub, CVE-bench, Xbow) and provides utilities for creating
and validating environment configurations.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
from pathlib import Path


@dataclass
class EnvConfig:
    """
    Environment configuration for VulRL.
    
    Attributes:
        task_id: Unique identifier for the task
        task_type: Type of environment (vulhub, cvebench, xbow)
        max_steps: Maximum number of steps per episode
        timeout: Timeout for individual actions (seconds)
        target_host: Target service hostname
        target_port: Target service port
        target_protocol: Target service protocol (http, https)
        backend_config: Backend-specific configuration
    """
    task_id: str
    task_type: str
    max_steps: int = 30
    timeout: int = 30
    target_host: str = "target"
    target_port: int = 80
    target_protocol: str = "http"
    backend_config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvConfig":
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
        if not self.task_id:
            raise ValueError("task_id is required")
        
        if not self.task_type:
            raise ValueError("task_type is required")
        
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        
        return True


def create_env_config(
    task_id: str,
    task_type: str,
    **kwargs
) -> EnvConfig:
    """
    Factory function to create environment configuration.
    
    Args:
        task_id: Unique identifier for the task
        task_type: Type of environment (vulhub, cvebench, xbow)
        **kwargs: Additional configuration parameters
        
    Returns:
        Configured EnvConfig instance
    """
    config = EnvConfig(
        task_id=task_id,
        task_type=task_type,
        **kwargs
    )
    config.validate()
    return config


def create_vulhub_config(
    task_id: str,
    vulhub_path: str,
    **kwargs
) -> EnvConfig:
    """
    Create configuration for Vulhub environment.
    
    Args:
        task_id: Unique identifier for the task
        vulhub_path: Path to Vulhub challenge directory
        **kwargs: Additional configuration parameters
        
    Returns:
        Configured EnvConfig for Vulhub
    """
    backend_config = {
        "vulhub_path": vulhub_path
    }
    backend_config.update(kwargs.pop("backend_config", {}))
    
    return create_env_config(
        task_id=task_id,
        task_type="vulhub",
        backend_config=backend_config,
        **kwargs
    )


def create_cvebench_config(
    task_id: str,
    compose_path: str,
    eval_config_path: str,
    **kwargs
) -> EnvConfig:
    """
    Create configuration for CVE-bench environment.
    
    Args:
        task_id: Unique identifier for the task
        compose_path: Path to docker-compose.yml
        eval_config_path: Path to evaluation config YAML
        **kwargs: Additional configuration parameters
        
    Returns:
        Configured EnvConfig for CVE-bench
    """
    backend_config = {
        "compose_path": compose_path,
        "eval_config_path": eval_config_path
    }
    backend_config.update(kwargs.pop("backend_config", {}))
    
    return create_env_config(
        task_id=task_id,
        task_type="cvebench",
        backend_config=backend_config,
        **kwargs
    )


def create_xbow_config(
    task_id: str,
    compose_path: str,
    benchmark_id: str,
    **kwargs
) -> EnvConfig:
    """
    Create configuration for Xbow environment.
    
    Args:
        task_id: Unique identifier for the task
        compose_path: Path to docker-compose.yml
        benchmark_id: Xbow benchmark identifier
        **kwargs: Additional configuration parameters
        
    Returns:
        Configured EnvConfig for Xbow
    """
    backend_config = {
        "compose_path": compose_path,
        "benchmark_id": benchmark_id
    }
    backend_config.update(kwargs.pop("backend_config", {}))
    
    return create_env_config(
        task_id=task_id,
        task_type="xbow",
        backend_config=backend_config,
        **kwargs
    )
