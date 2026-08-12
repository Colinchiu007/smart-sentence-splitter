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
import math
from typing import List

from ..models import SubtitleBlock, SceneSegment

# ── 规范常量 ─────────────────────────────────────────────
DEFAULT_MIN_CHARS = 8
DEFAULT_MAX_CHARS = 15

# Step 1 句界字符（归属前块）
SENTENCE_BOUNDARY = set("。！？…!?.")

# Step 3 优先级标点（空格/换行单独判定）
PRIORITY_PUNCT = set("。！？；.!?;，,、")

# 时间戳保留 2 位小数：四舍五入（half-up）——与 TypeScript Math.round(x*100)/100 语义一致（v0.15.1）
# 背景：Python round() 为银行家舍入（0.625→0.62），JS 为四舍五入（0.625→0.63），差分测试证实
# 两实现会在 .xx5 边界产生 0.01s 级分歧（等分场景累计 0.15s），故统一为 half-up。
ROUND_DECIMALS = 2


def _round2_half_up(x: float) -> float:
    """保留 2 位小数，四舍五入（half-up）。"""
    factor = 10 ** ROUND_DECIMALS
    return math.floor(x * factor + 0.5) / factor


# Step 3/6 顿号枚举单元保护（v1.1）：
# 枚举结束判定的更高优先级标点（顿号之上）
ENUM_HIGHER_PUNCT = set("。！？；…,!?;.")
# 枚举结束判定的谓词/主语引导词（常见分句起始字，启发式）
ENUM_PREDICATE_STARTERS = set("那这我就便都也很更将会要能可是有为")
# 枚举项连接词（顿号项之间可含 和/及/与 连接末项）
ENUM_CONNECTORS = set("和及与")

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
        """Step 3：逐字符累积；优先级标点且 ≥min 即切；≥max 强制切（标点/空格/硬切）；配对引号保护。

        平衡约束（与 Step 6 一致）：无标点硬切后若尾块为 4..min-1 字（超出合法 ≤3 短尾），
        从上一块让字给尾块（区间内优先标点），避免孤悬尾块（如 15+4 → 11+8）。
        """
        blocks: List[str] = []
        cur = ""
        stack: List[str] = []
        last_hard_cut = False  # 最近一次切分是否为无标点硬切
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
                last_hard_cut = False
            elif len(cur) >= self.max_chars and not stack:
                pos = self._apply_enumeration_shift(cur, self._find_split_pos(cur), require_tail_min=False)
                if pos > 0:
                    blocks.append(cur[:pos])
                    cur = cur[pos:]
                    last_hard_cut = False
                else:
                    blocks.append(cur)
                    cur = ""
                    last_hard_cut = True
            elif len(cur) >= self.max_chars * 2 and stack:
                blocks.append(cur)
                cur = ""
                stack = []
                last_hard_cut = True
        if cur:
            # 平衡约束：硬切后的尾块清理后为 4..min-1 字（非合法 ≤3 短尾）时，从上一块让字给尾块
            # （用清理后长度判断，避免把 "上打盹。"（清理后 3 字，合法短尾）误判为需要平衡）
            tail_clean = cur.strip().rstrip("".join(TRAILING_PUNCT))
            if last_hard_cut and blocks and 3 < len(tail_clean) < self.min_chars and len(blocks[-1]) >= self.min_chars:
                prev = blocks[-1]
                need = self.min_chars - len(tail_clean)
                lo = max(1, len(prev) - need)
                hi = len(prev) - 1
                pos = self._find_split_pos_in_range(prev, lo, hi)
                if pos <= 0:
                    pos = lo
                blocks[-1] = prev[:pos]
                cur = prev[pos:] + cur
            blocks.append(cur)
        return [b for b in blocks if b.strip()]

    @staticmethod
    def _find_split_pos(text: str) -> int:
        """从后往前找切分锚点（返回切后索引；无则 -1）。

        v1.1 顿号优先级最低：先找更高优先级标点（顿号除外），再找空格，最后顿号兜底——
        保证"仅当块内无更高优先级标点时才以顿号为锚点"，配合 _enumeration_end 实现枚举整体切分。
        """
        for i in range(len(text) - 1, -1, -1):
            if text[i] in PRIORITY_PUNCT and text[i] != "、":
                return i + 1
        for i in range(len(text) - 1, -1, -1):
            if text[i] in (" ", "\n", "\u3000"):
                return i + 1
        for i in range(len(text) - 1, -1, -1):
            if text[i] == "、":
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
        """Step 6：清理后仍 > max_chars 的块强制切分（标点优先，平衡切分）。

        - 切分点必须在块内部（pos < len），块尾标点不作为切分锚点；
        - 平衡约束：若尾块长度 < min_chars，切分点前移至 len(b) - min_chars
          （优先在 [len(b)-min_chars, len(b)) 区间内找最近标点），避免产生孤悬尾块
          （如 17 字块切 15+2 会让 2 字尾块成单块，应平衡切 9+8）。
        """
        out: List[str] = []
        for b in blocks:
            while len(b) > self.max_chars:
                pos = self._apply_enumeration_shift(b, self._find_split_pos(b))
                if pos <= 0 or pos >= len(b):
                    pos = self.max_chars
                # 平衡约束：尾块 < min_chars 时前移切分点
                if len(b) - pos < self.min_chars:
                    min_pos = max(1, len(b) - self.min_chars)
                    balanced = self._find_split_pos_in_range(b, min_pos, len(b) - 1)
                    pos = balanced if balanced > 0 else min_pos
                out.append(b[:pos])
                b = b[pos:]
            if b:
                out.append(b)
        return out

    @staticmethod
    def _enumeration_end(text: str, pos: int) -> int:
        """顿号枚举单元结束位置（v1.1）。

        从顿号后一字符 pos 向后扫描：枚举项以 、 分隔，可含 和/及/与 连接的末项；
        结束于：更高优先级标点、谓词/主语引导词（常见分句起始字）、或片段尾。
        返回枚举结束后的索引（切分点）；无顿号模式返回 pos。
        """
        i = pos
        n = len(text)
        while i < n:
            ch = text[i]
            if ch in ENUM_HIGHER_PUNCT or ch in ENUM_PREDICATE_STARTERS:
                return i
            i += 1
        return n

    def _apply_enumeration_shift(self, text: str, pos: int, require_tail_min: bool = True) -> int:
        """若切分锚点落在顿号上，把切分点前移到枚举单元结束之后。

        - 头块 ≤ max_chars 才生效；
        - require_tail_min=True（Step 6 完整块）：尾块 ≥ min_chars 才生效，否则交给平衡切分/回退顿号切；
        - require_tail_min=False（Step 3 累积期）：跳过尾块检查——此时 cur 还在累积，尾块长度未定型。
        """
        if pos <= 0 or pos >= len(text) or text[pos - 1] != "、":
            return pos
        eend = self._enumeration_end(text, pos)
        if eend > pos and eend <= self.max_chars:
            if not require_tail_min or len(text) - eend >= self.min_chars:
                return eend
        return pos

    @staticmethod
    def _find_split_pos_in_range(text: str, lo: int, hi: int) -> int:
        """在 [lo, hi] 范围内从后往前找最近优先级标点/空格（返回切后索引；无则 -1）。"""
        for i in range(hi, lo - 1, -1):
            if text[i] in PRIORITY_PUNCT:
                return i + 1
        for i in range(hi, lo - 1, -1):
            if text[i] in (" ", "\n", "\u3000"):
                return i + 1
        return -1

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
            d = _round2_half_up(durs[i])
            # 用舍入后的 duration 累加，保证区间严格连续（start_{i+1} = start_i + dur_i）
            subs.append(
                SubtitleBlock(
                    text=b,
                    display_order=i,
                    start_time=t,
                    duration=d,
                    parent_segment_id=parent_id,
                )
            )
            t = _round2_half_up(t + d)
        return subs
