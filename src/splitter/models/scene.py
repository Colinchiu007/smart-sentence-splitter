"""SceneSegment data model."""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
from .sentence import SentenceBlock
from .subtitle import SubtitleBlock
from .era import EraInfo


@dataclass
class SceneSegment:
    """语音段落，对应视频中的一个场景（6秒左右）。

    Attributes:
        text: 段落文本
        segment_id: 段落全局序号
        estimated_duration: 预估时长（秒）
        target_words: 目标字数
        sentences: 包含的 SentenceBlock 列表
        era_info: 时代检测结果（可选）
        subtitles: 字幕块列表
    """

    text: str
    segment_id: int
    estimated_duration: float
    target_words: int
    sentences: List[SentenceBlock] = field(default_factory=list)
    era_info: Optional[EraInfo] = None
    subtitles: List[SubtitleBlock] = field(default_factory=list)

    def __post_init__(self):
        if self.segment_id < 0:
            raise ValueError("SceneSegment.segment_id must be >= 0")
        if self.estimated_duration < 0:
            raise ValueError("SceneSegment.estimated_duration must be >= 0")
        if self.target_words < 0:
            raise ValueError("SceneSegment.target_words must be >= 0")

    def add_sentence(self, sentence: SentenceBlock) -> None:
        self.sentences.append(sentence)

    def add_subtitle(self, subtitle: SubtitleBlock) -> None:
        self.subtitles.append(subtitle)

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "text": self.text,
            "estimated_duration": round(self.estimated_duration, 2),
            "target_words": self.target_words,
            "sentence_count": len(self.sentences),
            "sentences": [s.to_dict() for s in self.sentences],
            "era_info": self.era_info.to_dict() if self.era_info else None,
            "subtitle_count": len(self.subtitles),
            "subtitles": [sub.to_dict() for sub in self.subtitles],
        }
