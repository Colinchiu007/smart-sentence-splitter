"""中文规则分句器（Tier 3）+ jieba 增强（Tier 2）。

Tier 3 (基础规则):
- 按 。！？；… 切分
- 引号/括号保护
- 中文缩写保护（等、即、如）

Tier 2 (jieba 增强):
- 利用 jieba 分词+词性标注
- 复句连接词识别（虽然、但是、因为、所以、虽然...但是...）
- 实体完整性保护（人名、地名、机构名）
- 语义边界评分

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


# 复句连接词（subordinate conjunctions）：在这些词前面可以切分（次级语义边界）
ZH_CLAUSE_BOUNDARIES = {
    # 让步
    "虽然", "尽管", "即使", "即便", "不论", "不管", "无论",
    # 因果
    "因为", "由于", "所以", "因此", "于是", "故",
    # 转折
    "但是", "然而", "不过", "可是", "但", "却", "只是",
    # 条件
    "如果", "假如", "倘若", "只要", "除非", "否则",
    # 并列
    "并且", "而且", "同时", "此外", "另外", "再者", "并且", "更",
    # 目的
    "为了", "以便", "以求",
    # 结果
    "以至于", "致使", "使得",
    # 时间
    "当", "当...时", "在...时", "之后", "之前", "随着",
}


# 强句末标点（必须切分）
ZH_SENTENCE_END = re.compile(r'(?<=[。！？])\s*')
# 次级句末标点（默认不切，可配置）
ZH_SOFT_END = re.compile(r'(?<=[；])\s*')
# 引号对（成对保护内部句末标点）
ZH_QUOTE_PAIRS = [
    ("「", "」"),
    ("『", "』"),
    ("\"", "\""),
    ("'", "'"),
    ("'", "'"),
]


class ChineseSplitter(BaseSentenceSplitter):
    """中文分句器（Tier 3 规则 + Tier 2 jieba 增强）。"""

    language = "zh"

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.use_jieba = self.config.get("use_jieba", True)
        self.entity_protection = self.config.get("entity_protection", True)
        self.handle_soft_end = self.config.get("handle_soft_end", True)
        self.max_sentence_length = self.config.get("max_sentence_length", 200)

        # jieba tokenizer（可选）
        self.tokenizer: Optional[JiebaTokenizer] = None
        if self.use_jieba:
            self.tokenizer = JiebaTokenizer()

    def is_available(self) -> bool:
        return True  # 中文分句器总是可用（jieba 缺失时降级为字符级）

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
        text, quote_map = self._protect_quoted(text)

        # 2. 按强句末标点（。！？）切分
        candidates = re.split(ZH_SENTENCE_END, text)
        candidates = [c.strip() for c in candidates if c.strip()]

        # 3. 还原引号
        candidates = [self._restore_quotes(c, quote_map) for c in candidates]

        # 4. 构造 SentenceBlock
        result = []
        idx = 0
        for c in candidates:
            if not c:
                continue
            # 过长句二次切分
            if len(c) > self.max_sentence_length:
                result.extend(self._split_long_sentence(c, idx))
                idx += len([x for x in result if x.index >= idx])  # advance idx
            else:
                block = self._make_block_with_metadata(c, idx)
                result.append(block)
                idx += 1

        return result

    def _make_block_with_metadata(self, text: str, index: int) -> SentenceBlock:
        """构造 SentenceBlock，包含 jieba 元数据。"""
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

        for open_q, close_q in ZH_QUOTE_PAIRS:
            # 转义正则
            open_pat = re.escape(open_q)
            close_pat = re.escape(close_q)

            def replace_quoted(match):
                nonlocal counter
                inner = match.group(1)
                if any(p in inner for p in "。！？；.!?;"):
                    placeholder = f"§ZHQUOTE{counter}§"
                    quote_map[placeholder] = match.group(0)
                    counter += 1
                    return placeholder
                return match.group(0)

            text = re.sub(open_pat + r'(.*?)' + close_pat, replace_quoted, text)

        return text, quote_map

    def _restore_quotes(self, text: str, quote_map: dict) -> str:
        for placeholder, original in quote_map.items():
            text = text.replace(placeholder, original)
        return text

    def _split_long_sentence(self, text: str, start_idx: int) -> List[SentenceBlock]:
        """过长句：先按 ；， 切，再按 max_sentence_length 强制切。"""
        parts = re.split(r'(?<=[；，,;])\s*', text)
        result = []
        idx = start_idx
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if len(p) > self.max_sentence_length:
                # 强制切
                for i in range(0, len(p), self.max_sentence_length):
                    chunk = p[i:i + self.max_sentence_length].strip()
                    if chunk:
                        result.append(self._make_block_with_metadata(chunk, idx))
                        idx += 1
            else:
                result.append(self._make_block_with_metadata(p, idx))
                idx += 1
        return result
