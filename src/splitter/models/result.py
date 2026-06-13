"""SplitResult data model — the final output of SmartSentenceSplitter.split()."""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from .sentence import SentenceBlock
from .scene import SceneSegment


@dataclass
class SplitResult:
    """分句处理完整结果。

    Attributes:
        sentences: 语义分句结果
        scenes: 场景段落列表
        tier_used: 实际使用的 tier 名称
        language: 检测到的语言
        total_duration: 总时长（秒）
        total_words: 总字数
        total_scenes: 总场景数
        config_snapshot: 当时使用的配置快照
    """

    sentences: List[SentenceBlock] = field(default_factory=list)
    scenes: List[SceneSegment] = field(default_factory=list)
    tier_used: str = "tier3_rule"
    language: str = "zh"
    total_duration: float = 0.0
    total_words: int = 0
    total_scenes: int = 0
    config_snapshot: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.total_scenes == 0 and self.scenes:
            self.total_scenes = len(self.scenes)
        if self.total_duration == 0.0 and self.scenes:
            self.total_duration = sum(s.estimated_duration for s in self.scenes)
        if self.total_words == 0:
            self.total_words = sum(len(s.text) for s in self.scenes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sentences": [s.to_dict() for s in self.sentences],
            "scenes": [s.to_dict() for s in self.scenes],
            "tier_used": self.tier_used,
            "language": self.language,
            "total_duration": round(self.total_duration, 2),
            "total_words": self.total_words,
            "total_scenes": self.total_scenes,
            "config_snapshot": self.config_snapshot,
        }
