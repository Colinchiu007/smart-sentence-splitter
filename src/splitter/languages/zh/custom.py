"""Customization — 用户词典干预机制。

源自 baidu/lac 的 `Customization` 思路：
1. 用 AC 自动机查找用户词典中的所有短语
2. 对每个匹配，**改写分句结果**（不是原文本），
   将用户词典中的词保持完整不分到不同句子。

用法：
    custom = Customization()
    custom.add_word("中华人民共和国")
    custom.load_customization("user_dict.txt")
    sentences = ["中华", "人民共和国", "万岁"]  # 原本被切错了
    custom.adjust(sentences)
    # → ["中华人民共和国", "万岁"]

词典格式：
    - `中华人民共和国` — 简单词
    - `花/n 开/v` — 带词性的短语（tag 被忽略，只保留 phrase）
"""

from __future__ import annotations
from typing import List, Optional, Tuple
from pathlib import Path

from .ac import ACAutomaton


class Customization:
    """用户词典干预类。

    对分词/分句结果进行后处理，将用户词典中的短语合并。
    """

    def __init__(self):
        self.ac = ACAutomaton()
        self.phrases: List[str] = []  # phrase → text
        self._loaded = False

    def add_word(self, word: str, sep: Optional[str] = None):
        """添加单个用户词典词。

        Args:
            word: 用户定义短语，格式同 LAC（`"中华人民共和国"` 或 `"花/n 开/v"`）
            sep: 短语分隔符（默认空白）
        """
        phrase = self._parse_word(word, sep)
        if not phrase or len(phrase) < 2:
            return
        self.phrases.append(phrase)
        self.ac.add_word(phrase)

    def load_customization(self, filepath: str, sep: Optional[str] = None):
        """从文件装载用户词典。

        每行一个短语，格式：`中华人民共和国` 或 `花/n 开/v`。
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Customization file not found: {filepath}")

        self.ac = ACAutomaton()
        self.phrases = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                phrase = self._parse_word(line, sep)
                if not phrase or len(phrase) < 2:
                    continue
                self.phrases.append(phrase)
                self.ac.add_word(phrase)

        self.ac.build()
        self._loaded = True

    def adjust(self, split_result: List[str]) -> List[str]:
        """后处理：合并被错误切分的用户词典词。

        对已有分句/分词结果执行合并。
        """
        if not self.phrases or not split_result:
            return split_result

        if not self._loaded:
            self.ac.build()
            self._loaded = True

        # 将分句结果拼接为全文
        full_text = "".join(split_result)

        # 用 AC 搜索用户词典匹配
        matches = self.ac.search(full_text)

        if not matches:
            return split_result

        # 按匹配切分：用最长匹配先合并
        # 1. 先按匹配把全文切块
        # 2. 在匹配边界处断开
        merge_ranges = []
        for m in matches:
            merge_ranges.append((m.start, m.end))

        # 排序并合并重叠区间
        merge_ranges.sort()
        merged_ranges = []
        for start, end in merge_ranges:
            if merged_ranges and start <= merged_ranges[-1][1]:
                # 重叠或相邻，合并
                prev_start, prev_end = merged_ranges[-1]
                merged_ranges[-1] = (prev_start, max(prev_end, end))
            else:
                merged_ranges.append((start, end))

        # 按合并区间重排 split_result
        result = []
        last_end_char = 0
        for merge_start, merge_end in merged_ranges:
            # 添加合并区间前的文本
            if last_end_char < merge_start:
                intervening = self._char_range_to_segments(full_text, last_end_char, merge_start, split_result)
                result.extend(intervening)

            # 添加合并后的短语
            merged_text = full_text[merge_start:merge_end]
            result.append(merged_text)
            last_end_char = merge_end

        # 添加剩余文本
        if last_end_char < len(full_text):
            remaining = self._char_range_to_segments(full_text, last_end_char, len(full_text), split_result)
            result.extend(remaining)

        # 过滤空
        return [r for r in result if r.strip()]

    @staticmethod
    def _parse_word(word: str, sep: Optional[str] = None) -> str:
        """解析词典词。"""
        if sep is None:
            parts = word.strip().split()
        else:
            parts = word.strip().split(sep)

        if not parts:
            return ""

        # 跟 LAC 相同的模式：去掉 /tag 后缀保留短语
        phrase_parts = []
        for part in parts:
            if "/" in part:
                phrase_parts.append(part[: part.rfind("/")])
            else:
                phrase_parts.append(part)
        return "".join(phrase_parts)

    @staticmethod
    def _char_range_to_segments(full_text: str, char_start: int, char_end: int, segments: List[str]) -> List[str]:
        """从 segments 中取落在 [char_start, char_end) 之间的部分。"""
        cum = 0
        result = []
        for seg in segments:
            seg_start = cum
            seg_end = cum + len(seg)
            if seg_end <= char_start:
                cum = seg_end
                continue
            if seg_start >= char_end:
                break
            # 有交集
            overlap_start = max(seg_start, char_start)
            overlap_end = min(seg_end, char_end)
            if overlap_end > overlap_start:
                result.append(full_text[overlap_start:overlap_end])
            cum = seg_end
        return result

    def adjust_dag(self, text: str, seg_results: Optional[List[str]] = None) -> List[str]:
        """v0.3 新增：DAG+DP 加权合并（借鉴 FoolNLTK `_mearge_user_words`）。

        同时考虑：
        1. 用户词典匹配（AC 自动机）
        2. 已有的分词结果（如果提供）

        构造 DAG，每条边有权重，DP 选最大路径。

        Args:
            text: 原始文本
            seg_results: 已有分词结果（None 时视为单字）

        Returns:
            合并后的分词列表
        """
        if not self.phrases:
            return seg_results or list(text)

        if not self._loaded:
            self.ac.build()
            self._loaded = True

        if seg_results is None:
            seg_results = list(text)

        # 1. 收集所有候选边
        # 边: (start, end) → weight
        edges: Dict[Tuple[int, int], float] = {}

        # 单字边
        for i in range(len(text)):
            edges[(i, i + 1)] = 1.0

        # 分词结果边（保留作为基础）
        cum = 0
        for word in seg_results:
            w_len = len(word)
            if w_len > 0:
                # 权重 = 1.0 + 长度
                weight = 1.0 + w_len
                edges[(cum, cum + w_len)] = max(edges.get((cum, cum + w_len), 0), weight)
            cum += w_len

        # 用户词典边（优先级最高，权重大于已有分词）
        matches = self.ac.search(text, longest_only=True)
        for m in matches:
            # 权重 = 用户词典优先级 × 长度 × 长度（长词 + 用户词典双重加成）
            weight = 2.0 * m.length * m.length
            key = (m.start, m.end)
            if key in edges:
                edges[key] = max(edges[key], weight)
            else:
                edges[key] = weight

        # 2. DP 选最大权重路径
        if not edges:
            return seg_results

        # 构建邻接表
        from collections import defaultdict

        adj: Dict[int, List[Tuple[int, float]]] = defaultdict(list)
        for (s, e), w in edges.items():
            adj[s].append((e, w))

        n = len(text)
        # dp[i] = (max_score, next_index)
        dp: Dict[int, Tuple[float, int]] = {n: (0.0, n)}

        for i in range(n - 1, -1, -1):
            if not adj[i]:
                # 无路可走：跳过（实际不会发生，因为有单字边）
                dp[i] = (float("-inf"), n)
                continue
            best = max((w + dp[e][0], e) for e, w in adj[i] if e in dp)
            dp[i] = best

        # 3. 回溯路径
        if n not in dp or dp[0][1] == n:
            return seg_results

        result: List[str] = []
        pos = 0
        while pos < n:
            next_pos = dp[pos][1]
            if next_pos <= pos:
                break
            result.append(text[pos:next_pos])
            pos = next_pos

        return result
