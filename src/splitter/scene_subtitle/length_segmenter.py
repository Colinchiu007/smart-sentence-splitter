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
    "。",
    "！",
    "？",
    "；",  # 强分隔（句末）
    "》",
    "」",
    "）",
    "]",
    "】",
    "}",  # 配对符号右边界 (可作切分点)
    "，",
    "、",  # 弱分隔（句内）
    ".",
    "!",
    "?",
    ";",  # 英文强分隔
    ",",
    ":",
    ";",  # 英文弱分隔
]

# 常见量词（用于语义保护，避免在数词+量词之间切分）
_CLASSIFIERS = frozenset(
    "封艘把件张支根块瓶碗杯条座架辆匹头只朵棵株亩石斗升斤担篇本页则条款扇面幅幅道顿阵回场遍次趟回番种般般"
)

# 配对引号/括号 — 切分时跳过这些字符避免断在引号中间
PAIRED_QUOTES = [
    ("《", "》"),
    ("「", "」"),
    ("『", "』"),
    ("(", ")"),
    ("（", "）"),
    ("[", "]"),
    ("【", "】"),
    ("{", "}"),
    ('"', '"'),
    ("'", "'"),
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
            raise ValueError(f"Invalid strategy: {strategy!r}. Must be one of {self.VALID_STRATEGIES}")
        if min_chars >= max_chars:
            raise ValueError(f"min_chars ({min_chars}) must be < max_chars ({max_chars})")
        if min_chars < 1:
            raise ValueError(f"min_chars must be >= 1, got {min_chars}")

        self.strategy = strategy
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.prefer_punctuation = prefer_punctuation
        self.warning_on_violation = warning_on_violation
        self.priority_punctuation = priority_punctuation or PRIORITY_PUNCTUATION
        self.warnings: List[str] = []

    def split_text(self, text: str) -> List[str]:
        """公开接口: 按字数 + 标点优先级 + 配对引号保护切分文本。

        Args:
            text: 要切分的文本

        Returns:
            切分后的文本块列表 (strategy=A 时重切, B/off 时返回 [text])
        """
        if self.strategy == "off":
            return [text] if text else []
        if self.strategy == "B":
            return [text] if text else []
        return self._resplit(text)

    def segment(self, sentences: List[SentenceBlock]) -> List[SentenceBlock]:
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
    def _passthrough(self, sentences: List[SentenceBlock]) -> List[SentenceBlock]:
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
    def _apply_b(self, sentences: List[SentenceBlock]) -> List[SentenceBlock]:
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
                    f"[B] Sentence {s.index} length={len(s.text)} status={new.length_status}: {s.text[:30]}..."
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
    def _apply_a(self, sentences: List[SentenceBlock]) -> List[SentenceBlock]:
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
        """对单个长文本按字数 + 标点优先级重切。

        v0.10.1 改进:
        1. 找不到标点时扩大搜索范围（向后延伸到 max_chars * 2），避免硬切在词中间
        2. 切分后校验：下一块以标点开头时，将标点移入上一块
        3. 删除了旧版 unreachable code
        """
        if len(text) <= self.max_chars:
            return [text]

        chunks: List[str] = []
        remaining = text

        while len(remaining) > self.max_chars:
            head = remaining[: self.max_chars]
            split_at = self._find_split_position(head)

            if split_at > 0:
                # 找到了标点位置 — 在标点处切
                chunks.append(remaining[: split_at + 1])
                remaining = remaining[split_at + 1 :]
            else:
                # 找不到标点 — 检查是否截断了配对引号
                pair_split = self._try_paired_quote_split(remaining)
                if pair_split is not None:
                    cut_at, head_len = pair_split
                    chunks.append(remaining[: cut_at + head_len])
                    remaining = remaining[cut_at + head_len :]
                else:
                    # v0.10.1: 扩大搜索范围 — 从 max_chars 向后找下一个优先级标点
                    extended_cut = self._find_extended_split(remaining)
                    if extended_cut is not None:
                        chunks.append(remaining[: extended_cut + 1])
                        remaining = remaining[extended_cut + 1 :]
                    else:
                        # v0.10.1: 语义保护 — 避免在数词+量词之间硬切
                        cut_pos = self.max_chars
                        cut_pos = self._adjust_for_semantic(remaining, cut_pos)
                        chunks.append(remaining[:cut_pos])
                        remaining = remaining[cut_pos:]

        if remaining:
            # 短尾合并：剩余 < min_chars 时合并到上一块，避免孤立断词
            # v0.12.0: 跨句不合并 — 如果前一块末尾是句子终止标点\uff08。！？\uff09，
            # 不合并剩余文本到前一块，避免两句话显示在同一屏字幕上。
            _SENTENCE_END = frozenset("。！？")
            if chunks and len(remaining) < self.min_chars and chunks[-1] and chunks[-1][-1] not in _SENTENCE_END:
                chunks[-1] += remaining
            else:
                chunks.append(remaining)

        # v0.10.1: 切分后校验 — 下一块以标点开头时，将标点移入上一块
        chunks = self._fix_leading_punctuation(chunks)

        return chunks

    def _adjust_for_semantic(self, text: str, cut_pos: int) -> int:
        """v0.10.1: 语义保护 — 调整硬切位置，避免截断紧密语义结构。

        规则:
        - 如果 cut_pos 处切分会分离 数词+量词 (如 一/封)，向后移 1 位
        - 如果 cut_pos 处切分会分离 形容词+的 (如 美丽的/花)，向后移 1 位
        """
        if cut_pos >= len(text) or cut_pos < 1:
            return cut_pos

        prev_char = text[cut_pos - 1]  # 上一块末尾字符
        next_char = text[cut_pos]  # 下一块开头字符

        # 规则1: 数词 + 量词 — 如 "一/封" "三/艘" "两/只"
        if next_char in _CLASSIFIERS and prev_char in "一二两三三四五六七八九十两数几":
            # 向后移 1 位，把量词纳入上一块
            if cut_pos + 1 < len(text):
                return cut_pos + 1

        # 规则2: "的" + 名词 — 如 "美丽的/花" 不应在 "的" 后切
        if prev_char == "的" and cut_pos >= 2:
            # 不切在 "的" 后面，把 "的" 留给下一块（向前移 1 位）
            return cut_pos - 1

        return cut_pos

    def _find_extended_split(self, text: str) -> Optional[int]:
        """v0.10.1: 在 max_chars 之外搜索下一个优先级标点。

        从 max_chars 位置开始向后搜索（最多到 max_chars * 2），
        找到第一个优先级标点时返回其位置。
        允许块略超 max_chars，避免硬切在词中间。

        Returns:
            切分点 index (含标点)，或 None 表示没找到
        """
        search_limit = min(len(text), self.max_chars * 2)
        # 从 max_chars 位置开始向后搜索
        for i in range(self.max_chars, search_limit):
            if text[i] in self.priority_punctuation:
                return i
        return None

    @staticmethod
    def _fix_leading_punctuation(chunks: List[str]) -> List[str]:
        """v0.10.1: 切分后校验 — 如果下一块以标点开头，将标点移入上一块末尾。"""
        if len(chunks) < 2:
            return chunks
        LEADING_PUNCT = frozenset("，、。！？；.!?;")
        fixed = [chunks[0]]
        for b in chunks[1:]:
            if b and b[0] in LEADING_PUNCT:
                fixed[-1] = fixed[-1] + b[0]
                b = b[1:]
            if b:
                fixed.append(b)
        return fixed

    def _try_paired_quote_split(self, remaining: str) -> Optional[tuple]:
        """检查 remaining 中是否截断了配对引号, 返回 (cut_at, head_len) 或 None。

        逻辑: 在 head = remaining[:max_chars] 范围内, 找最右的"成对左边界" (《, 「, ( 等)
        如果该左边界在 head 之外找不到匹配的右边界 (即被截断),
        但在 remaining 整体能找到, 则将 (left, right) 整体作为 1 块切出。
        """
        head = remaining[: self.max_chars]
        for left, right in PAIRED_QUOTES:
            # 找 head 内的所有 left
            i = 0
            while i < len(head):
                l = head.find(left, i)
                if l < 0:
                    break
                # 检查 head 内是否有 right
                r_head = head.find(right, l + 1)
                if r_head >= 0:
                    # head 内有配对, 跳过
                    i = r_head + 1
                    continue
                # head 内没 right, 看 remaining 整体
                r_full = remaining.find(right, l + 1)
                if r_full < 0:
                    # remaining 也没 right, 跳过
                    i = l + 1
                    continue
                # 找到了完整配对, 计算是否能在 max_chars 内放下
                pair_len = r_full - l + 1
                if pair_len <= self.max_chars:
                    # 可以放下: 切为 (l 之前) + (left...right)
                    return (l, pair_len)
                # 配对太长, 试下一个 left
                i = l + 1
        return None

    def _find_split_position(self, head: str) -> int:
        """在 head 范围内找最合适的切分点。

        策略:
        1. 配对引号/括号 (《》, 「」, () 等): 仅当**配对**在 head 内时锁定
        2. 单边的左/右引号: 视为可切分点
        3. 在可切区域里, 按优先级标点表找最右的标点

        Returns:
            切分点 index (含标点), 0 表示没找到
        """
        if not self.prefer_punctuation:
            return self.max_chars - 1

        # 标记成对引号内的不可切区段
        locked = [False] * len(head)
        for left, right in PAIRED_QUOTES:
            i = 0
            while i < len(head):
                l = head.find(left, i)
                if l < 0:
                    break
                r = head.find(right, l + 1)
                # 只有**配对在 head 内**才锁定
                if r < 0 or r >= self.max_chars:
                    i = l + 1
                    continue
                for j in range(l, r + 1):
                    locked[j] = True
                i = r + 1

        # 在 unlocked 区域找最右的优先级标点
        best_pos = 0
        for punct in self.priority_punctuation:
            for pos in range(len(head) - 1, -1, -1):
                if locked[pos]:
                    continue
                if head[pos] == punct and pos < self.max_chars:
                    if pos > best_pos:
                        best_pos = pos
                    break
            if best_pos > 0:
                return best_pos
        return 0
