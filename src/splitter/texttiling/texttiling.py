"""TextTiling algorithm for unsupervised topic segmentation.

Based on Hearst (1997) "TextTiling: Segmenting Text into Multi-Paragraph
Subtopic Passages".

中文适配:
- 字符级分词 (过滤停用字)
- 句级窗口 (vs 字符级窗口)
- 改进的深度评分
"""

from __future__ import annotations
import re
import math
from collections import Counter
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

from .sentence_similarity import cosine_similarity


@dataclass
class TopicBoundary:
    position: int
    depth_score: float
    confidence: float
    text_before: str = ""
    text_after: str = ""


# 中文停用字 (TextTiling 分词用)
STOP_CHARS = frozenset(
    '的了在是不也和就都而及与或但被把从到这那上下有我你他她它们个之以'
    '为所能会很太又再还吧吗啊呢嗯哦哈呀哟噢喔嘛呗啵'
)


class TextTiling:
    """TextTiling 主题分割算法。

    Args:
        min_text_length: 短于此长度的文本直接返回无边界
        sentence_window: 句级窗口大小 (句数)
        step_size: 滑动步长 (句数)
        depth_score_threshold: 深度评分阈值
        smoothing_passes: 平滑次数
    """

    def __init__(
        self,
        min_text_length: int = 30,
        sentence_window: int = 3,
        step_size: Optional[int] = None,
        depth_score_threshold: float = 0.15,
        smoothing_passes: int = 0,
    ):
        self.min_text_length = min_text_length
        self.sentence_window = sentence_window
        self.step_size = step_size if step_size is not None else max(1, sentence_window // 2)
        self.depth_score_threshold = depth_score_threshold
        self.smoothing_passes = max(0, smoothing_passes)

    # ===== 句级分词 =====

    def tokenize_sentence(self, sentence: str) -> List[str]:
        """将单个句子分词 (字符级, 过滤停用字)。

        示例:
            "今天天气真好" → ['今', '天', '天', '气', '真', '好']
            "Hello World" → ['hello', 'world']
        """
        tokens = []
        i = 0
        while i < len(sentence):
            c = sentence[i]
            if '\u4e00' <= c <= '\u9fff' and c not in STOP_CHARS:
                tokens.append(c)
                i += 1
            elif c.isascii() and c.isalpha():
                word = ''
                while i < len(sentence) and sentence[i].isascii() and (
                    sentence[i].isalpha() or sentence[i] == "'"
                ):
                    word += sentence[i]
                    i += 1
                if word:
                    tokens.append(word.lower())
            else:
                i += 1
        return tokens

    # ===== 句级 TextTiling =====

    def tile_by_sentences(self, sentences: List[str]) -> List[TopicBoundary]:
        """对句子列表执行 TextTiling, 返回主题边界。"""
        if len(sentences) < self.sentence_window * 2:
            return []

        # 1. 对每个句子分词
        sent_tokens = [self.tokenize_sentence(s) for s in sentences]

        # 2. 句级滑动窗口构建 tile
        tiles = []
        tile_sent_indices = []  # 每个 tile 覆盖的句号范围 [start_sent, end_sent)
        w = self.sentence_window
        step = self.step_size
        for start in range(0, len(sent_tokens) - w + 1, step):
            # 合并 w 个句子的 tokens
            combined = []
            for si in range(start, start + w):
                combined.extend(sent_tokens[si])
            tiles.append(Counter(combined))
            tile_sent_indices.append(start)

        if len(tiles) < 2:
            return []

        # 3. 余弦相似度序列
        sims = self._compute_similarities(tiles)

        # 4. 平滑
        sims = self._smooth(sims, self.smoothing_passes)

        if len(sims) < 2:
            return []

        # 5. 深度评分 (绝对值 + 相对)
        depths = self._compute_depth_scores(sims)

        # 6. 边界识别
        max_depth = max(depths) if depths else 1.0
        threshold = max(self.depth_score_threshold, max_depth * 0.3)  # 相对阈值
        boundaries = self._identify_boundaries(depths, threshold=threshold)

        # 7. 转换为字符位置
        result = []
        sentence_starts = [0]
        for s in sentences:
            sentence_starts.append(sentence_starts[-1] + len(s) + 1)  # +1 for separators

        for tile_idx, depth in boundaries:
            sent_idx = tile_sent_indices[tile_idx]
            if sent_idx < len(sentence_starts):
                char_pos = sentence_starts[sent_idx]
                result.append(TopicBoundary(
                    position=char_pos,
                    depth_score=depth,
                    confidence=min(1.0, depth / max_depth) if max_depth > 0 else 0.0,
                    text_before=("".join(sentences[max(0, sent_idx-1):sent_idx])[-30:]),
                    text_after=("".join(sentences[sent_idx:sent_idx+2])[:30]),
                ))

        return result

    def _compute_similarities(self, tile_vectors: List[Counter]) -> List[float]:
        sims = []
        for i in range(len(tile_vectors) - 1):
            sim = cosine_similarity(tile_vectors[i], tile_vectors[i + 1])
            sims.append(sim)
        return sims

    def _smooth(self, values: List[float], passes: int) -> List[float]:
        if passes <= 0:
            return values
        smoothed = list(values)
        for _ in range(passes):
            new_values = list(smoothed)
            for i in range(1, len(smoothed) - 1):
                new_values[i] = (smoothed[i - 1] + 2 * smoothed[i] + smoothed[i + 1]) / 4
            smoothed = new_values
        return smoothed

    def _compute_depth_scores(self, sims: List[float]) -> List[float]:
        depths = []
        for i in range(len(sims)):
            if i == 0 or i == len(sims) - 1:
                depths.append(0.0)
            else:
                d = sims[i - 1] + sims[i + 1] - 2 * sims[i]
                depths.append(max(0.0, d))
        return depths

    def _identify_boundaries(
        self, depths: List[float], threshold: float = 0.15
    ) -> List[Tuple[int, float]]:
        """找局部极大值且超过阈值的边界。"""
        boundaries = []
        for i in range(1, len(depths) - 1):
            if depths[i] > threshold and depths[i] >= depths[i - 1] and depths[i] >= depths[i + 1]:
                boundaries.append((i, depths[i]))
        # 如果没有局部极大值满足, 取全局最大
        if not boundaries and depths:
            max_depth = max(depths)
            if max_depth > threshold:
                max_idx = depths.index(max_depth)
                # 跳过首尾
                if 0 < max_idx < len(depths) - 1:
                    boundaries.append((max_idx, max_depth))
        return boundaries

    # ===== 向后兼容: 旧版接口 =====

    def tokenize(self, text: str) -> List[str]:
        """向下兼容: 旧字符级分词。"""
        # 探测语言
        cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        ascii_alpha = sum(1 for c in text if c.isascii() and c.isalpha())
        total = max(1, len(text))

        if cjk / total > 0.3 or (cjk + ascii_alpha) / total < 0.5:
            tokens = []
            i = 0
            while i < len(text):
                c = text[i]
                if '\u4e00' <= c <= '\u9fff' and c not in STOP_CHARS:
                    tokens.append(c)
                    i += 1
                elif c.isascii() and c.isalpha():
                    word = ''
                    while i < len(text) and text[i].isascii() and (text[i].isalpha() or text[i] == "'"):
                        word += text[i]
                        i += 1
                    if word: tokens.append(word.lower())
                else:
                    i += 1
            return tokens
        return [t.lower() for t in re.split(r'\s+', text.strip()) if t and t.isascii()]

    def find_boundaries(self, text: str, tokens: Optional[List[str]] = None) -> List[TopicBoundary]:
        """旧版接口 (按字符级 tiles 分). 已弃用, 用 tile_by_sentences()。"""
        if not text or not text.strip():
            return []
        if len(text) < self.min_text_length:
            return []
        if tokens is None:
            tokens = self.tokenize(text)
        if len(tokens) < self.sentence_window * 2:
            return []

        # 用字符级旧逻辑
        from collections import Counter
        tiles, start_indices = self._build_tiles(tokens)
        tile_vectors = [Counter(t) for t in tiles]
        sims = self._compute_similarities(tile_vectors)
        sims = self._smooth(sims, self.smoothing_passes)
        depths = self._compute_depth_scores(sims)
        max_depth = max(depths) if depths else 1.0
        threshold = max(self.depth_score_threshold, max_depth * 0.4)
        boundaries = self._identify_boundaries(depths, threshold=threshold)

        result = []
        for tile_idx, depth in boundaries:
            token_pos = start_indices[tile_idx]
            char_pos = self._token_pos_to_char_pos(text, tokens, token_pos)
            result.append(TopicBoundary(
                position=char_pos, depth_score=depth,
                confidence=min(1.0, depth / max_depth) if max_depth > 0 else 0.0,
                text_before=text[max(0, char_pos - 30):char_pos],
                text_after=text[char_pos:min(len(text), char_pos + 30)],
            ))
        return result

    def _build_tiles(self, tokens: List[str]) -> Tuple[List[List[str]], List[int]]:
        w = self.sentence_window
        step = self.step_size
        tiles = []
        start_indices = []
        for i in range(0, len(tokens) - w + 1, step):
            tiles.append(tokens[i:i + w])
            start_indices.append(i)
        return tiles, start_indices

    @staticmethod
    def _token_pos_to_char_pos(text: str, tokens: List[str], token_pos: int) -> int:
        if token_pos >= len(tokens):
            return len(text)
        total = 0
        for i in range(token_pos):
            total += len(tokens[i]) + 1
        return min(total, len(text))