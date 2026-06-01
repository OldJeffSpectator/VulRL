"""
Model Provider Registry for Inspect AI
注册自定义模型提供者
"""

from .lora_model_provider import cve_lora_provider

# 导出所有模型提供者
__all__ = ["cve_lora_provider"]
