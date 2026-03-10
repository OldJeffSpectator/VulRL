"""LLM HTTP client for worker units."""

import aiohttp
from typing import List, Dict, Any


class LLMClient:
    """HTTP client for LLM inference."""
    
    def __init__(self, endpoint: str, model_name: str):
        """Initialize LLM client.
        
        Args:
            endpoint: LLM server endpoint (e.g., http://127.0.0.1:8001)
            model_name: Model name
        """
        self.endpoint = endpoint
        self.model_name = model_name
    
    async def query(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> str:
        """Query LLM for completion.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Max tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Generated text
        """
        url = f"{self.endpoint}/v1/chat/completions"
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                return result["choices"][0]["message"]["content"]
