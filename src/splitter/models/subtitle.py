"""SubtitleBlock data model."""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class SubtitleBlock:
    """字幕块，对应屏幕上一行字幕。

    Attributes:
        text: 字幕文本
        display_order: 显示顺序（在同一 scene 内从0开始）
        start_time: 开始时间（秒，相对所属 scene）
        duration: 显示时长（秒）
        parent_segment_id: 所属语音段落的 segment_id
    """

    text: str
    display_order: int
    start_time: float
    duration: float
    parent_segment_id: int

    def __post_init__(self):
        if not self.text:
            raise ValueError("SubtitleBlock.text cannot be empty")
        if self.display_order < 0:
            raise ValueError("SubtitleBlock.display_order must be >= 0")
        if self.start_time < 0:
            raise ValueError("SubtitleBlock.start_time must be >= 0")
        if self.duration < 0:
            raise ValueError("SubtitleBlock.duration must be >= 0")
        if self.parent_segment_id < 0:
            raise ValueError("SubtitleBlock.parent_segment_id must be >= 0")

    def to_dict(self) -> dict:
        return asdict(self)
