"""Subtitle segmenter (Layer 3) — 对齐《字幕分割规范 v1.0》。

见 docs/subtitle-segmentation-spec.md（双实现共享：smart-sentence-splitter Python
与 Multi-Publish story2video-engine TypeScript 输出同一字幕块序列）。

规范 7 步流水线（顺序固定）：
  Step 1 分句边界保留（句子优先，块不跨句）
  Step 2 引号感知预分割（说话内容/叙述分离）
  Step 3 长度切分（标点优先 + 配对引号保护，min/max）
  Step 4 短块合并（前块 <min / 纯标点短块 / 短尾）
  Step 5 标点规范化（trim → 开头修正 → 末尾去除 → 跨块引号清理 → 再去除）
  Step 6 超长强制分割
  Step 7 时间戳分配（proportional / equal）

配置（兼容旧键）：min_chars_per_block / max_chars_per_block / time_calculation_method。
"""

from __future__ import annotations
from typing import List

from ..models import SubtitleBlock, SceneSegment

# ── 规范常量 ─────────────────────────────────────────────
DEFAULT_MIN_CHARS = 8
DEFAULT_MAX_CHARS = 15

# Step 1 句界字符（归属前块）
SENTENCE_BOUNDARY = set("。！？…!?.")

# Step 3 优先级标点（空格/换行单独判定）
PRIORITY_PUNCT = set("。！？；.!?;，,、")

# Step 5 开头修正标点
LEADING_PUNCT = set("，、。！？；,!?;.")

# Step 5 末尾去除标点
TRAILING_PUNCT = set("。！？；，、.!?;…")

# Step 2 / Step 5 配对引号
QUOTE_PAIRS = [
    ("\u201c", "\u201d"),  # " "
    ("\u2018", "\u2019"),  # ' '
    ("\u300c", "\u300d"),  # 「 」
    ("\u300e", "\u300f"),  # 『 』
    ("\u300a", "\u300b"),  # 《 》
    ("\uff08", "\uff09"),  # （ ）
    ("\u3010", "\u3011"),  # 【 】
    ("[", "]"),
    ('"', '"'),
    ("'", "'"),
]
LEFT_QUOTES = {p[0] for p in QUOTE_PAIRS}
RIGHT_QUOTES = {p[1] for p in QUOTE_PAIRS}
QUOTE_MAP = dict(QUOTE_PAIRS)


class SubtitleSegmenter:
    """字幕级分割器 — 按《字幕分割规范 v1.0》实现。"""

    def __init__(self, config: dict = None):
        config = config or {}
        self.min_chars = int(config.get("min_chars_per_block", DEFAULT_MIN_CHARS))
        self.max_chars = int(config.get("max_chars_per_block", DEFAULT_MAX_CHARS))
        # 规范 3：配置合法性，非法回退默认
        if not (1 <= self.min_chars <= self.max_chars):
            self.min_chars, self.max_chars = DEFAULT_MIN_CHARS, DEFAULT_MAX_CHARS
        if self.max_chars > 64:
            self.max_chars = 64
        if self.min_chars > self.max_chars:
            self.min_chars = self.max_chars
        self.time_method = config.get("time_calculation_method", "proportional")

    def segment(self, scene: SceneSegment) -> List[SubtitleBlock]:
        """为单个 SceneSegment 生成字幕块（规范流水线）。"""
        text = (scene.text or "").strip()
        if not text:
            return []
        blocks = self._split_to_blocks(text)
        return self._assign_timestamps(blocks, scene.estimated_duration, scene.segment_id)

    # ── 主流程（Step 1-6）───────────────────────────────
    def _split_to_blocks(self, text: str) -> List[str]:
        """Step 1-6：分句 → 引号 → 长度 → 合并 → 标点 → 强制。"""
        all_blocks: List[str] = []
        for sentence in self._split_sentences(text):  # Step 1
            for fragment in self._split_quote_boundaries(sentence):  # Step 2
                blocks = self._length_split(fragment)  # Step 3
                blocks = self._merge_short(blocks)  # Step 4
                blocks = self._clean(blocks)  # Step 5
                blocks = self._enforce_max(blocks)  # Step 6
                blocks = self._clean(blocks)  # Step 6 后清理：强制切分可能产生新孤立引号/标点
                all_blocks.extend(blocks)
        # 规范 3：过滤空块与纯标点块（含孤立引号）
        return [
            b
            for b in all_blocks
            if b.strip() and not all(c in TRAILING_PUNCT or c in LEFT_QUOTES or c in RIGHT_QUOTES for c in b)
        ]

    def _split_sentences(self, text: str) -> List[str]:
        """Step 1：按句界切分（句界字符归属前块）；未闭合引号内的句界不生效（保护引号配对）。"""
        sentences: List[str] = []
        cur = ""
        stack: List[str] = []
        for ch in text:
            cur += ch
            if ch in LEFT_QUOTES:
                stack.append(ch)
            elif ch in RIGHT_QUOTES and stack and QUOTE_MAP.get(stack[-1]) == ch:
                stack.pop()
            if ch in SENTENCE_BOUNDARY and not stack:
                sentences.append(cur)
                cur = ""
        if cur:
            sentences.append(cur)
        return [s for s in sentences if s.strip()]

    def _split_quote_boundaries(self, text: str) -> List[str]:
        """Step 2：闭引号后切分，且引号内容 ≥ min_chars 才切；短引号内容并入上下文。

        规则（规范 v1.0）：
        - 维护引号栈；外层配对闭合时，若引号内内容长度 ≥ min_chars，则在闭引号后切分；
        - 引号内容 < min_chars 不切分（避免产生孤立引号/说话人引导短块）；
        - 未闭合引号（句尾裸开引号）不切分，交由后续步骤处理。
        """
        fragments: List[str] = []
        cur = ""
        stack: List[tuple] = []  # (quote_char, content_start_index_in_cur)
        for ch in text:
            if ch in LEFT_QUOTES:
                stack.append((ch, len(cur)))
                cur += ch
            elif ch in RIGHT_QUOTES and stack and QUOTE_MAP.get(stack[-1][0]) == ch:
                _, start = stack.pop()
                content_len = len(cur) - start - 1  # 引号内内容长度（不含开引号）
                cur += ch
                if not stack and content_len >= self.min_chars:
                    fragments.append(cur)
                    cur = ""
            else:
                cur += ch
        if cur.strip():
            fragments.append(cur)
        return [f for f in fragments if f.strip()]

    def _length_split(self, text: str) -> List[str]:
        """Step 3：逐字符累积；优先级标点且 ≥min 即切；≥max 强制切（标点/空格/硬切）；配对引号保护。"""
        blocks: List[str] = []
        cur = ""
        stack: List[str] = []
        for ch in text:
            cur += ch
            if ch in LEFT_QUOTES:
                stack.append(ch)
            elif ch in RIGHT_QUOTES and stack and QUOTE_MAP.get(stack[-1]) == ch:
                stack.pop()
            is_punct = ch in PRIORITY_PUNCT or ch in (" ", "\n", "\u3000")
            if is_punct and len(cur) >= self.min_chars:
                blocks.append(cur)
                cur = ""
            elif len(cur) >= self.max_chars and not stack:
                pos = self._find_split_pos(cur)
                if pos > 0:
                    blocks.append(cur[:pos])
                    cur = cur[pos:]
                else:
                    blocks.append(cur)
                    cur = ""
            elif len(cur) >= self.max_chars * 2 and stack:
                blocks.append(cur)
                cur = ""
                stack = []
        if cur:
            blocks.append(cur)
        return [b for b in blocks if b.strip()]

    @staticmethod
    def _find_split_pos(text: str) -> int:
        """从后往前找最近优先级标点/空格的分割位置（返回切后索引；无则 -1）。"""
        for i in range(len(text) - 1, -1, -1):
            if text[i] in PRIORITY_PUNCT:
                return i + 1
        for i in range(len(text) - 1, -1, -1):
            if text[i] in (" ", "\n", "\u3000"):
                return i + 1
        return -1

    def _merge_short(self, blocks: List[str]) -> List[str]:
        """Step 4：前块 <min 合并；纯标点短块（≤2）并入前块；短尾（≤3 且前块 ≥min）并入前块。"""
        if not blocks:
            return blocks
        merged = [blocks[0]]
        for b in blocks[1:]:
            b_stripped = b.strip()
            is_punct_tail = len(b_stripped) <= 2 and all(
                c in TRAILING_PUNCT or c in LEFT_QUOTES or c in RIGHT_QUOTES for c in b_stripped
            )
            is_short_tail = len(b_stripped) <= 3 and len(merged[-1]) >= self.min_chars
            if len(merged[-1]) < self.min_chars or is_punct_tail or is_short_tail:
                merged[-1] = merged[-1] + b
            else:
                merged.append(b)
        return [b for b in merged if b.strip()]

    def _clean(self, blocks: List[str]) -> List[str]:
        """Step 5：trim → 开头标点修正 → 跨块引号清理（先删引号暴露标点）→ 末尾标点去除 → 再去除。

        顺序要点：必须先清理跨块引号，否则 rstrip 会被孤立引号挡住（如 “。” 的 “。” 在引号后）。
        """
        blocks = [b.strip() for b in blocks if b.strip()]
        if not blocks:
            return []
        # 子步 1：开头标点修正（首块开头标点删除，后续块开头标点前移）
        fixed = [blocks[0]]
        if fixed[0] and fixed[0][0] in LEADING_PUNCT:
            fixed[0] = fixed[0][1:]
        for b in blocks[1:]:
            if b and b[0] in LEADING_PUNCT and fixed[-1]:
                fixed[-1] = fixed[-1] + b[0]
                b = b[1:]
            if b:
                fixed.append(b)
        blocks = [b for b in fixed if b.strip()]
        # 子步 2：跨块引号清理（块内成对保留，未配对删除）— 必须先于末尾标点去除
        blocks = self._clean_cross_quotes(blocks)
        # 子步 3：末尾标点去除（引号已清理，标点可被 rstrip 命中）
        blocks = [b.rstrip("".join(TRAILING_PUNCT)) for b in blocks]
        blocks = [b for b in blocks if b.strip()]
        # 子步 4：再去除（开头修正 + trim）
        out = []
        for b in blocks:
            nb = b
            if nb and nb[0] in LEADING_PUNCT and out:
                out[-1] = out[-1] + nb[0]
                nb = nb[1:]
            nb = nb.rstrip("".join(TRAILING_PUNCT)).strip()
            if nb:
                out.append(nb)
        return out

    def _clean_cross_quotes(self, blocks: List[str]) -> List[str]:
        """Step 5 子步 3：块内成对引号保留；孤立（跨块）引号删除。"""
        out: List[str] = []
        for b in blocks:
            out.append(self._drop_unpaired_quotes(b))
        return [b for b in out if b.strip()]

    @staticmethod
    def _drop_unpaired_quotes(text: str) -> str:
        """删除文本中未配对的引号（块内成对保留）。"""
        stack: List[int] = []
        drop = [False] * len(text)
        for i, ch in enumerate(text):
            if ch in LEFT_QUOTES:
                stack.append(i)
            elif ch in RIGHT_QUOTES:
                if stack and QUOTE_MAP.get(text[stack[-1]]) == ch:
                    stack.pop()
                else:
                    drop[i] = True
        for idx in stack:
            drop[idx] = True
        return "".join(ch for i, ch in enumerate(text) if not drop[i])

    def _enforce_max(self, blocks: List[str]) -> List[str]:
        """Step 6：清理后仍 > max_chars 的块强制切分（标点优先，无标点硬切）。

        注意：切分点必须在块内部（pos < len），块尾标点不作为切分锚点
        （块尾标点由 Step 5 去除，且依赖它切分会产生无效零长度切分）。
        """
        out: List[str] = []
        for b in blocks:
            while len(b) > self.max_chars:
                pos = self._find_split_pos(b)
                if pos <= 0 or pos >= len(b):
                    pos = self.max_chars
                out.append(b[:pos])
                b = b[pos:]
            if b:
                out.append(b)
        return out

    # ── Step 7 时间戳 ───────────────────────────────────
    def _assign_timestamps(self, blocks: List[str], parent_duration: float, parent_id: int) -> List[SubtitleBlock]:
        n = len(blocks)
        if n == 0:
            return []
        if self.time_method == "equal":
            durs = [parent_duration / n] * n
        else:
            total = sum(len(b) for b in blocks)
            durs = [(len(b) / total * parent_duration) if total else parent_duration / n for b in blocks]
        subs: List[SubtitleBlock] = []
        t = 0.0
        for i, b in enumerate(blocks):
            d = round(durs[i], 2)
            subs.append(
                SubtitleBlock(
                    text=b,
                    display_order=i,
                    start_time=round(t, 2),
                    duration=d,
                    parent_segment_id=parent_id,
                )
            )
            t += durs[i]
        return subs
