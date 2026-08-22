"""Subtitle segmenter (Layer 3) — 对齐《字幕分割规范 v1.2》。

见 docs/subtitle-segmentation-spec.md（双实现共享：smart-sentence-splitter Python
与 Multi-Publish story2video-engine TypeScript 输出同一字幕块序列）。

规范 7 步流水线（顺序固定）：
  Step 1 分句边界保留（句子优先，块不跨句）
  Step 2 引号感知预分割（说话内容/叙述分离）
  Step 3 长度切分（标点优先 + 配对引号保护，min/max；顿号枚举单元整体保护 v1.1）
  Step 4 短块合并（前块 <min / 纯标点短块 / 短尾）
  Step 5 标点规范化（trim → 开头修正 → 末尾去除 → 跨块引号清理 → 再去除）
  Step 6 超长强制分割（平衡切分 + 顿号枚举整体切分）
  Step 7 时间戳分配（proportional / equal；half-up 舍入保留 2 位小数）

规则单源：所有字符集/参数/舍入模式从 subtitle_rules.json 加载
（Multi-Publish 仓库存同步副本，两实现不得再手写硬编码规则）。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import List

from ..models import SubtitleBlock, SceneSegment

# ── 规则单源（subtitle_rules.json，双实现共享）────────────────────────────
_RULES = json.loads((Path(__file__).resolve().parent / "subtitle_rules.json").read_text(encoding="utf-8"))

# 默认配置（规范 3：非法配置回退默认）
DEFAULT_MIN_CHARS = int(_RULES["defaults"]["min_chars_per_block"])
DEFAULT_MAX_CHARS = int(_RULES["defaults"]["max_chars_per_block"])
MAX_CHARS_CAP = int(_RULES["defaults"]["max_chars_cap"])

# Step 1 句界字符（归属前块）
SENTENCE_BOUNDARY = set(_RULES["sentence_boundary"])

# Step 3 优先级标点（空格/换行单独判定）
PRIORITY_PUNCT = set(_RULES["priority_punct"])

# Step 3/6 顿号枚举单元保护（v1.1）：
# 枚举结束判定的更高优先级标点（顿号之上，含全角逗号）
ENUM_HIGHER_PUNCT = set(_RULES["enum"]["higher_punct"])
# 枚举结束判定的谓词/主语引导词（常见分句起始字，启发式）
ENUM_PREDICATE_STARTERS = set(_RULES["enum"]["predicate_starters"])
# 枚举项连接词（顿号项之间可含 和/及/与 连接末项）
ENUM_CONNECTORS = set(_RULES["enum"]["connectors"])

# Step 5 开头修正标点
LEADING_PUNCT = set(_RULES["leading_punct"])

# Step 5 末尾去除标点
TRAILING_PUNCT = set(_RULES["trailing_punct"])

# Step 2 / Step 5 配对引号
QUOTE_PAIRS = [tuple(pair) for pair in _RULES["quote_pairs"]]
LEFT_QUOTES = {p[0] for p in QUOTE_PAIRS}
RIGHT_QUOTES = {p[1] for p in QUOTE_PAIRS}
QUOTE_MAP = dict(QUOTE_PAIRS)

# 时间戳保留 2 位小数：四舍五入（half-up）——与 TypeScript Math.round(x*100)/100 语义一致（v0.15.1）
# 背景：Python round() 为银行家舍入（0.625→0.62），JS 为四舍五入（0.625→0.63），差分测试证实
# 两实现会在 .xx5 边界产生 0.01s 级分歧（等分场景累计 0.15s），故统一为 half-up。
ROUND_DECIMALS = int(_RULES["rounding"]["decimal_places"])

# Step 3/6 词边界感知切分（v1.2）：无标点硬切/平衡切分时优先在不劈词的位置切分。
# 切点判定 = 块首为连词/介词（引导短语）或块尾为助词/副词/句内标点（收束）；
# 块首为强黏着后缀时排除（避免 "扶余|国"、"电|视剧" 类劈词）。
WORD_GOOD_LEAD = set(_RULES["word_split"]["good_lead"])
WORD_GOOD_TAIL = set(_RULES["word_split"]["good_tail"])
WORD_BAD_FOLLOWERS = set(_RULES["word_split"]["bad_followers"])
# v1.2.2：good_tail 路径的块首排除集（仅纯黏着后缀，如 "个|性" 的 性）。
# 与 bad_followers（第二趟非黏着切点用）分离：电/视/剧/这 等虽在 bad_followers，
# 但 "的|电视…"、"是|这位…" 是好切点，不能被误伤。
WORD_GOOD_TAIL_BLOCKERS = set(_RULES["word_split"].get("good_tail_blockers", ""))
# v1.2.3：成词保护（兼容字段名 no_cut_bigrams）——项目可以是任意长度短语，
# 切点不得落在任一短语内部（如 "蒙古"、"江南"、"包税人"）。
WORD_NO_CUT_PHRASES = set(_RULES["word_split"].get("no_cut_bigrams", []))


def _round2_half_up(x: float) -> float:
    """保留 2 位小数，四舍五入（half-up）。"""
    factor = 10**ROUND_DECIMALS
    return math.floor(x * factor + 0.5) / factor


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

    @staticmethod
    def _is_number_dot(text: str) -> bool:
        """当前累积文本以 数字+半角点 结尾（如 "713."）→ 该 "." 是小数点/数字一部分，不是句界。

        v1.2.3：半角点同时是句界/标点集成员，直接套用会把 "降雨量狂飙到一天713.3毫米" 劈成 "713."+"3毫米"。
        """
        return len(text) >= 2 and text[-1] == "." and text[-2].isdigit()

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
            if ch in SENTENCE_BOUNDARY and not stack and not self._is_number_dot(cur):
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
            # v1.2.3：数字中的小数点（如 713.3）不是切分标点
            if is_punct and len(cur) >= self.min_chars and not (ch == "." and len(cur) >= 2 and cur[-2].isdigit()):
                blocks.append(cur)
                cur = ""
                last_hard_cut = False
            elif len(cur) >= self.max_chars and not stack:
                pos = self._apply_enumeration_shift(cur, self._find_split_pos(cur), require_tail_min=False)
                pos = self._safe_cut_position(cur, pos)
                if pos > 0:
                    blocks.append(cur[:pos])
                    cur = cur[pos:]
                    last_hard_cut = False
                else:
                    # v1.2 词边界感知：无标点硬切时优先不劈词（区间内找好切点/非黏着切点）
                    ws = self._word_safe_split(
                        cur,
                        max(1, len(cur) - self.max_chars - 1),
                        len(cur) - 1,
                        min_head=self.min_chars,
                        tail_min=self.min_chars,
                    )
                    pos = self._safe_cut_position(cur, ws if ws > 0 else len(cur))
                    if pos <= 0:
                        continue
                    blocks.append(cur[:pos])
                    cur = cur[pos:]
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
                    # v1.2.2 词边界感知让字：区间内无标点时，向 lo 左侧找不劈词的好切点
                    # （避免把 "…从文化认|同滑向…" 的 "同" 硬让出劈开 "文化认同"）。
                    ws = self._word_safe_split(prev, 1, lo, min_head=1)
                    pos = ws if ws > 0 else lo
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
                if text[i] == "." and (
                    (i > 0 and text[i - 1].isdigit()) or (i + 1 < len(text) and text[i + 1].isdigit())
                ):
                    continue  # v1.2.3：数字中的小数点不是切分锚点
                return i + 1
        for i in range(len(text) - 1, -1, -1):
            if text[i] in (" ", "\n", "\u3000"):
                return i + 1
        for i in range(len(text) - 1, -1, -1):
            if text[i] == "、":
                return i + 1
        return -1

    @staticmethod
    def _clean_len(text: str) -> int:
        """剥离尾部标点后的长度（Step 4 短块判定用，v1.2）。"""
        return len(text.strip().rstrip("".join(TRAILING_PUNCT)))

    @staticmethod
    def _protected_phrase_span_at_boundary(text: str, i: int):
        """返回切点所在的受保护短语跨度；切点恰在短语两端时安全。"""
        if i <= 0 or i >= len(text):
            return None
        for phrase in WORD_NO_CUT_PHRASES:
            if not phrase or len(phrase) < 2:
                continue
            start = text.find(phrase)
            while start >= 0:
                end = start + len(phrase)
                if start < i < end:
                    return phrase, start, end
                if start >= i:
                    break
                start = text.find(phrase, start + 1)
        return None

    @staticmethod
    def _protected_phrase_prefix_at_end(text: str):
        """返回文本末尾尚未完整出现的受保护短语前缀，避免流式累积在前缀中间切断。"""
        best = None
        for phrase in WORD_NO_CUT_PHRASES:
            if not phrase or len(phrase) < 2:
                continue
            for prefix_length in range(1, len(phrase)):
                if text.endswith(phrase[:prefix_length]) and (best is None or prefix_length > best[2]):
                    best = phrase, len(text) - prefix_length, prefix_length
        return best

    @classmethod
    def _safe_cut_position(cls, text: str, i: int) -> int:
        """将候选切点移到受保护短语外，保证字幕块边界不落在短语内部。"""
        span = cls._protected_phrase_span_at_boundary(text, i)
        if span is not None:
            return span[1] if span[1] > 0 else span[2]
        prefix = cls._protected_phrase_prefix_at_end(text)
        if prefix is not None and i >= prefix[1]:
            return prefix[1] if prefix[1] > 0 else 0
        return i

    @staticmethod
    def _is_good_cut(text: str, i: int) -> bool:
        """词边界好切点：切点后为连词/介词（块首引导），或切点前为助词/副词/句内标点（块尾收束）。

        v1.2.2：块尾收束路径（text[i-1] 为收束字）额外要求切点后首字符非强黏着后缀
        （good_tail_blockers），避免 "…保持个|性独立" 类劈词（"个" 入 good_tail 后 "个性" 被拆）；
        只用独立排除集而非 bad_followers，避免误伤 "的|电视…"、"是|这位…" 等好切点。
        v1.2.3：切点落在任意长度成词短语内部一律不是好切点。
        """
        if i >= len(text):
            return False
        if SubtitleSegmenter._protected_phrase_span_at_boundary(text, i):
            return False
        if text[i] in WORD_GOOD_LEAD:
            return True
        return i > 0 and text[i - 1] in WORD_GOOD_TAIL and text[i] not in WORD_GOOD_TAIL_BLOCKERS

    @classmethod
    def _word_safe_split(cls, text: str, lo: int, hi: int, min_head: int = 1, tail_min: int = 0) -> int:
        """在 [lo, hi] 内找不劈词的切点索引；-1 表示无（v1.2）。

        策略（优先级）：
        - 好切点从后往前找（头块尽量长），要求头块 >= min_head 且排除孤悬 ≤3 字短尾；
          v1.2.2 软约束：头块欠长但 >= min_head-2 且尾块 >= tail_min 时仍接受
          （如 "里面讲述的正是|这位…" 7 字头块 + 9 字尾块，避免劈 "这位"；
           而 "新加坡现在|越来越…" 5 字头块仍拒绝，避免 5 字短头块）；
        - 非黏着后缀切点从前往后找，要求头块 >= min_head（防过度前移劈出过短头块，
          如 "一只银灰色小猫蜷在|摊开的笔记本" 不切 "一|只银灰…"）；
        - 无则 -1，回退算术/标点切分。
        """
        fallback = -1
        for i in range(hi, lo - 1, -1):
            tail = len(text) - i
            if not (i >= min_head or (tail_min > 0 and i >= min_head - 2 and tail >= tail_min)):
                continue
            if not cls._is_good_cut(text, i):
                continue
            if tail > 3 and (tail_min == 0 or tail >= tail_min or tail >= 5 or text[i] in WORD_GOOD_LEAD):
                return i
            # v1.2.3 孤悬尾防护（仅 tail==4 且块首非连词/介词）："着|脖" 劈 "脖子" → 前移找 tail 达标点
            # （"新加坡华人也不想|被掐着…" tail=8）；找不到再回退。
            # "人|为"（为∈good_lead 引导短语）、"个|西"（tail=6）、"能|多"（tail=7）直接接受，不误伤。
            if fallback < 0 and tail == 4 and text[i] not in WORD_GOOD_LEAD and (i == 0 or not text[i - 1].isdigit()):
                fallback = i
        if fallback >= 0:
            return fallback
        for i in range(max(lo, min_head), hi + 1):
            if (
                i < len(text)
                and text[i] not in WORD_BAD_FOLLOWERS
                and (i == 0 or not text[i - 1].isdigit())
                and not cls._protected_phrase_span_at_boundary(text, i)
            ):
                return i
        return -1

    def _merge_short(self, blocks: List[str]) -> List[str]:
        """Step 4：短块合并（v1.2 修复机制三 + 防过度并入）。

        - 判定统一使用 clean 后长度（剥离尾部标点），避免 Step 5 剥标点后块变短无法补救；
        - 并入条件：合并后长度 <= max_chars，否则保持独立短块（由 short_block_exceptions 声明）；
        - 句界结尾（。！？…）的块是完整句，不并入前块。
        """
        if not blocks:
            return blocks
        merged = [blocks[0]]
        for b in blocks[1:]:
            b_stripped = b.strip()
            b_clean_len = self._clean_len(b)
            prev_clean_len = self._clean_len(merged[-1])
            is_punct_tail = len(b_stripped) <= 2 and all(
                c in TRAILING_PUNCT or c in LEFT_QUOTES or c in RIGHT_QUOTES for c in b_stripped
            )
            is_short_tail = b_clean_len <= 3 and prev_clean_len >= self.min_chars
            is_sentence_end = bool(b_stripped) and b_stripped[-1] in SENTENCE_BOUNDARY and b_clean_len > 3
            merged_len = prev_clean_len + b_clean_len
            if is_sentence_end:
                merged.append(b)
            elif (
                prev_clean_len < self.min_chars or is_punct_tail or is_short_tail or b_clean_len < self.min_chars
            ) and merged_len <= self.max_chars:
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
                pos = self._safe_cut_position(b, pos)
                if any(phrase == b for phrase in WORD_NO_CUT_PHRASES):
                    # 保护短语本身可能比 max_chars 更长；完整短语优先于违反长度上限。
                    out.append(b)
                    b = ""
                    break
                if pos <= 0 or pos >= len(b):
                    pos = self.max_chars
                # 固定长度兜底后再次检查，避免兜底切点落回受保护短语内部。
                pos = self._safe_cut_position(b, pos)
                if pos <= 0 or pos >= len(b):
                    pos = min(self.max_chars, len(b) - 1)
                # 平衡约束：尾块 < min_chars 时前移切分点（v1.2：词边界感知 + 越界修复）
                if len(b) - pos < self.min_chars:
                    min_pos = max(1, len(b) - self.min_chars)
                    hi = len(b) - 1
                    ws = self._word_safe_split(b, min_pos, hi, min_head=min_pos, tail_min=self.min_chars)
                    if ws > 0 and ws < len(b):
                        pos = self._safe_cut_position(b, ws)
                    else:
                        # 越界修复：balanced == len(b)（尾字符恰为标点时 i+1 越界）视为无效
                        balanced = self._find_split_pos_in_range(b, min_pos, hi)
                        pos = balanced if 0 < balanced < len(b) else min_pos
                        pos = self._safe_cut_position(b, pos)
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
        # v1.2.1 守卫：枚举单元扫到块尾仍无终止、且内部无更多顿号项时，疑似把谓语吞进
        # 枚举末项（如 "呐喊声混成一锅滚" 被整段吞并 → 15+3 劈词孤尾），不吞并回退锚点。
        if eend == len(text) and "、" not in text[pos:eend]:
            return pos
        if eend > pos and eend <= self.max_chars:
            if not require_tail_min or len(text) - eend >= self.min_chars:
                return eend
        return pos

    @staticmethod
    def _find_split_pos_in_range(text: str, lo: int, hi: int) -> int:
        """在 [lo, hi] 范围内从后往前找最近优先级标点/空格（返回切后索引；无则 -1）。"""
        for i in range(hi, lo - 1, -1):
            if text[i] in PRIORITY_PUNCT:
                if text[i] == "." and (
                    (i > 0 and text[i - 1].isdigit()) or (i + 1 < len(text) and text[i + 1].isdigit())
                ):
                    continue  # v1.2.3：数字中的小数点不是切分锚点
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
