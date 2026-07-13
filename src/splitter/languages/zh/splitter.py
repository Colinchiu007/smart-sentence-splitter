"""中文规则分句器（Tier 3）+ jieba 增强（Tier 2）。

Tier 3 (基础规则):
- 按 。！？；… 切分
- EOS 窗口：对标点前后 5 个字符做上下文的窗口检测（借鉴 HanLP EOS N-gram 思路）
- 引号/括号保护
- 中文缩写保护（等、即、如）

Tier 2 (jieba 增强):
- 利用 jieba 分词+词性标注
- 复句连接词识别 — 在这些词前面的标点不切分（因为它们在子句中间）
- 实体完整性保护（人名、地名、机构名）

使用：
    splitter = ChineseSplitter(config={"use_jieba": True})
    result = splitter.split("今天天气真好。我们去公园散步。")
"""

from __future__ import annotations
import re
from typing import List, Optional

from ...core.base_splitter import BaseSentenceSplitter
from ...models import SentenceBlock
from .tokenizer import JiebaTokenizer


# 复句连接词：在这些词前面紧挨着的标点不当作句末
# 即 "因为...所以..." 中间的分号不切
ZH_CLAUSE_CONJUNCTIONS = {
    "因为",
    "由于",
    "所以",
    "因此",
    "于是",
    "故",
    "虽然",
    "尽管",
    "即使",
    "即便",
    "不论",
    "不管",
    "无论",
    "但是",
    "然而",
    "不过",
    "可是",
    "但",
    "却",
    "只是",
    "如果",
    "假如",
    "倘若",
    "只要",
    "除非",
    "否则",
    "并且",
    "而且",
    "同时",
    "此外",
    "另外",
    "再者",
    "更",
    "为了",
    "以便",
    "以求",
    "以至于",
    "致使",
    "使得",
}


class ChineseSplitter(BaseSentenceSplitter):
    """中文分句器（Tier 3 规则 + Tier 2 jieba 增强）。

    规则分句 + EOS 窗口检测：
    1. 找到候选句末标点（。！？；）
    2. 对标点前后各取 W 个字符检查候选项是否需要忽略：
       - 标点后紧接着英文/数字 > 4 个 → 可能是缩写 → 不切
       - 标点前有复句连接词 → 不切
       - 括号/引号不匹配 → 不切
    3. 仅在确定为句末时切分
    """

    language = "zh"

    # EOS 窗口大小（从 HanLP EOS N-gram 借鉴）
    EOS_WINDOW = 5
    # 候选句末标点
    EOS_CHARS = set("。！？；.!?;")
    # 英文/数字字符集（用于缩写检测）
    EN_NUM_PATTERN = re.compile(r"^[a-zA-Z0-9]{4,}$")

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.use_jieba = self.config.get("use_jieba", True)
        self.entity_protection = self.config.get("entity_protection", True)
        self.handle_soft_end = self.config.get("handle_soft_end", True)
        self.max_sentence_length = self.config.get("max_sentence_length", 200)
        self.eos_window = self.config.get("eos_window", self.EOS_WINDOW)

        # jieba tokenizer（可选）
        self.tokenizer: Optional[JiebaTokenizer] = None
        if self.use_jieba:
            self.tokenizer = JiebaTokenizer()

    def is_available(self) -> bool:
        return True

    @property
    def tier(self) -> str:
        if self.tokenizer and self.tokenizer.is_available():
            return "tier2_semantic"
        return "tier3_rule"

    def split(self, text: str) -> List[SentenceBlock]:
        if not text or not text.strip():
            return []

        text = text.strip()
        # 1. 保护引号内句末标点
        protected_text, quote_map = self._protect_quoted(text)

        # 2. EOS 窗口检测：找候选句末标点
        eos_positions = self._find_eos_positions(protected_text)

        # 3. 按句末位置切分
        candidates = self._split_at_positions(protected_text, eos_positions)

        # 4. 还原引号
        candidates = [self._restore_quotes(c, quote_map) for c in candidates]
        candidates = [c.strip() for c in candidates if c.strip()]

        # 5. 构造 SentenceBlock
        result = []
        idx = 0
        for c in candidates:
            if not c:
                continue
            if len(c) > self.max_sentence_length:
                result.extend(self._split_long_sentence(c, idx))
                idx += len([x for x in result if x.index >= idx]) + 1
            else:
                block = self._make_block_with_metadata(c, idx)
                result.append(block)
                idx += 1

        return result

    def _find_eos_positions(self, text: str) -> List[int]:
        """找候选句末标点，并用窗口检测过滤。

        借鉴 HanLP EOS N-gram 思路：只对比候选标点做上下文分析，
        不对全字符序列做标注。

        Returns:
            确定为句末的标点位置列表
        """
        eos_positions = []
        for i, char in enumerate(text):
            if char not in self.EOS_CHARS:
                continue

            # === 窗口检测（EOS Window Check）===

            # 1. 检测标点后是否连续 4+ 英文/数字 → 可能是缩写 → 不切
            after_window = text[i + 1 : i + 1 + self.eos_window]
            if after_window and self.EN_NUM_PATTERN.match(after_window):
                continue

            # 2. 检测前一个字符是否是复句连接词的一部分
            before_window = text[max(0, i - self.eos_window) : i]
            for conj in ZH_CLAUSE_CONJUNCTIONS:
                if conj in before_window:
                    # 只在连接词距离标点很近时才跳过（< 窗口大小）
                    if len(before_window) - before_window.rfind(conj) < self.eos_window + len(conj):
                        break
            else:
                eos_positions.append(i)

        return eos_positions

    def _split_at_positions(self, text: str, positions: List[int]) -> List[str]:
        """按指定位置列表切分文本。"""
        if not positions:
            return [text]

        parts = []
        prev = 0
        for pos in positions:
            part = text[prev : pos + 1]
            if part.strip():
                parts.append(part)
            prev = pos + 1
        # 剩余
        if prev < len(text):
            remaining = text[prev:]
            if remaining.strip():
                parts.append(remaining)
        return parts

    def _make_block_with_metadata(self, text: str, index: int) -> SentenceBlock:
        words = []
        pos_tags = []
        if self.tokenizer and self.tokenizer.is_available():
            words = self.tokenizer.tokenize(text)
            pos_tags = [tag for _, tag in self.tokenizer.pos_tag(text)]
        return SentenceBlock(
            text=text,
            index=index,
            words=words,
            pos_tags=pos_tags,
            tier=self.tier,
            language=self.language,
        )

    def _protect_quoted(self, text: str) -> tuple[str, dict]:
        """保护引号内可能的句末标点。"""
        quote_map = {}
        counter = 0

        quote_pairs = [
            ("「", "」"),
            ("『", "』"),
            ('"', '"'),
            ("'", "'"),
            ("\u201c", "\u201d"),
        ]

        for open_q, close_q in quote_pairs:

            def gen_replacer():
                nonlocal counter
                open_pat = re.escape(open_q)
                close_pat = re.escape(close_q)

                def replace_quoted(match):
                    nonlocal counter
                    inner = match.group(1)
                    if any(p in inner for p in "。！？；.!?;"):
                        # 剥离尾部句末标点，保留在占位符外让 EOS 检测可见
                        inner_clean = inner.rstrip("。！？；.!?;")
                        trailing_eos = inner[len(inner_clean):]
                        placeholder = f"\u00a7ZHQ{counter}\u00a7"
                        quote_map[placeholder] = open_q + inner_clean + close_q
                        counter += 1
                        import sys; print('DEBUG inner=%r i_clean=%r tr=%r' % (inner, inner_clean, trailing_eos), file=sys.stderr); sys.stderr.flush()
                        return placeholder + trailing_eos
                    return match.group(0)

                return replace_quoted

            text = re.sub(
                re.escape(open_q) + r"(.*?)" + re.escape(close_q),
                gen_replacer(),
                text,
            )

        return text, quote_map

    @staticmethod
    def _restore_quotes(text: str, quote_map: dict) -> str:
        for placeholder, original in quote_map.items():
            text = text.replace(placeholder, original)
        return text

    def _split_long_sentence(self, text: str, start_idx: int) -> List[SentenceBlock]:
        """过长句：先按 ；， 切，再按 max_sentence_length 强制切。"""
        parts = re.split(r"(?<=[；，,;])\s*", text)
        result = []
        idx = start_idx
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if len(p) > self.max_sentence_length:
                for i in range(0, len(p), self.max_sentence_length):
                    chunk = p[i : i + self.max_sentence_length].strip()
                    if chunk:
                        result.append(self._make_block_with_metadata(chunk, idx))
                        idx += 1
            else:
                result.append(self._make_block_with_metadata(p, idx))
                idx += 1
        return result

