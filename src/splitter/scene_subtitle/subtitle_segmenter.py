"""Subtitle segmenter (Layer 3).

将 SceneSegment 内的文本切分为 8-15 字的字幕块。

v0.9.2 改动: 复用 LengthSegmenter 配对引号保护 — 不再自己实现切分。
v0.10.1 改动: 字幕后处理 — 末尾标点去除、跨块引号清理、开头标点修正。
v0.11.0 改动: 引号感知预分割 + 超长块强制再分割 + 诊断日志。
"""

from __future__ import annotations
from typing import List
import logging

from ..models import SubtitleBlock, SceneSegment

logger = logging.getLogger(__name__)

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

        # v0.11.0: 引号感知预分割 — 在引号边界处切分，避免说话内容与叙述粘连
        fragments = self._split_at_quote_boundaries(text)
        has_quotes = len(fragments) > 1

        # 对每个片段独立做字数切分
        blocks: List[str] = []
        for frag in fragments:
            frag_blocks = self._length_seg.split_text(frag)
            if not frag_blocks:
                frag_blocks = [frag]
            blocks.extend(frag_blocks)

        # v0.11.0: 诊断日志 — 检测超长块
        for b in blocks:
            if len(b) > self.max_chars * 2:
                logger.warning(
                    f"Block too long after split: {len(b)} chars: {b[:30]}..."
                )

        # 后处理: 把太短的首块合并到上一块, 末尾太短合并到上一块
        # v0.11.0: 有引号分割时跳过合并，避免引号内容与叙述粘连
        if not has_quotes:
            blocks = self._merge_short(blocks)

        # v0.10.1: 字幕后处理 — 开头标点修正、末尾标点去除、跨块引号清理
        blocks = self._clean_subtitle_blocks(blocks)

        # v0.11.0: 超长块强制再分割 — 清理/合并后仍超 max_chars 的块强制再切
        blocks = self._enforce_max_length(blocks)

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

    # v0.11.0: 引号感知预分割
    _QUOTE_PAIRS = [
        ('\u201c', '\u201d'),  # " "
        ('\u300c', '\u300d'),  # 「 」
        ('"', '"'),
        ("'", "'"),
    ]

    def _split_at_quote_boundaries(self, text: str) -> List[str]:
        """v0.11.0 R1: 在引号边界处预分割文本。

        规则:
        - 每对引号（含内部标点）作为一个独立片段
        - 引号后的叙述文字作为另一个片段
        - 避免引号内容跨越 LengthSegmenter 的 max_chars 窗口导致配对锁定

        示例:
        - '"不对，"宴会散后...' → ['"不对，"', '宴会散后...']
        - '"异教徒！"他们狞笑着。' → ['"异教徒！"', '他们狞笑着。']
        - '质问："天朝...？' → ['质问：', '"天朝...？']
        """
        if not text:
            return [text] if text else []

        # 找到所有引号对的 (start, end) 位置
        quote_spans = []  # (start_idx, end_idx) inclusive
        for lq, rq in self._QUOTE_PAIRS:
            i = 0
            while i < len(text):
                l = text.find(lq, i)
                if l < 0:
                    break
                r = text.find(rq, l + 1)
                if r < 0:
                    break  # 未闭合引号，跳过
                quote_spans.append((l, r))
                i = r + 1

        if not quote_spans:
            return [text]

        # 按起始位置排序
        quote_spans.sort()

        # 在每个引号对的闭合引号后切分
        # 切分点 = 闭合引号位置 + 1（含闭合引号后的紧跟标点）
        fragments = []
        prev_end = 0

        for start, end in quote_spans:
            # 引号前的文本（叙述部分）
            if start > prev_end:
                before = text[prev_end:start]
                if before.strip():
                    fragments.append(before)

            # 引号内的内容（含引号）
            quote_content = text[start:end + 1]
            # 检查闭合引号后是否有紧跟的标点（如 ？！，）
            after_pos = end + 1
            if after_pos < len(text) and text[after_pos] in _TRAILING_PUNCT:
                quote_content += text[after_pos]
                after_pos += 1
            fragments.append(quote_content)
            prev_end = after_pos

        # 剩余文本（最后一个引号后的叙述）
        if prev_end < len(text):
            remaining = text[prev_end:]
            if remaining.strip():
                fragments.append(remaining)

        return fragments if fragments else [text]

    def _enforce_max_length(self, blocks: List[str]) -> List[str]:
        """v0.11.0 R2: 清理后仍超过 max_chars 的块，强制用标点再分。

        逻辑:
        1. 遍历每个块，如果 len > max_chars
        2. 在块内找优先级标点切分
        3. 找不到标点时，在 max_chars 位置硬切
        4. 短尾合并到前一块
        """
        SPLIT_PUNCT = frozenset("，、。！？；：.!?;:")
        result = []

        for block in blocks:
            if len(block) <= self.max_chars:
                result.append(block)
                continue

            # 需要再分
            sub_blocks = self._force_split(block, self.max_chars, SPLIT_PUNCT)
            result.extend(sub_blocks)

        return result

    @staticmethod
    def _force_split(text: str, max_chars: int, punct_set: frozenset) -> List[str]:
        """将超长文本按标点或硬切分成 <= max_chars 的块。"""
        chunks = []
        remaining = text

        while len(remaining) > max_chars:
            # 在 remaining[:max_chars] 内找最右的优先级标点
            head = remaining[:max_chars]
            best = 0
            for i in range(len(head) - 1, -1, -1):
                if head[i] in punct_set:
                    best = i + 1  # 含标点
                    break

            if best > 0:
                chunks.append(remaining[:best])
                remaining = remaining[best:]
            else:
                # 找不到标点 — 硬切
                chunks.append(remaining[:max_chars])
                remaining = remaining[max_chars:]

        if remaining:
            # 短尾合并：仅当合并后仍 <= max_chars 时才合并
            if chunks and len(remaining) < 3 and len(chunks[-1]) + len(remaining) <= max_chars:
                chunks[-1] += remaining
            else:
                chunks.append(remaining)

        return chunks

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
