"""Abstract sentence splitter interface."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List
from ..models import SentenceBlock


class BaseSentenceSplitter(ABC):
    """分句器抽象接口。

    所有分句器（规则/语义/LLM）都实现此接口。
    """

    language: str = "zh"  # 子类覆盖
    tier: str = "tier3_rule"  # 子类覆盖
    priority: int = 100  # 数字越小越优先

    @abstractmethod
    def split(self, text: str) -> List[SentenceBlock]:
        """将文本分割为句子列表。

        Args:
            text: 输入文本

        Returns:
            SentenceBlock 列表
        """
        raise NotImplementedError

    def is_available(self) -> bool:
        """分句器是否可用（依赖是否安装、API 是否可达等）。"""
        return True

    def _make_block(self, text: str, index: int, **kwargs) -> SentenceBlock:
        """构造一个 SentenceBlock，自动设置 tier 和 language。"""
        text = text.strip()
        if not text:
            return None
        return SentenceBlock(
            text=text,
            index=index,
            tier=self.tier,
            language=self.language,
            **kwargs,
        )
