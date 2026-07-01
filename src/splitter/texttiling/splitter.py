"""TextTiling Semantic Splitter (v0.9.10 句级优化).

Tier 2 分句器：
1. 用 TextTiling 句级算法识别主题边界
2. 用规则分句器做句子级切分
3. 在主题边界处标记 is_topic_boundary=True

v0.9.10 改动:
- 从字符级窗口改为句级窗口 (sentence_window)
- 过滤中文停用字
- 相对阈值 (max_depth * 0.3 + absolute)
"""

from __future__ import annotations
from typing import List, Optional

from ..core.base_splitter import BaseSentenceSplitter
from ..models import SentenceBlock
from ..languages.zh.splitter import ChineseSplitter
from ..languages.en.splitter import EnglishSplitter
from ..utils.language_detect import detect_language
from .texttiling import TextTiling, TopicBoundary


class TextTilingSemanticSplitter(BaseSentenceSplitter):
    """TextTiling 主题分割分句器 (Tier 2A)。"""

    language = "auto"
    tier = "tier2_semantic"

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.tt = TextTiling(
            min_text_length=self.config.get("min_text_length", 30),
            sentence_window=self.config.get("sentence_window", 3),
            step_size=self.config.get("step_size"),
            depth_score_threshold=self.config.get("depth_score_threshold", 0.15),
            smoothing_passes=self.config.get("smoothing_passes", 0),
        )
        self.zh_splitter = ChineseSplitter({"use_jieba": True})
        self.en_splitter = EnglishSplitter()

    def is_available(self) -> bool:
        return True

    def split(self, text: str) -> List[SentenceBlock]:
        if not text or not text.strip():
            return []

        text = text.strip()
        lang = detect_language(text)
        if lang == "ja":
            lang = "zh"

        # 短文本早退
        if len(text) < self.tt.min_text_length:
            return self._fallback_split(text, lang)

        # 1. 先用规则分句器切成句子
        if lang == "en":
            rule_blocks = self.en_splitter.split(text)
        else:
            rule_blocks = self.zh_splitter.split(text)

        if not rule_blocks:
            return []

        # 2. 提取句子文本
        sentences = [b.text for b in rule_blocks]

        # 3. TextTiling 找主题边界 (句级)
        boundaries = self.tt.tile_by_sentences(sentences)

        # 4. 标记边界句子
        boundary_set = set()
        for b in boundaries:
            # 从字符位置反推句子索引
            char_pos = 0
            for idx, sent in enumerate(sentences):
                if char_pos >= b.position:
                    boundary_set.add(idx)
                    break
                char_pos += len(sent) + 1  # +1 for separator

        # 5. 给规则分句结果追加标记
        for i, block in enumerate(rule_blocks):
            block.is_topic_boundary = i in boundary_set

        return rule_blocks

    def _fallback_split(self, text: str, lang: str) -> List[SentenceBlock]:
        if lang == "en":
            return self.en_splitter.split(text) or []
        return self.zh_splitter.split(text) or []
