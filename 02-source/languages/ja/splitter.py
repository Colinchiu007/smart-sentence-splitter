"""JapaneseSplitter — 日语分句器 (v0.9.9 新增).

日语和中文类似, 不使用空格分隔单词, 句末标点为句点、感叹号、问号。
处理:
- 括弧内句点不分割 (「」『』（）)
- 三点リーダー ... 不分割
"""

import re
from typing import List, Optional

from ...core.base_splitter import BaseSentenceSplitter

# 日语句末标点
JA_EOS_RE = re.compile(r'[。！？\n]')

# 日语配对引号
JA_PAIRED_QUOTES = [
    ("「", "」"),
    ("『", "』"),
    ("（", "）"),
    ("(", ")"),
    ("〔", "〕"),
]


class JapaneseSplitter(BaseSentenceSplitter):
    """日语分句器 — 按句末标点分割, 保护配对引号。"""

    language = "ja"
    tier = "tier3_rule_ja"

    def __init__(self, config: Optional[dict] = None):
        super().__init__()
        self.config = config or {}

    def is_available(self) -> bool:
        return True

    def split(self, text: str) -> List:
        """日语分句入口。"""
        from ...models import SentenceBlock

        if not text or not text.strip():
            return []

        boundaries = self._find_boundaries(text)

        # 按边界切分
        sentences = []
        last = 0
        for b in boundaries:
            chunk = text[last:b + 1].strip()
            if chunk:
                sentences.append(chunk)
            last = b + 1
        remaining = text[last:].strip()
        if remaining:
            sentences.append(remaining)

        # 构建 SentenceBlock
        blocks = []
        for i, s in enumerate(sentences):
            if not s:
                continue
            blocks.append(SentenceBlock(
                text=s,
                index=i,
                tier="tier3_rule_ja",
                language="ja",
                words=[],
                pos_tags=[],
                confidence=0.9,
            ))

        return blocks

    def _find_boundaries(self, text: str) -> List[int]:
        """找到所有可分割的句末标点位置, 排除引号内。"""
        # 先标记引号嵌套区域
        in_quote = [False] * len(text)
        for left, right in JA_PAIRED_QUOTES:
            i = 0
            while i < len(text):
                l = text.find(left, i)
                if l < 0:
                    break
                r = text.find(right, l + 1)
                if r < 0:
                    i = l + 1
                    continue
                for j in range(l, r + 1):
                    in_quote[j] = True
                i = r + 1

        # 在引号外找句末标点
        boundaries = []
        for m in JA_EOS_RE.finditer(text):
            pos = m.start()
            if pos >= len(text):
                continue
            if in_quote[pos]:
                continue
            boundaries.append(pos)

        return boundaries
