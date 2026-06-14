"""Ollama Provider (本地 LLM，与 OpenAI 协议兼容)。"""

from __future__ import annotations
import os
from typing import List, Dict, Any, Optional


class OllamaProvider:
    """Ollama 本地 LLM Provider（OpenAI 协议兼容）。"""

    name = "ollama"
    DEFAULT_BASE = "http://localhost:11434/v1"

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: Optional[str] = None,
        timeout: int = 60,
    ):
        self._model = model
        self.base_url = base_url or self.DEFAULT_BASE
        self.timeout = timeout
        self._client = None

    @property
    def model(self) -> str:
        return self._model

    def is_available(self) -> bool:
        """检查 Ollama 服务是否在运行（/api/tags 端点）。"""
        try:
            import requests
            resp = requests.get(self.base_url.replace("/v1", "") + "/api/tags", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key="ollama",  # Ollama 不需要 key，但 SDK 要求非空
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        client = self._get_client()
        resp = client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=kwargs.get("temperature", 0.0),
            max_tokens=kwargs.get("max_tokens", 4096),
        )
        return resp.choices[0].message.content
