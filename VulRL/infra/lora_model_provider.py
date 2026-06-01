"""
LoRA Model Provider for Inspect AI
将训练好的 LoRA 模型注册为 Inspect AI 的模型提供者

用法:
    inspect eval task.py --model=cve_lora/model -M checkpoint_path=/path/to/checkpoint
"""

import os
import json
import re
import asyncio
from pathlib import Path
from typing import Any, Optional

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


# 默认基础模型
DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-3B-Instruct"


def convert_tools_to_qwen_format(tools: list[ToolInfo]) -> list[dict]:
    """将 Inspect 的 ToolInfo 转换为 Qwen 格式"""
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


def convert_messages_to_qwen_format(messages: list[ChatMessage]) -> list[dict]:
    """将 Inspect 的 ChatMessage 转换为 Qwen 格式"""
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
                # 处理多模态内容
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
            # 添加 tool calls
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
                "tool_call_id": msg.tool_call_id,
                "content": msg.content if isinstance(msg.content, str) else str(msg.content)
            })

    return qwen_messages


def parse_tool_calls_from_output(output: str) -> tuple[str, list[ToolCall]]:
    """从模型输出中解析 tool calls"""
    tool_calls = []

    # Qwen 使用特殊格式的 function call
    # 格式: <tool_call>{"name": "func", "arguments": {...}}</tool_call>
    tool_call_pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
    matches = re.findall(tool_call_pattern, output, re.DOTALL)

    for i, match in enumerate(matches):
        try:
            call_data = json.loads(match)
            tool_call = ToolCall(
                id=f"call_{i}",
                function=call_data.get("name", ""),
                arguments=call_data.get("arguments", {})
            )
            tool_calls.append(tool_call)
        except json.JSONDecodeError:
            continue

    # 另一种格式: 直接的 JSON function call
    if not tool_calls:
        # 尝试匹配 {"tool": "name", "arguments": {...}} 格式
        json_pattern = r'\{[^{}]*"(?:tool|name)"[^{}]*"(?:arguments|params)"[^{}]*\}'
        json_matches = re.findall(json_pattern, output, re.DOTALL)

        for i, match in enumerate(json_matches):
            try:
                call_data = json.loads(match)
                name = call_data.get("tool") or call_data.get("name", "")
                args = call_data.get("arguments") or call_data.get("params", {})
                if name:
                    tool_call = ToolCall(
                        id=f"call_{i}",
                        function=name,
                        arguments=args
                    )
                    tool_calls.append(tool_call)
            except json.JSONDecodeError:
                continue

    # 清理输出中的 tool call 标记
    clean_output = re.sub(tool_call_pattern, '', output).strip()

    return clean_output, tool_calls


class CVELoRAModelAPI(ModelAPI):
    """
    CVE LoRA 模型的 Inspect AI 接口

    使用方式:
        --model=cve_lora/model -M checkpoint_path=/path/to/checkpoint
    """

    def __init__(
        self,
        model_name: str,
        base_model: str = DEFAULT_BASE_MODEL,
        checkpoint_path: Optional[str] = None,
        device: str = "auto",
        torch_dtype: str = "bfloat16",
        max_new_tokens: int = 2048,
        **model_args
    ):
        super().__init__(model_name, **model_args)

        self.base_model_name = base_model
        self.checkpoint_path = checkpoint_path
        self.device = device
        self.max_new_tokens = max_new_tokens

        # 设置 torch dtype
        dtype_map = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }
        self.torch_dtype = dtype_map.get(torch_dtype, torch.bfloat16)

        # 加载模型和 tokenizer
        self.model = None
        self.tokenizer = None
        self._load_model()

    def _load_model(self):
        """加载基础模型和 LoRA 权重"""
        print(f"Loading base model: {self.base_model_name}")

        # 加载 tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.base_model_name,
            trust_remote_code=True
        )

        # 确保有 pad token
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # 加载基础模型
        self.model = AutoModelForCausalLM.from_pretrained(
            self.base_model_name,
            torch_dtype=self.torch_dtype,
            device_map=self.device,
            trust_remote_code=True
        )

        # 加载 LoRA 权重
        if self.checkpoint_path:
            lora_path = Path(self.checkpoint_path)

            # 检查是否是完整路径还是 checkpoint 目录
            if (lora_path / "policy").exists():
                lora_path = lora_path / "policy"

            if lora_path.exists():
                print(f"Loading LoRA weights from: {lora_path}")
                self.model = PeftModel.from_pretrained(
                    self.model,
                    str(lora_path),
                    torch_dtype=self.torch_dtype
                )
                # 可选: 合并权重以提高推理速度
                # self.model = self.model.merge_and_unload()
                print("LoRA weights loaded successfully")
            else:
                print(f"Warning: LoRA path not found: {lora_path}")

        self.model.eval()

    async def generate(
        self,
        input: list[ChatMessage],
        tools: list[ToolInfo],
        tool_choice: ToolChoice,
        config: GenerateConfig,
    ) -> ModelOutput:
        """生成响应"""

        # 转换消息格式
        messages = convert_messages_to_qwen_format(input)

        # 转换工具格式
        qwen_tools = convert_tools_to_qwen_format(tools) if tools else None

        # 使用 tokenizer 的 apply_chat_template
        if qwen_tools:
            text = self.tokenizer.apply_chat_template(
                messages,
                tools=qwen_tools,
                add_generation_prompt=True,
                tokenize=False
            )
        else:
            text = self.tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=False
            )

        # Tokenize
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)

        # 生成参数
        max_tokens = config.max_tokens or self.max_new_tokens
        temperature = config.temperature if config.temperature is not None else 0.7
        top_p = config.top_p if config.top_p is not None else 0.9

        # 使用 asyncio 在线程池中运行生成
        loop = asyncio.get_event_loop()

        def _generate():
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature if temperature > 0 else None,
                    top_p=top_p if temperature > 0 else None,
                    do_sample=temperature > 0,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            return outputs

        outputs = await loop.run_in_executor(None, _generate)

        # 解码输出
        generated_ids = outputs[0][inputs.input_ids.shape[1]:]
        response_text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)

        # 解析 tool calls
        content, tool_calls = parse_tool_calls_from_output(response_text)

        # 确定停止原因
        stop_reason = StopReason.STOP
        if tool_calls:
            stop_reason = StopReason.TOOL_CALLS
        elif len(generated_ids) >= max_tokens:
            stop_reason = StopReason.MAX_TOKENS

        # 构建响应
        return ModelOutput(
            model=self.model_name,
            choices=[
                ChatMessageAssistant(
                    content=content,
                    tool_calls=tool_calls if tool_calls else None,
                )
            ],
            stop_reason=stop_reason,
        )

    @property
    def max_tokens(self) -> Optional[int]:
        """返回最大 token 数"""
        return self.max_new_tokens

    @property
    def max_connections(self) -> int:
        """最大并发连接数"""
        return 1  # 本地模型通常只支持单连接


@modelapi(name="cve_lora")
def cve_lora_provider():
    """注册 CVE LoRA 模型提供者"""
    return CVELoRAModelAPI
