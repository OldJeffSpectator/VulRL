# src/vulrl/models/model_registry.py
"""
Model registry for integrating custom models with Inspect AI.

Provides utilities for registering LoRA models and other custom model providers
with the Inspect AI framework.
"""

from typing import Optional

from inspect_ai.model import modelapi

from .model_provider import LoRAModelProvider, DEFAULT_BASE_MODEL


@modelapi(name="cve_lora")
def cve_lora_provider(
    checkpoint_path: Optional[str] = None,
    base_model: str = DEFAULT_BASE_MODEL,
    **kwargs
) -> LoRAModelProvider:
    """
    Inspect AI model provider for LoRA-finetuned CVE models.
    
    Usage:
        inspect eval task.py --model=cve_lora -M checkpoint_path=/path/to/checkpoint
    
    Args:
        checkpoint_path: Path to the LoRA checkpoint directory (required)
        base_model: Base model identifier (default: Qwen/Qwen2.5-3B-Instruct)
        **kwargs: Additional model configuration parameters
        
    Returns:
        Configured LoRAModelProvider instance
    """
    if not checkpoint_path:
        raise ValueError(
            "checkpoint_path is required. Use: "
            "inspect eval --model=cve_lora -M checkpoint_path=/path/to/checkpoint"
        )
    
    return LoRAModelProvider(
        model_name="cve_lora",
        base_model=base_model,
        checkpoint_path=checkpoint_path,
        **kwargs
    )


def register_model_with_inspect(
    model_name: str,
    provider_func,
    **default_kwargs
):
    """
    Register a custom model provider with Inspect AI.
    
    Args:
        model_name: Name to register the model under
        provider_func: Function that returns a ModelAPI instance
        **default_kwargs: Default keyword arguments for the provider
    """
    # Wrap provider function with modelapi decorator
    wrapped_provider = modelapi(name=model_name)(provider_func)
    
    print(f"[ModelRegistry] Registered model provider: {model_name}")
    
    return wrapped_provider
