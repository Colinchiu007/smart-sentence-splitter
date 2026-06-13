"""EraInfo data model."""

from dataclasses import dataclass, field, asdict
from typing import List


@dataclass
class EraInfo:
    """时代检测结果。

    Attributes:
        era: 时代标签（modern / ancient / mixed）
        confidence: 置信度 0-1
        keywords: 匹配到的关键词列表
    """

    era: str
    confidence: float
    keywords: List[str] = field(default_factory=list)

    VALID_ERAS = ("modern", "ancient", "mixed")

    def __post_init__(self):
        if self.era not in self.VALID_ERAS:
            raise ValueError(
                f"EraInfo.era must be one of {self.VALID_ERAS}, got '{self.era}'"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("EraInfo.confidence must be in [0, 1]")

    def to_dict(self) -> dict:
        return asdict(self)
