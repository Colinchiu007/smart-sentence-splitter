"""Whitespace tokenizer for English (zero-dependency)."""

from __future__ import annotations
import re
from typing import List, Tuple
from ...core.base_tokenizer import BaseTokenizer


class WhitespaceTokenizer(BaseTokenizer):
    """基于空白字符的英文分词器（零依赖）。"""

    language = "en"

    # 英文分词：在空白 + 标点边界切分，但保留缩写
    _WORD_PATTERN = re.compile(r"[A-Za-z]+(?:'[a-z]+)?|\d+(?:\.\d+)?|[^\s\w]")

    def tokenize(self, text: str) -> List[str]:
        """分词：英文单词、数字、标点分别作为 token。"""
        if not text:
            return []
        return self._WORD_PATTERN.findall(text)

    def pos_tag(self, text: str) -> List[Tuple[str, str]]:
        """英文不做词性标注（默认空实现）。"""
        return []
