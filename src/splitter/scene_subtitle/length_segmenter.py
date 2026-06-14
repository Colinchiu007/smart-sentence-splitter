"""LengthSegmenter — 字数控制策略（v0.6 新增）.

3 种策略:
- "off"  透传
- "A"    重切（按字数，3-15 字/块），用优先级标点贪心切
- "B"    标尺（不切，标 ok/too_short/too_long 状态）

设计要点:
- 默认 B 模式 — 兼容 v0.5.1 现有行为
- A 模式在 tier 链分句后、scene segmenter 前调用
- A 模式保留原始 language / tier 信息
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any
import logging
import copy

from ..models import SentenceBlock


logger = logging.getLogger(__name__)


# 优先级标点（中文在前，英文在后）
# 选最近的 < max_chars 的标点切
PRIORITY_PUNCTUATION = [
    "。", "！", "？", "；",  # 强分隔（句末）
    "，", "、",                  # 弱分隔（句内）
    ".", "!", "?", ";",        # 英文强分隔
    ",", ":", ";",                # 英文弱分隔
]


class LengthSegmenter:
    """字数控制分句器。

    Args:
        strategy: "off" | "A" | "B" (默认 B)
        min_chars: 最小字数
        max_chars: 最大字数
        prefer_punctuation: A 模式时优先标点切（默认 True）
        warning_on_violation: B 模式时记录警告
    """

    VALID_STRATEGIES = ("off", "A", "B")

    def __init__(
        self,
        strategy: str = "B",
        min_chars: int = 3,
        max_chars: int = 15,
        prefer_punctuation: bool = True,
        warning_on_violation: bool = True,
        priority_punctuation: Optional[List[str]] = None,
    ):
        if strategy not in self.VALID_STRATEGIES:
            raise ValueError(
                f"Invalid strategy: {strategy!r}. "
                f"Must be one of {self.VALID_STRATEGIES}"
            )
        if min_chars >= max_chars:
            raise ValueError(
                f"min_chars ({min_chars}) must be < max_chars ({max_chars})"
            )
        if min_chars < 1:
            raise ValueError(f"min_chars must be >= 1, got {min_chars}")

        self.strategy = strategy
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.prefer_punctuation = prefer_punctuation
        self.warning_on_violation = warning_on_violation
        self.priority_punctuation = priority_punctuation or PRIORITY_PUNCTUATION
        self.warnings: List[str] = []

    def segment(
        self, sentences: List[SentenceBlock]
    ) -> List[SentenceBlock]:
        """应用字数控制策略。

        Args:
            sentences: 输入句子列表

        Returns:
            按策略处理后的句子列表（B 模式原样，A 模式重切）
        """
        if self.strategy == "off":
            return self._passthrough(sentences)
        if self.strategy == "B":
            return self._apply_b(sentences)
        if self.strategy == "A":
            return self._apply_a(sentences)
        # 默认透传
        return self._passthrough(sentences)

    # ===== Strategy: off =====
    def _passthrough(
        self, sentences: List[SentenceBlock]
    ) -> List[SentenceBlock]:
        """off 策略：原样返回，只标记 status=ok 和 applied=none。"""
        out = []
        for s in sentences:
            if not s.text or not s.text.strip():
                continue
            new = copy.copy(s)
            new.length_status = "ok"
            new.length_strategy_applied = "none"
            out.append(new)
        return out

    # ===== Strategy: B (标尺) =====
    def _apply_b(
        self, sentences: List[SentenceBlock]
    ) -> List[SentenceBlock]:
        """B 策略：不切，只标 length_status。"""
        self.warnings = []  # 重置
        out = []
        for s in sentences:
            if not s.text or not s.text.strip():
                continue
            new = copy.copy(s)
            new.length_strategy_applied = "B"
            new.length_status = self._classify_length(s.text)
            if new.length_status != "ok" and self.warning_on_violation:
                self.warnings.append(
                    f"[B] Sentence {s.index} length={len(s.text)} "
                    f"status={new.length_status}: {s.text[:30]}..."
                )
            out.append(new)
        return out

    def _classify_length(self, text: str) -> str:
        """根据字数分类。"""
        n = len(text)
        if n < self.min_chars:
            return "too_short"
        if n > self.max_chars:
            return "too_long"
        return "ok"

    # ===== Strategy: A (重切) =====
    def _apply_a(
        self, sentences: List[SentenceBlock]
    ) -> List[SentenceBlock]:
        """A 策略：按字数 + 标点优先级重切。"""
        out = []
        for s in sentences:
            if not s.text or not s.text.strip():
                continue
            chunks = self._resplit(s.text)
            for i, chunk in enumerate(chunks):
                if not chunk or not chunk.strip():
                    continue
                # 保留原始 metadata (tier / language / is_topic_boundary)
                new = SentenceBlock(
                    text=chunk,
                    index=len(out),  # 全局新序号
                    tier=s.tier,
                    language=s.language,
                    words=[],
                    pos_tags=[],
                    confidence=s.confidence,
                    is_topic_boundary=s.is_topic_boundary,
                    topic_depth_score=s.topic_depth_score,
                    length_status=self._classify_length(chunk),
                    length_strategy_applied="A",
                )
                out.append(new)
        return out

    def _resplit(self, text: str) -> List[str]:
        """对单个长文本按字数 + 标点优先级重切。"""
        if len(text) <= self.max_chars:
            return [text]

        chunks: List[str] = []
        remaining = text

        while len(remaining) > self.max_chars:
            # 1. 在 max_chars 范围内找最右边的标点（贪心）
            head = remaining[:self.max_chars]
            split_at = self._find_split_position(head)

            if split_at > 0:
                # 找到了标点位置 — 在标点处切
                chunks.append(remaining[:split_at + 1])  # 含标点
                remaining = remaining[split_at + 1:]
            else:
                # 没找到标点 — 强制按 max_chars 切
                chunks.append(remaining[:self.max_chars])
                remaining = remaining[self.max_chars:]

        if remaining:
            chunks.append(remaining)

        return chunks

    def _find_split_position(self, head: str) -> int:
        """在 head 范围内找最合适的切分点。

        策略: 优先级标点表（从高到低），找每个标点的最右出现位置。

        Returns:
            切分点 index (含标点), 0 表示没找到
        """
        if not self.prefer_punctuation:
            # 不优先标点 — 强制按 max_chars-1 切
            return self.max_chars - 1

        for punct in self.priority_punctuation:
            # 找最右的标点（不超 max_chars 范围）
            pos = head.rfind(punct)
            if pos > 0:
                return pos
        return 0
