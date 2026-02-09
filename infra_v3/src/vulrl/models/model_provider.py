# src/vulrl/models/model_provider.py
"""
LoRA Model Provider for Inspect AI integration.

Provides a model API adapter that allows LoRA-finetuned models to be used
within the Inspect AI evaluation framework.
"""

import os
import json
import re
import asyncio
from pathlib import Path
from typing import Any, Optional, List, Dict

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

from inspect_ai.model import (
    ModelAPI,
    ModelOutput,
    ChatMessage,
    ChatMessageUser,
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageTool,
    ContentText,
    ToolCall,
    ToolChoice,
    ToolInfo,
    GenerateConfig,
    modelapi,
    StopReason,
)


# Default base model
DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-3B-Instruct"


def convert_tools_to_qwen_format(tools: List[ToolInfo]) -> List[Dict]:
    """Convert Inspect ToolInfo to Qwen format."""
    qwen_tools = []
    for tool in tools:
        qwen_tool = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.parameters if tool.parameters else {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
        qwen_tools.append(qwen_tool)
    return qwen_tools


def convert_messages_to_qwen_format(messages: List[ChatMessage]) -> List[Dict]:
    """Convert Inspect ChatMessage to Qwen format."""
    qwen_messages = []

    for msg in messages:
        if isinstance(msg, ChatMessageSystem):
            qwen_messages.append({
                "role": "system",
                "content": msg.content if isinstance(msg.content, str) else str(msg.content)
            })
        elif isinstance(msg, ChatMessageUser):
            content = msg.content
            if isinstance(content, list):
                # Handle multimodal content
                text_parts = []
                for part in content:
                    if isinstance(part, ContentText):
                        text_parts.append(part.text)
                    elif isinstance(part, str):
                        text_parts.append(part)
                content = "\n".join(text_parts)
            qwen_messages.append({
                "role": "user",
                "content": content
            })
        elif isinstance(msg, ChatMessageAssistant):
            assistant_msg = {
                "role": "assistant",
                "content": msg.content if isinstance(msg.content, str) else ""
            }
            # Add tool calls
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function,
                            "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else tc.arguments
                        }
                    }
                    for tc in msg.tool_calls
                ]
            qwen_messages.append(assistant_msg)
        elif isinstance(msg, ChatMessageTool):
            qwen_messages.append({
                "role": "tool",
                "content": msg.content if isinstance(msg.content, str) else str(msg.content),
                "tool_call_id": msg.tool_call_id
            })

    return qwen_messages


class LoRAModelProvider(ModelAPI):
    """
    LoRA Model Provider for Inspect AI.
    
    Loads a LoRA-finetuned model and provides inference capabilities
    compatible with the Inspect AI framework.
    """

    def __init__(
        self,
        model_name: str,
        base_model: str,
        config: GenerateConfig = GenerateConfig(),
        **model_kwargs: Any
    ):
        super().__init__(model_name, base_model, config, **model_kwargs)

        self.checkpoint_path = model_kwargs.get("checkpoint_path")
        if not self.checkpoint_path:
            raise ValueError("checkpoint_path must be provided")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[LoRAModelProvider] Using device: {self.device}")
        print(f"[LoRAModelProvider] Loading base model: {base_model}")
        print(f"[LoRAModelProvider] Loading LoRA checkpoint: {self.checkpoint_path}")

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            base_model,
            trust_remote_code=True,
            padding_side="left"
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Load base model
        self.model = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            device_map="auto" if self.device == "cuda" else None,
            trust_remote_code=True
        )

        # Load LoRA weights
        print(f"[LoRAModelProvider] Loading LoRA adapter...")
        self.model = PeftModel.from_pretrained(
            self.model,
            self.checkpoint_path,
            is_trainable=False
        )
        self.model.eval()

        print(f"[LoRAModelProvider] Model loaded successfully")

    async def generate(
        self,
        input: List[ChatMessage],
        tools: List[ToolInfo],
        tool_choice: ToolChoice,
        config: GenerateConfig
    ) -> ModelOutput:
        """
        Generate a response using the LoRA model.
        
        Args:
            input: List of chat messages
            tools: Available tools for the model
            tool_choice: Tool selection strategy
            config: Generation configuration
            
        Returns:
            ModelOutput containing the generated response
        """
        # Convert messages and tools to Qwen format
        qwen_messages = convert_messages_to_qwen_format(input)
        qwen_tools = convert_tools_to_qwen_format(tools) if tools else None

        # Apply chat template
        if qwen_tools:
            text = self.tokenizer.apply_chat_template(
                qwen_messages,
                tools=qwen_tools,
                tokenize=False,
                add_generation_prompt=True
            )
        else:
            text = self.tokenizer.apply_chat_template(
                qwen_messages,
                tokenize=False,
                add_generation_prompt=True
            )

        # Tokenize
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=config.max_tokens or 4096
        ).to(self.device)

        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=config.max_tokens or 2048,
                temperature=config.temperature or 0.7,
                top_p=config.top_p or 0.9,
                do_sample=True,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id
            )

        # Decode response
        response_ids = outputs[0][inputs.input_ids.shape[1]:]
        response_text = self.tokenizer.decode(response_ids, skip_special_tokens=True)

        # Parse tool calls if present
        tool_calls = self._extract_tool_calls(response_text)

        # Construct ModelOutput
        if tool_calls:
            message = ChatMessageAssistant(
                content="",
                tool_calls=tool_calls
            )
            stop_reason = StopReason.TOOL_CALL
        else:
            message = ChatMessageAssistant(content=response_text)
            stop_reason = StopReason.STOP

        return ModelOutput(
            model=self.model_name,
            choices=[message],
            stop_reason=stop_reason,
            usage=None  # TODO: Implement token usage tracking
        )

    def _extract_tool_calls(self, response: str) -> List[ToolCall]:
        """
        Extract tool calls from model response.
        
        Args:
            response: Raw response text from the model
            
        Returns:
            List of extracted ToolCall objects
        """
        tool_calls = []

        # Pattern for Qwen tool call format: ✿FUNCTION✿
        pattern = r'✿([^✿]+)✿'
        matches = re.finditer(pattern, response)

        for i, match in enumerate(matches):
            try:
                call_str = match.group(1)
                call_json = json.loads(call_str)

                tool_call = ToolCall(
                    id=f"call_{i}",
                    function=call_json.get("name", ""),
                    arguments=call_json.get("arguments", {}),
                    type="function"
                )
                tool_calls.append(tool_call)
            except Exception as e:
                print(f"[LoRAModelProvider] Error parsing tool call: {e}")
                continue

        return tool_calls


def create_lora_model(
    checkpoint_path: str,
    base_model: str = DEFAULT_BASE_MODEL,
    model_name: str = "cve_lora"
) -> LoRAModelProvider:
    """
    Factory function to create a LoRA model provider.
    
    Args:
        checkpoint_path: Path to the LoRA checkpoint directory
        base_model: Base model identifier
        model_name: Name for the model provider
        
    Returns:
        Configured LoRAModelProvider instance
    """
    return LoRAModelProvider(
        model_name=model_name,
        base_model=base_model,
        checkpoint_path=checkpoint_path
    )
