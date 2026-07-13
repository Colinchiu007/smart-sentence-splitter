"""Subtitle segmenter (Layer 3).

将 SceneSegment 内的文本切分为 8-15 字的字幕块。

v0.9.2 改动: 复用 LengthSegmenter 配对引号保护 — 不再自己实现切分。
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
        self.time_method = self.config.get("time_calculation_method", "proportional")
        # v0.9.2: 复用 LengthSegmenter A 模式 (配对引号保护)
        from .length_segmenter import LengthSegmenter
        self._length_seg = LengthSegmenter(
            strategy="A",
            min_chars=self.min_chars,
            max_chars=self.max_chars,
        )

    def segment(self, scene: SceneSegment) -> List[SubtitleBlock]:
        """为单个 SceneSegment 生成字幕块列表。"""
        text = scene.text
        parent_id = scene.segment_id
        parent_duration = scene.estimated_duration

        if not text or not text.strip():
            return []

        # v0.9.2: 用 LengthSegmenter 切 (配对引号保护)
        blocks = self._length_seg.split_text(text)

        # LengthSegmenter._resplit 不会切 < max_chars 的短文本, 强制至少切一块
        if not blocks:
            blocks = [text]

        # 后处理: 把太短的首块合并到上一块, 末尾太短合并到上一块
        blocks = self._merge_short(blocks)

        return self._assign_timestamps(blocks, parent_duration, parent_id)

    def _merge_short(self, blocks: List[str]) -> List[str]:
        """合并 < min_chars 的块或纯标点短块。
        
        规则:
        1. 前一块 < min_chars → 合并
        2. 当前块 <= 2 字且全是标点 → 无条件合并到前一块
        """
        if not blocks:
            return blocks
        merged = [blocks[0]]
        for b in blocks[1:]:
            b_stripped = b.strip()
            is_punct_tail = len(b_stripped) <= 2 and all(c in "\u3002\uff01\uff1f\uff1b\u3001.!?;\u2026" for c in b_stripped)
            is_short_tail = len(b_stripped) <= 3 and len(merged[-1]) >= self.min_chars
            if len(merged[-1]) < self.min_chars or is_punct_tail or is_short_tail:
                merged[-1] = merged[-1] + b
            else:
                merged.append(b)
        return [b for b in merged if b.strip()]

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
