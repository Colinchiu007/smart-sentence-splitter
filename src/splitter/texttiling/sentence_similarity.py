"""Sentence similarity metrics for TextTiling."""

from __future__ import annotations
import math
from typing import Dict, Set


def cosine_similarity(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    """余弦相似度（基于词频向量）。

    Args:
        v1: 词 → 频次 字典
        v2: 词 → 频次 字典

    Returns:
        相似度 0.0-1.0
    """
    if not v1 or not v2:
        return 0.0

    # 点积
    common_keys = set(v1.keys()) & set(v2.keys())
    dot = sum(v1[k] * v2[k] for k in common_keys)

    # 模
    norm1 = math.sqrt(sum(v * v for v in v1.values()))
    norm2 = math.sqrt(sum(v * v for v in v2.values()))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot / (norm1 * norm2)


def jaccard_similarity(s1: Set[str], s2: Set[str]) -> float:
    """Jaccard 相似度（基于词集合）。

    Args:
        s1: 词集合
        s2: 词集合

    Returns:
        相似度 0.0-1.0
    """
    if not s1 or not s2:
        return 0.0
    intersection = len(s1 & s2)
    union = len(s1 | s2)
    if union == 0:
        return 0.0
    return intersection / union
