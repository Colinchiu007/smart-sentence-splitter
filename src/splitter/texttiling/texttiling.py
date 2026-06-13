"""TextTiling algorithm for unsupervised topic segmentation.

Based on Hearst (1997) "TextTiling: Segmenting Text into Multi-Paragraph
Subtopic Passages".

Algorithm steps:
1. Tokenize text into words
2. Sliding window: create overlapping tiles
3. Vectorize each tile (bag-of-words)
4. Compute cosine similarity between adjacent tiles
5. Depth score: how much a tile differs from its neighbors
6. Boundaries: local maxima in depth score above threshold

Notes:
- Works on word-level (Chinese must be pre-segmented with jieba)
- Pure stdlib (no numpy/scipy dependency)
- Suitable for texts with multiple distinct topic shifts
"""

from __future__ import annotations
import re
from collections import Counter
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

from .sentence_similarity import cosine_similarity


@dataclass
class TopicBoundary:
    """主题边界标记。

    Attributes:
        position: 在原文本中的字符位置（用于还原）
        depth_score: 深度评分（相对落差，越大越可能是边界）
        confidence: 归一化置信度 0-1
        text_before: 边界前 ~30 字符（用于调试/展示）
        text_after: 边界后 ~30 字符
    """

    position: int
    depth_score: float
    confidence: float
    text_before: str = ""
    text_after: str = ""

    def __post_init__(self):
        if self.position < 0:
            raise ValueError("TopicBoundary.position must be >= 0")
        if not (0.0 <= self.confidence <= 1.0):
            # 允许 confidence 暂时超出 0-1，由调用方归一化
            pass


class TextTiling:
    """TextTiling 主题分割算法。

    Args:
        min_text_length: 短于此长度的文本直接返回无边界
        window_size: 滑动窗口大小（词数）
        step_size: 滑动步长（默认 w//2，重叠 50%）
        depth_score_threshold: 深度评分阈值（0.0-2.0）
        smoothing_passes: 相似度序列平滑次数
    """

    def __init__(
        self,
        min_text_length: int = 100,
        window_size: int = 20,
        step_size: Optional[int] = None,
        depth_score_threshold: float = 0.3,
        smoothing_passes: int = 0,
    ):
        self.min_text_length = min_text_length
        self.window_size = window_size
        self.step_size = step_size if step_size is not None else max(1, window_size // 2)
        self.depth_score_threshold = depth_score_threshold
        self.smoothing_passes = max(0, smoothing_passes)

    def tokenize(self, text: str) -> List[str]:
        """分词（默认按空白切分，调用方可替换为 jieba）。"""
        if not text:
            return []
        # 简单按空白 + 标点切分
        return [t for t in re.split(r'\s+', text.strip()) if t]

    def find_boundaries(self, text: str, tokens: Optional[List[str]] = None) -> List[TopicBoundary]:
        """在文本中查找主题边界。

        Args:
            text: 原始文本
            tokens: 预分词结果（None 时自动分词）

        Returns:
            TopicBoundary 列表（按 position 升序）
        """
        if not text or not text.strip():
            return []

        # 短文本早退
        if len(text) < self.min_text_length:
            return []

        # 1. 分词
        if tokens is None:
            tokens = self.tokenize(text)
        if len(tokens) < self.window_size * 2:
            return []

        # 2. 滑动窗口构建 tiles
        tiles, tile_start_indices = self._build_tiles(tokens)
        if len(tiles) < 3:
            return []

        # 3. 向量化
        tile_vectors = [Counter(tile) for tile in tiles]

        # 4. 相邻 tile 相似度
        sims = self._compute_similarities(tile_vectors)
        if len(sims) < 2:
            return []

        # 5. 平滑
        sims = self._smooth(sims, self.smoothing_passes)

        # 6. 深度评分
        depths = self._compute_depth_scores(sims)

        # 7. 边界识别
        boundaries = self._identify_boundaries(depths, threshold=self.depth_score_threshold)

        # 8. 转换为字符位置 + 上下文
        result = []
        max_depth = max(depths) if depths else 1.0
        for tile_idx, depth in boundaries:
            # tile 对应的 token 位置
            token_pos = tile_start_indices[tile_idx]
            # token 位置 → 字符位置（按空格累加 token 长度）
            char_pos = self._token_pos_to_char_pos(text, tokens, token_pos)
            result.append(TopicBoundary(
                position=char_pos,
                depth_score=depth,
                confidence=min(1.0, depth / max_depth) if max_depth > 0 else 0.0,
                text_before=text[max(0, char_pos - 30):char_pos],
                text_after=text[char_pos:min(len(text), char_pos + 30)],
            ))

        return result

    def _build_tiles(self, tokens: List[str]) -> Tuple[List[List[str]], List[int]]:
        """滑动窗口构建 tile 序列。

        Returns:
            (tiles, start_indices)
        """
        tiles = []
        start_indices = []
        w = self.window_size
        step = self.step_size
        for i in range(0, len(tokens) - w + 1, step):
            tiles.append(tokens[i:i + w])
            start_indices.append(i)
        return tiles, start_indices

    def _compute_similarities(self, tile_vectors: List[Counter]) -> List[float]:
        """计算相邻 tile 的余弦相似度。"""
        sims = []
        for i in range(len(tile_vectors) - 1):
            sim = cosine_similarity(
                dict(tile_vectors[i]),
                dict(tile_vectors[i + 1]),
            )
            sims.append(sim)
        return sims

    def _smooth(self, sims: List[float], passes: int) -> List[float]:
        """用滑动平均平滑相似度序列。"""
        if passes <= 0 or len(sims) < 3:
            return sims

        result = list(sims)
        for _ in range(passes):
            new_result = [result[0]]
            for i in range(1, len(result) - 1):
                new_result.append((result[i - 1] + result[i] + result[i + 1]) / 3.0)
            new_result.append(result[-1])
            result = new_result
        return result

    def _compute_depth_scores(self, sims: List[float]) -> List[float]:
        """计算深度评分：当前点比左右邻居低多少。

        depth[i] = sims[i-1] + sims[i+1] - 2 * sims[i]

        注意：sims[i] 是 tile[i] 和 tile[i+1] 的相似度。
        所以 sims[i] 表示"第 i 个边界"的相似度。
        depth[i] 越大，表示 tile[i] 与 tile[i+1] 之间的相似度落差越大。
        """
        depths = []
        for i in range(len(sims)):
            if i == 0 or i == len(sims) - 1:
                depths.append(0.0)
                continue
            depth = sims[i - 1] + sims[i + 1] - 2.0 * sims[i]
            depths.append(max(0.0, depth))
        return depths

    def _identify_boundaries(
        self,
        depths: List[float],
        threshold: float,
    ) -> List[Tuple[int, float]]:
        """从深度评分中识别边界（局部极大值 + 阈值过滤）。

        局部极大值定义：depths[i] >= depths[i-1] 且 depths[i] >= depths[i+1]
        （允许相邻同值，即"平顶"也视为极大值）
        """
        if not depths:
            return []

        boundaries = []
        for i in range(len(depths)):
            if depths[i] <= threshold:
                continue
            # 局部极大值判定
            left_ok = (i == 0) or (depths[i] >= depths[i - 1])
            right_ok = (i == len(depths) - 1) or (depths[i] >= depths[i + 1])
            if left_ok and right_ok:
                boundaries.append((i, depths[i]))

        return boundaries

    @staticmethod
    def _token_pos_to_char_pos(text: str, tokens: List[str], token_pos: int) -> int:
        """将 token 位置转换为字符位置。

        简化策略：按 token 长度累加，token 之间可能含 1 个空格。
        """
        if token_pos == 0:
            return 0
        if token_pos >= len(tokens):
            return len(text)

        # 累加 token 长度 + token 间空格
        char_pos = 0
        for i in range(token_pos):
            char_pos += len(tokens[i])
            # 加上 token 间的空格（如果有）
            if i < len(tokens) - 1 and char_pos < len(text) and text[char_pos] in ' \t':
                char_pos += 1
        return min(char_pos, len(text))
