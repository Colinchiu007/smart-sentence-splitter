"""Jieba-based Chinese tokenizer.

可选依赖：jieba 未安装时降级为 char-level 兜底。
"""

from __future__ import annotations
from typing import List, Tuple

from ...core.base_tokenizer import BaseTokenizer


class JiebaTokenizer(BaseTokenizer):
    """Jieba 中文分词器。"""

    language = "zh"

    def __init__(self):
        self._jieba = None
        self._posseg = None
        self._available = False
        self._try_load()

    def _try_load(self):
        try:
            import jieba
            import jieba.posseg as pseg
            self._jieba = jieba
            self._posseg = pseg
            self._available = True
        except ImportError:
            self._available = False

    def is_available(self) -> bool:
        return self._available

    def tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        if not self._available:
            # 兜底：单字分词
            return list(text)
        return list(self._jieba.cut(text))

    def pos_tag(self, text: str) -> List[Tuple[str, str]]:
        if not text or not self._available:
            return []
        return [(w.word, w.flag) for w in self._posseg.cut(text)]
