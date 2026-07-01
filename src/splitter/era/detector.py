"""Era detector (ancient / modern / mixed) for Chinese text.

基于三层关键词加权评分：
- 现代专属词（exclusive）→ modern
- 古代专属词（exclusive）→ ancient
- 通用现代词 / 通用古代词 → 加分
- 得分竞争 + 1.5x 阈值
"""

from __future__ import annotations
from typing import List, Tuple
from ..models import EraInfo
from .vocab import (
    MODERN_EXCLUSIVE,
    MODERN_COMMON,
    ANCIENT_EXCLUSIVE,
    ANCIENT_COMMON,
)


class EraDetector:
    """时代检测器（仅对中文内容生效）。"""

    def __init__(self):
        self.modern_ex = MODERN_EXCLUSIVE
        self.modern_cm = MODERN_COMMON
        self.ancient_ex = ANCIENT_EXCLUSIVE
        self.ancient_cm = ANCIENT_COMMON

    def detect(self, text: str) -> EraInfo:
        """检测文本所属时代。

        Returns:
            EraInfo
        """
        if not text or not text.strip():
            return EraInfo(era="mixed", confidence=0.0, keywords=[])

        text = text.strip()
        if len(text) < 3:
            return EraInfo(era="mixed", confidence=0.0, keywords=[])

        # 1. 扫描匹配
        modern_ex_hits = [kw for kw in self.modern_ex if kw in text]
        ancient_ex_hits = [kw for kw in self.ancient_ex if kw in text]
        modern_cm_hits = [kw for kw in self.modern_cm if kw in text]
        ancient_cm_hits = [kw for kw in self.ancient_cm if kw in text]

        # 2. 计算得分
        modern_score = len(modern_ex_hits) * 3 + len(modern_cm_hits)
        ancient_score = len(ancient_ex_hits) * 3 + len(ancient_cm_hits)

        # 3. 判定
        if modern_score >= 2 and modern_score >= ancient_score * 1.5:
            confidence = min(0.6 + modern_score * 0.08, 0.98)
            return EraInfo(era="modern", confidence=confidence, keywords=modern_ex_hits[:5])
        if len(modern_ex_hits) >= 1 and len(ancient_ex_hits) == 0:
            return EraInfo(era="modern", confidence=0.8, keywords=modern_ex_hits[:3])
        if ancient_score >= 2 and ancient_score >= modern_score * 1.5:
            confidence = min(0.6 + ancient_score * 0.08, 0.98)
            return EraInfo(era="ancient", confidence=confidence, keywords=ancient_ex_hits[:5])
        if len(ancient_ex_hits) >= 1 and len(modern_ex_hits) == 0:
            return EraInfo(era="ancient", confidence=0.8, keywords=ancient_ex_hits[:3])
        if modern_score > ancient_score and modern_score >= 2:
            return EraInfo(era="modern", confidence=0.6, keywords=modern_ex_hits[:3])
        if ancient_score > modern_score and ancient_score >= 2:
            return EraInfo(era="ancient", confidence=0.6, keywords=ancient_ex_hits[:3])

        return EraInfo(era="mixed", confidence=0.0, keywords=[])

    def detect_batch(self, texts: List[str]) -> List[EraInfo]:
        """批量检测。"""
        return [self.detect(t) for t in texts]
