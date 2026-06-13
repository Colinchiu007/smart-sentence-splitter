"""Subtitle segmenter (Layer 3).

将 SceneSegment 内的文本切分为 8-15 字的字幕块。
"""

from __future__ import annotations
from typing import List

from ..models import SubtitleBlock, SceneSegment


class SubtitleSegmenter:
    """字幕级分割器。"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.min_chars = self.config.get("min_chars_per_block", 8)
        self.max_chars = self.config.get("max_chars_per_block", 15)
        self.punctuation_priority = self.config.get("punctuation_priority", [
            "。", "！", "？", "；", "，",
            ".", "!", "?", ",",
            "、", " ", "\n",
        ])
        self.time_method = self.config.get("time_calculation_method", "proportional")

    def segment(self, scene: SceneSegment) -> List[SubtitleBlock]:
        """为单个 SceneSegment 生成字幕块列表。"""
        text = scene.text
        parent_id = scene.segment_id
        parent_duration = scene.estimated_duration

        if not text or not text.strip():
            return []

        blocks = self._split_into_blocks(text)
        return self._assign_timestamps(blocks, parent_duration, parent_id)

    def _split_into_blocks(self, text: str) -> List[str]:
        """将文本切分为字幕块。"""
        blocks: List[str] = []
        current = ""

        for char in text:
            current += char

            # 如果遇到标点
            if char in self.punctuation_priority:
                if len(current) >= self.min_chars:
                    blocks.append(current)
                    current = ""
                # 否则继续累积

            # 强制切分（达到 max_chars）
            if len(current) >= self.max_chars:
                # 尝试在最近的标点处切
                split_pos = self._find_split_position(current)
                if split_pos > 0:
                    blocks.append(current[:split_pos])
                    current = current[split_pos:]
                else:
                    blocks.append(current)
                    current = ""

        # 处理尾部
        if current.strip():
            if len(current) < self.min_chars and blocks:
                # 太小，合并到上一块
                blocks[-1] += current
            elif current.strip():
                blocks.append(current)

        return [b for b in blocks if b.strip()]

    def _find_split_position(self, text: str) -> int:
        """找到合适的切分位置（最近的标点/空格之后）。"""
        # 优先在 punctuation_priority 列表中靠前的标点处切
        for i in range(len(text) - 1, -1, -1):
            if text[i] in self.punctuation_priority:
                return i + 1
        return -1

    def _assign_timestamps(
        self,
        blocks: List[str],
        parent_duration: float,
        parent_id: int,
    ) -> List[SubtitleBlock]:
        """为字幕块分配时间戳。"""
        if not blocks:
            return []

        if self.time_method == "equal":
            return self._equal_timestamps(blocks, parent_duration, parent_id)
        return self._proportional_timestamps(blocks, parent_duration, parent_id)

    def _equal_timestamps(
        self,
        blocks: List[str],
        parent_duration: float,
        parent_id: int,
    ) -> List[SubtitleBlock]:
        """平均分配时间。"""
        block_dur = parent_duration / len(blocks)
        result = []
        for i, text in enumerate(blocks):
            result.append(SubtitleBlock(
                text=text,
                display_order=i,
                start_time=i * block_dur,
                duration=block_dur,
                parent_segment_id=parent_id,
            ))
        return result

    def _proportional_timestamps(
        self,
        blocks: List[str],
        parent_duration: float,
        parent_id: int,
    ) -> List[SubtitleBlock]:
        """按字数比例分配时间。"""
        total_chars = sum(len(b) for b in blocks)
        if total_chars == 0:
            return []

        result = []
        current_time = 0.0
        for i, text in enumerate(blocks):
            dur = (len(text) / total_chars) * parent_duration
            result.append(SubtitleBlock(
                text=text,
                display_order=i,
                start_time=current_time,
                duration=dur,
                parent_segment_id=parent_id,
            ))
            current_time += dur
        return result
