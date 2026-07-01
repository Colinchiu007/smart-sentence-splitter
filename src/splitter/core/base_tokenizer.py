"""Abstract tokenizer interface."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Tuple


class BaseTokenizer(ABC):
    """分词器抽象接口。"""

    language: str = "zh"

    @abstractmethod
    def tokenize(self, text: str) -> List[str]:
        """分词"""
        raise NotImplementedError

    def pos_tag(self, text: str) -> List[Tuple[str, str]]:
        """词性标注（默认不实现）"""
        return []
