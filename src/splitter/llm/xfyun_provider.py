"""Xfyun MAAS Provider（与 OpenAI 协议兼容）。"""

from __future__ import annotations
import os
from typing import List, Dict, Any, Optional


class XfyunProvider:
    """讯飞 MAAS API Provider（OpenAI 协议兼容）。"""

    name = "xfyun"
    DEFAULT_BASE = "https://maas-api.cn-huabei-1.xf-yun.com/v1"

    def __init__(
        self,
        model: str = "astron-code-latest",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
    ):
        self._model = model
        self.api_key = api_key or os.getenv("XFYUN_API_KEY")
        self.base_url = base_url or self.DEFAULT_BASE
        self.timeout = timeout
        self._client = None

    @property
    def model(self) -> str:
        return self._model

    def is_available(self) -> bool:
        return self.api_key is not None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.api_key,
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
