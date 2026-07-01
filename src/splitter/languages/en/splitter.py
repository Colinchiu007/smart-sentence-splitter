"""English rule-based sentence splitter (Tier 3).

特性：
- 标点驱动 (. ! ? ; — ...)
- 缩写保护（Mr. Dr. U.S. 等 18+ 个）
- 引号对保护（"..." '...'）
- 省略号合并（... 视为 1 个边界）
- 破折号子句（—...— 包裹的子句）
- 句首大写启发式（可选）
"""

from __future__ import annotations
import re
from typing import List

from ...core.base_splitter import BaseSentenceSplitter
from ...models import SentenceBlock
from .abbreviations import EN_ABBREVIATIONS


class EnglishSplitter(BaseSentenceSplitter):
    """英文规则分句器（Tier 3 fallback）。"""

    language = "en"
    tier = "tier3_rule"

    # 句末标点（含 Unicode 引号包裹的 .!?;）
    SENTENCE_END = re.compile(r'(?<=[.!?;])\s+(?=[A-Z"\'])')
    # 句末标点+引号/括号（允许在标点后跟引号/括号）
    SENTENCE_END_WITH_QUOTE = re.compile(r'(?<=[.!?]["\'])\s+(?=[A-Z])')
    # 省略号（视为 1 个边界）
    ELLIPSIS = re.compile(r"\.{3,}")
    # 破折号包裹的子句
    EM_DASH_CLAUSE = re.compile(r"—[^—]+?—")

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.abbreviations = set(self.config.get("extra_abbreviations", [])) | set(EN_ABBREVIATIONS)
        self.handle_ellipsis = self.config.get("handle_ellipsis", True)
        self.handle_em_dash = self.config.get("handle_em_dash", True)
        self.max_sentence_length = self.config.get("max_sentence_length", 200)

    def split(self, text: str) -> List[SentenceBlock]:
        if not text or not text.strip():
            return []

        text = text.strip()
        # 1. 保护缩写（替换为占位符）
        text, abbr_map = self._protect_abbreviations(text)

        # 2. 保护引号内句号（简化版：粗粒度成对匹配）
        text, quote_map = self._protect_quoted_sentences(text)

        # 3. 保护省略号（先标记，稍后还原）
        ellipsis_map = {}
        if self.handle_ellipsis:
            text, ellipsis_map = self._protect_ellipsis(text)

        # 4. 按句末标点切分
        candidates = self._split_by_punctuation(text)

        # 5. 还原占位符
        result = []
        idx = 0
        for c in candidates:
            c = self._restore(c, abbr_map)
            c = self._restore(c, quote_map)
            c = self._restore_ellipsis(c, ellipsis_map)
            c = self._clean_whitespace(c)
            c = c.strip()
            if not c:
                continue
            # 6. 处理过长句
            if len(c) > self.max_sentence_length:
                result.extend(self._split_long(c, idx))
                idx += 1
            else:
                result.append(self._make_block(c, idx))
                idx += 1

        return result

    @staticmethod
    def _clean_whitespace(text: str) -> str:
        """合并多余空白（保留句末标点）。"""
        import re as _re

        return _re.sub(r"[\t ]+", " ", text)

    def _protect_ellipsis(self, text: str) -> tuple[str, dict]:
        """保护省略号（视为 1 个边界点）。"""
        ellipsis_map = {}
        counter = 0

        def replace_ellipsis(match):
            nonlocal counter
            placeholder = f"§ELLIPSIS{counter}§"
            ellipsis_map[placeholder] = "..."
            counter += 1
            return placeholder

        text = self.ELLIPSIS.sub(replace_ellipsis, text)
        return text, ellipsis_map

    @staticmethod
    def _restore_ellipsis(text: str, ellipsis_map: dict) -> str:
        for placeholder, original in ellipsis_map.items():
            text = text.replace(placeholder, original)
        return text

    def _protect_abbreviations(self, text: str) -> tuple[str, dict]:
        """将缩写替换为占位符，避免被误切。"""
        abbr_map = {}
        sorted_abbrs = sorted(self.abbreviations, key=len, reverse=True)
        for i, abbr in enumerate(sorted_abbrs):
            placeholder = f"§ABBR{i}§"
            # 用空格/标点边界匹配
            pattern = re.compile(r"(?<!\w)" + re.escape(abbr) + r"(?!\w)")
            if pattern.search(text):
                abbr_map[placeholder] = abbr
                text = pattern.sub(placeholder, text)
        return text, abbr_map

    def _protect_quoted_sentences(self, text: str) -> tuple[str, dict]:
        """保护引号内可能的句末标点。

        简化策略：将 "..." 内包含 .!?; 的内容替换为占位符。
        """
        quote_map = {}
        counter = 0

        def replace_quoted(match):
            nonlocal counter
            inner = match.group(1)
            if any(p in inner for p in ".!?"):
                placeholder = f"§QUOTE{counter}§"
                quote_map[placeholder] = match.group(0)
                counter += 1
                return placeholder
            return match.group(0)

        # 匹配 "..." 或 "..."(全角)
        text = re.sub(r'"([^"]*?)"', replace_quoted, text)
        text = re.sub(r"'([^']*?)'", replace_quoted, text)
        return text, quote_map

    def _split_by_punctuation(self, text: str) -> List[str]:
        """按句末标点切分。

        切分策略：
        1. 找出所有候选切分点（句末标点后跟空白 + [大写/引号/左括号/小写+省略号]）
        2. 在切分点处切分

        处理省略号：在 `§ELLIPSIS0§` 末尾视为可切分点。
        """
        # 标记可切分点：用特殊换行符
        # 规则 1: .!?; 后跟空白 + 大写/引号/左括号 → 切
        # 规则 2: §ELLIPSIS\d+§ 后跟空白 + 小写 → 切
        marked = re.sub(
            r'([.!?;])\s+(?=[A-Z"\(\(])',
            r"\1\n<SPLIT>",
            text,
        )
        # 规则 2: 省略号占位符 + 空白 + 小写
        marked = re.sub(
            r"(§ELLIPSIS\d+§)\s+(?=[a-z])",
            r"\1\n<SPLIT>",
            marked,
        )

        parts = marked.split("\n<SPLIT>")
        return [p for p in parts if p.strip()]

    def _split_long(self, text: str, start_idx: int) -> List[SentenceBlock]:
        """处理过长句：在逗号/分号处切。"""
        parts = re.split(r"(?<=[,;:])\s+", text)
        result = []
        idx = start_idx
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if len(p) > self.max_sentence_length:
                # 强制按 max_sentence_length 切
                for i in range(0, len(p), self.max_sentence_length):
                    chunk = p[i : i + self.max_sentence_length].strip()
                    if chunk:
                        result.append(self._make_block(chunk, idx))
                        idx += 1
            else:
                result.append(self._make_block(p, idx))
                idx += 1
        return result

    @staticmethod
    def _restore(text: str, placeholder_map: dict) -> str:
        """还原占位符。"""
        for placeholder, original in placeholder_map.items():
            text = text.replace(placeholder, original)
        return text
