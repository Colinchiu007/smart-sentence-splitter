"""LLM Provider 抽象基类。"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class LLMProvider(ABC):
    """LLM Provider 抽象基类。

    统一的 chat 接口，所有 provider 都实现：
    - is_available(): 检查 API key / 服务端点
    - chat(messages, **kwargs): 发送 chat 请求，返回文本
    """

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """检查 provider 是否可用（API key / 服务端点）。"""
        raise NotImplementedError

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """调用 LLM chat API，返回文本响应。"""
        raise NotImplementedError

    @property
    @abstractmethod
    def model(self) -> str:
        """当前模型名。"""
        raise NotImplementedError
