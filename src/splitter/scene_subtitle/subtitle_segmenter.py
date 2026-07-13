"""Subtitle segmenter (Layer 3).

将 SceneSegment 内的文本切分为 8-15 字的字幕块。

v0.9.2 改动: 复用 LengthSegmenter 配对引号保护 — 不再自己实现切分。
v0.10.1 改动: 字幕后处理 — 末尾标点去除、跨块引号清理、开头标点修正。
"""

from __future__ import annotations
from typing import List

from ..models import SubtitleBlock, SceneSegment

# 句末/句内标点（用于末尾去除和开头检测）
_TRAILING_PUNCT = frozenset("。！？；，、.!?;…\n")
# 纯标点判定集合（含引号，用于 _merge_short）
_PUNCT_CHARS = frozenset("。！？；，、.!?;…\n\"'\"\"''「」『』《》（）()[]【】{}§")
# 跨块引号对
_CROSS_BLOCK_QUOTES = [
    ('\u201c', '\u201d'),  # " "
    ('\u300c', '\u300d'),  # 「 」
    ('"', '"'),
    ("'", "'"),
]


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

        # v0.10.1: 字幕后处理 — 开头标点修正、末尾标点去除、跨块引号清理
        blocks = self._clean_subtitle_blocks(blocks)

        return self._assign_timestamps(blocks, parent_duration, parent_id)

    def _merge_short(self, blocks: List[str]) -> List[str]:
        """合并 < min_chars 的块或纯标点短块。
        
        规则:
        1. 前一块 < min_chars → 合并
        2. 当前块 <= 2 字且全是标点（含引号） → 无条件合并到前一块
        """
        if not blocks:
            return blocks
        merged = [blocks[0]]
        for b in blocks[1:]:
            b_stripped = b.strip()
            # v0.10.1: 扩展纯标点集合，包含引号字符
            is_punct_tail = len(b_stripped) <= 2 and all(c in _PUNCT_CHARS for c in b_stripped)
            is_short_tail = len(b_stripped) <= 3 and len(merged[-1]) >= self.min_chars
            if len(merged[-1]) < self.min_chars or is_punct_tail or is_short_tail:
                merged[-1] = merged[-1] + b
            else:
                merged.append(b)
        return [b for b in merged if b.strip()]

    def _clean_subtitle_blocks(self, blocks: List[str]) -> List[str]:
        """v0.10.1: 字幕后处理（4 步管线）。

        1. 开头标点修正: 如果块以 ，、。！？； 开头，将该标点移到上一块末尾
        2. 末尾标点去除: 去掉每个块末尾的标点符号
        3. 跨块引号清理: 两遍匹配 — 块内配对优先，跨块未配对引号删除
        4. 再次去除标点: 引号删除后可能暴露新的末尾/开头标点
        """
        if not blocks:
            return blocks

        # --- Step 1: 开头标点修正 ---
        LEADING_PUNCT = frozenset("，、。！？；.!?;")
        fixed = [blocks[0]]
        for b in blocks[1:]:
            if b and b[0] in LEADING_PUNCT:
                # 把开头标点移到上一块末尾
                fixed[-1] = fixed[-1] + b[0]
                b = b[1:]
            if b:  # 可能移走后变空
                fixed.append(b)
        blocks = fixed

        # --- Step 2: 末尾标点去除 ---
        blocks = [b.rstrip("。！？；，、.!?;…\n") if b else b for b in blocks]
        # 过滤空块
        blocks = [b for b in blocks if b.strip()]

        # --- Step 3: 跨块引号清理（两遍匹配）---
        LEFT_QUOTES = {q[0] for q in _CROSS_BLOCK_QUOTES}
        RIGHT_QUOTES = {q[1] for q in _CROSS_BLOCK_QUOTES}
        _Q_MAP = {}
        for lq, rq in _CROSS_BLOCK_QUOTES:
            _Q_MAP[lq] = rq
            _Q_MAP[rq] = lq

        # 收集所有引号位置
        quote_positions = []  # (block_idx, char_idx, quote_char)
        for bi, block in enumerate(blocks):
            for ci, ch in enumerate(block):
                if ch in LEFT_QUOTES or ch in RIGHT_QUOTES:
                    quote_positions.append((bi, ci, ch))

        if not quote_positions:
            return blocks

        matched = set()  # 已匹配的 (block_idx, char_idx)

        # Pass 1: 块内匹配 — 同一块内的配对引号优先匹配
        for bi, block in enumerate(blocks):
            stack = []  # (char_idx, quote_char)
            for ci, ch in enumerate(block):
                if ch in LEFT_QUOTES:
                    stack.append((ci, ch))
                elif ch in RIGHT_QUOTES:
                    expected_left = _Q_MAP.get(ch)
                    if stack and stack[-1][1] == expected_left:
                        prev_ci, _ = stack.pop()
                        matched.add((bi, prev_ci))
                        matched.add((bi, ci))

        # Pass 2: 跨块匹配 — 对剩余未匹配的引号做全局栈匹配
        remaining = [(bi, ci, ch) for bi, ci, ch in quote_positions if (bi, ci) not in matched]
        stack = []  # (block_idx, char_idx, quote_char)
        cross_matched = set()
        for bi, ci, ch in remaining:
            if ch in LEFT_QUOTES:
                stack.append((bi, ci, ch))
            elif ch in RIGHT_QUOTES:
                expected_left = _Q_MAP.get(ch)
                found = None
                for si in range(len(stack) - 1, -1, -1):
                    if stack[si][2] == expected_left:
                        found = si
                        break
                if found is not None:
                    cross_matched.add((stack[found][0], stack[found][1]))
                    cross_matched.add((bi, ci))
                    stack.pop(found)

        # 跨块匹配成功的引号 → 删除（因为配对分在不同块中）
        # 块内匹配成功的引号 → 保留
        # 完全未匹配的引号 → 删除
        to_remove = set()
        # 未匹配且不在 cross_matched 中的 → 删除
        for bi, ci, ch in quote_positions:
            if (bi, ci) in matched:
                continue  # 块内配对，保留
            if (bi, ci) in cross_matched:
                to_remove.add((bi, ci))  # 跨块配对，删除两个
            else:
                to_remove.add((bi, ci))  # 未配对，删除

        if to_remove:
            remove_by_block = {}
            for bi, ci in to_remove:
                remove_by_block.setdefault(bi, set()).add(ci)
            new_blocks = []
            for bi, block in enumerate(blocks):
                if bi in remove_by_block:
                    indices = remove_by_block[bi]
                    new_block = "".join(ch for ci, ch in enumerate(block) if ci not in indices)
                    new_blocks.append(new_block)
                else:
                    new_blocks.append(block)
            blocks = [b for b in new_blocks if b.strip()]

        # --- Step 4: 引号清理后再次去除末尾/开头标点 ---
        # 删除引号后，原本紧挨引号的标点可能暴露为新的末尾/开头
        LEADING_PUNCT2 = frozenset("，、。！？；.!?:;")
        blocks = [b.rstrip("。！？；，、.!?;…\n") if b else b for b in blocks]
        # 开头标点修正（再来一次）
        if len(blocks) >= 2:
            fixed2 = [blocks[0]]
            for b in blocks[1:]:
                if b and b[0] in LEADING_PUNCT2:
                    fixed2[-1] = fixed2[-1] + b[0]
                    b = b[1:]
                if b:
                    fixed2.append(b)
            blocks = fixed2
        blocks = [b for b in blocks if b.strip()]

        return blocks

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
