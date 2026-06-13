"""TextTiling Semantic Splitter.

Tier 2 升级版分句器：
1. 用 TextTiling 算法识别主题边界
2. 用现有规则分句器按句子切分
3. 在主题边界处插入 is_topic_boundary=True 的虚拟 SentenceBlock

输出顺序：
  sentences[0] → sentences[1] → [BOUNDARY] → sentences[2] → sentences[3] → [BOUNDARY] → ...

注意：BOUNDARY 是虚拟 block，text 是边界处的 "「主题转换」" 标记。
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
    """TextTiling 主题分割驱动的分句器（Tier 2A）。

    特征：
    - language="auto"：支持中文 + 英文（jieba 预分词）
    - tier="tier2_semantic"
    - 在主题边界处插入虚拟 SentenceBlock（is_topic_boundary=True）
    """

    language = "auto"
    tier = "tier2_semantic"

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.tt = TextTiling(
            min_text_length=self.config.get("min_text_length", 100),
            window_size=self.config.get("window_size", 20),
            step_size=self.config.get("step_size"),
            depth_score_threshold=self.config.get("depth_score_threshold", 0.3),
            smoothing_passes=self.config.get("smoothing_passes", 1),
        )
        # 兜底：使用规则分句器做句子级切分
        self.zh_splitter = ChineseSplitter({"use_jieba": True})
        self.en_splitter = EnglishSplitter()

    def is_available(self) -> bool:
        """始终可用。"""
        return True

    def split(self, text: str) -> List[SentenceBlock]:
        if not text or not text.strip():
            return []

        text = text.strip()

        # 1. 检测语言
        lang = detect_language(text)
        if lang == "ja":
            lang = "zh"  # 暂用 zh 兜底

        # 2. 短文本早退：直接用规则分句
        if len(text) < self.tt.min_text_length:
            return self._fallback_split(text, lang)

        # 3. 预分词
        tokens = self._pre_tokenize(text, lang)

        # 4. 识别主题边界
        try:
            boundaries = self.tt.find_boundaries(text, tokens=tokens)
        except Exception:
            # 异常时降级到规则分句
            return self._fallback_split(text, lang)

        # 5. 规则分句（获得基础句子列表）
        base_sentences = self._fallback_split(text, lang)

        # 6. 合并：在边界处插入 virtual block
        if not boundaries:
            return base_sentences

        return self._insert_boundaries(base_sentences, boundaries, lang)

    def _pre_tokenize(self, text: str, lang: str) -> List[str]:
        """预分词（中文用 jieba，英文空白）。"""
        if lang == "zh":
            try:
                import jieba
                return list(jieba.cut(text))
            except ImportError:
                # jieba 不可用时按字符分
                return list(text)
        return text.split()

    def _fallback_split(self, text: str, lang: str) -> List[SentenceBlock]:
        """规则分句（兜底）。"""
        try:
            if lang == "zh":
                return self.zh_splitter.split(text)
            return self.en_splitter.split(text)
        except Exception:
            # 终极兜底：按句号切
            from . import _naive_split
            return _naive_split(text, self.tier, lang)

    def _insert_boundaries(
        self,
        sentences: List[SentenceBlock],
        boundaries: List[TopicBoundary],
        lang: str,
    ) -> List[SentenceBlock]:
        """在主题边界处插入 virtual SentenceBlock。"""
        if not sentences or not boundaries:
            return sentences

        # 边界累积偏移：每插入一个 virtual block，后续 index 都要 +1
        result = []
        sentence_idx = 0
        boundary_idx = 0
        virtual_index_offset = 0

        # 构造当前文本累积位置（从所有 sentence.text 拼接）
        text_parts = []
        for s in sentences:
            text_parts.append(s.text)
        # 全文（含 sentence 间隔的空白）
        full_text = "".join(text_parts)

        # 简化策略：
        # 1. 对每个 boundary，找到其字符 position 在哪个 sentence 范围内
        # 2. 在该 sentence 之前插入 virtual block

        for b in boundaries:
            # 找到 position 对应的 sentence
            cum_len = 0
            inserted = False
            for i, s in enumerate(sentences):
                s_start = cum_len
                s_end = cum_len + len(s.text)
                if s_start <= b.position < s_end:
                    # 边界在 sentence i 内 → 在 sentence i 之前插入 virtual block
                    virtual_idx = i + virtual_index_offset
                    virtual_block = SentenceBlock(
                        text="「主题转换」",
                        index=virtual_idx,
                        language=lang,
                        tier=self.tier,
                        confidence=b.confidence,
                        is_topic_boundary=True,
                        topic_depth_score=b.depth_score,
                    )
                    # 找到 result 中 sentence i 的实际位置
                    # 简化：按顺序遍历 result，找到第 i 个非 boundary
                    non_boundary_count = sum(1 for x in result if not x.is_topic_boundary)
                    if non_boundary_count == i:
                        result.append(virtual_block)
                        virtual_index_offset += 1
                    else:
                        # 插入到 result 末尾（兜底）
                        result.append(virtual_block)
                        virtual_index_offset += 1
                    inserted = True
                    break
                cum_len = s_end

            if not inserted:
                # 边界超出所有 sentence 范围，忽略
                pass

        # 把剩余 sentences 追加（已按顺序）
        non_boundary_count = sum(1 for x in result if not x.is_topic_boundary)
        for s in sentences:
            result.append(s)

        # 重新设置 index
        for i, s in enumerate(result):
            s.index = i

        return result


def _naive_split(text: str, tier: str, lang: str) -> List[SentenceBlock]:
    """终极兜底分句：按句号切。"""
    import re
    parts = re.split(r'(?<=[。！？.!?])\s*', text)
    parts = [p.strip() for p in parts if p.strip()]
    return [
        SentenceBlock(text=p, index=i, language=lang, tier=tier)
        for i, p in enumerate(parts)
    ]
