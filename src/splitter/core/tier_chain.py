"""Tier chain orchestrator.

三级降级链：
- Tier 1: LLM 语义分句（可选，未实现时跳过）
- Tier 2: 语义分句（jieba / spaCy 等）
- Tier 3: 规则分句（永远可用）

每个分句器实现 is_available()，不可用时自动跳到下一级。
"""

from __future__ import annotations
from typing import List, Optional

from .base_splitter import BaseSentenceSplitter
from ..models import SentenceBlock


class TierChain:
    """分句器降级链。"""

    def __init__(self, splitters: List[BaseSentenceSplitter], min_tier: int = 2):
        """
        Args:
            splitters: 分句器列表，按优先级排序 [tier1, tier2, tier3]
            min_tier: 最低允许的 tier（1=LLM, 2=Semantic, 3=Rule）
        """
        self.splitters = splitters
        self.min_tier = min_tier  # 1/2/3

    def split(self, text: str) -> tuple[List[SentenceBlock], str]:
        """执行降级链，返回 (分句结果, 实际使用的 tier 名称)。"""
        last_error: Optional[Exception] = None

        for splitter in self.splitters:
            tier_num = self._parse_tier_num(splitter.tier)
            if tier_num < self.min_tier:
                continue  # 用户禁止使用比 min_tier 更精细的 tier
            if not splitter.is_available():
                continue
            try:
                result = splitter.split(text)
                if self._is_valid(result):
                    return result, splitter.tier
            except Exception as e:
                last_error = e
                continue

        # 所有 tier 都失败或不可用，最后一个兜底
        if self.splitters:
            result = self.splitters[-1].split(text)
            return result, f"{self.splitters[-1].tier}_fallback"
        raise RuntimeError("No splitters configured") from last_error

    @staticmethod
    def _parse_tier_num(tier: str) -> int:
        """从 tier 名称提取数字。tier1_llm → 1, tier3_rule → 3"""
        try:
            return int(tier.split("_")[0].replace("tier", ""))
        except (ValueError, IndexError):
            return 99  # 未知 tier 放最后

    @staticmethod
    def _is_valid(result: List[SentenceBlock]) -> bool:
        """验证分句结果合理性。"""
        if not result:
            return False
        avg_len = sum(len(s.text) for s in result) / len(result)
        return 1 < avg_len < 1000
