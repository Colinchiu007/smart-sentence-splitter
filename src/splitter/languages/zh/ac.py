"""Aho-Corasick 自动机（标准实现，借鉴 FoolNLTK trie.py）。

v0.3 升级：
1. 返回 Match dataclass 而非 tuple
2. fail 节点 emit 集合合并（标准 AC 算法细节）
3. 增加 longest-only 模式（只保留最长匹配）

用法：
    ac = ACAutomaton()
    ac.add_word("北京大学")
    ac.add_word("大学")
    ac.build()
    matches = ac.search("北京大学位于北京")  # 返回 [Match(...)]
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Tuple
from collections import deque


@dataclass
class Match:
    """模式串匹配结果。

    Attributes:
        start: 起始位置（含）
        end: 结束位置（不含）
        keyword: 匹配到的模式串
        length: 匹配长度（end - start）
    """
    start: int
    end: int
    keyword: str
    length: int = 0

    def __post_init__(self):
        if self.length == 0:
            self.length = self.end - self.start
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"Invalid Match: start={self.start}, end={self.end}")


class _ACNode:
    """AC 自动机节点（内部类）。"""
    __slots__ = ("children", "fail", "emits")

    def __init__(self):
        self.children: Dict[str, int] = {}  # char → node_id
        self.fail: int = 0                  # fail 指针
        self.emits: Set[str] = set()         # 该节点能匹配的所有模式串


class ACAutomaton:
    """Aho-Corasick 多模式匹配自动机。"""

    def __init__(self):
        self._nodes: List[_ACNode] = [_ACNode()]
        self._patterns: List[str] = []
        self._built = False

    def add_word(self, word: str) -> int:
        """添加模式串。

        Returns:
            模式串 id
        """
        if self._built:
            raise RuntimeError("Cannot add words after build()")
        word = word.strip()
        if not word:
            return -1

        pattern_id = len(self._patterns)
        self._patterns.append(word)

        # 沿 goto 链向下走
        node = 0
        for char in word:
            if char not in self._nodes[node].children:
                self._nodes[node].children[char] = len(self._nodes)
                self._nodes.append(_ACNode())
            node = self._nodes[node].children[char]

        # 标记匹配
        self._nodes[node].emits.add(word)
        return pattern_id

    def add_words(self, words: List[str]):
        """批量添加。"""
        for w in words:
            self.add_word(w)

    def build(self):
        """构建 fail 指针（BFS，标准 AC 算法）。"""
        q: deque[int] = deque()

        # 第一层节点的 fail 指向 root
        for char, next_node in self._nodes[0].children.items():
            self._nodes[next_node].fail = 0
            q.append(next_node)

        # BFS 构建 fail 指针
        while q:
            current = q.popleft()
            current_node = self._nodes[current]
            for char, next_node in current_node.children.items():
                q.append(next_node)
                # 沿 fail 链找最远可匹配的祖先
                fail_state = current_node.fail
                while fail_state != 0 and char not in self._nodes[fail_state].children:
                    fail_state = self._nodes[fail_state].fail
                if char in self._nodes[fail_state].children:
                    fail_state = self._nodes[fail_state].children[char]
                self._nodes[next_node].fail = fail_state

                # ★ 关键：合并 fail 节点的 emit
                fail_node = self._nodes[fail_state]
                if fail_node.emits:
                    self._nodes[next_node].emits |= fail_node.emits

        self._built = True

    def search(
        self,
        text: str,
        longest_only: bool = True,
    ) -> List[Match]:
        """在 text 中搜索所有模式串。

        Args:
            text: 待搜索文本
            longest_only: True 时只返回最长匹配（重叠时去短）

        Returns:
            Match 列表
        """
        if not self._built:
            self.build()

        if not text:
            return []

        matches: List[Match] = []
        node = 0
        # position: 已处理字符数（即下一个字符的下标）
        position = 0

        for char in text:
            # 沿 fail 链找匹配
            while node != 0 and char not in self._nodes[node].children:
                node = self._nodes[node].fail
            node = self._nodes[node].children.get(char, 0)

            # ★ 直接输出当前节点 emits（build 时已合并所有 fail 链 emit）
            for keyword in self._nodes[node].emits:
                end = position + 1
                start = end - len(keyword)
                if start >= 0:
                    matches.append(Match(start=start, end=end, keyword=keyword))

            position += 1

        if not longest_only:
            return matches

        # longest_only: 同一位置只保留最长
        result: List[Match] = []
        by_start: Dict[int, Match] = {}
        for m in matches:
            existing = by_start.get(m.start)
            if existing is None or m.length > existing.length:
                by_start[m.start] = m

        result = sorted(by_start.values(), key=lambda x: (x.start, -x.length))

        # 去掉被更长匹配覆盖的
        final: List[Match] = []
        for m in result:
            covered = any(
                other.start <= m.start and other.end >= m.end and other.length > m.length
                for other in result
            )
            if not covered:
                final.append(m)
        return final

    def __len__(self) -> int:
        return len(self._patterns)


class TriedTree:
    """简化版 Trie 树（与 LAC prefix_tree.py 兼容）— 保留。"""

    def __init__(self):
        self.tree: Dict[str, int] = {}

    def add_word(self, word: str):
        self.tree[word] = len(word)
        for i in range(1, len(word)):
            wfrag = word[:i]
            if wfrag not in self.tree:
                self.tree[wfrag] = None

    def search(self, content: str) -> List[Tuple[int, int]]:
        result = []
        length = len(content)
        for start in range(length):
            for end in range(start + 1, length + 1):
                pos = self.tree.get(content[start:end], -1)
                if pos == -1:
                    break
                if pos:
                    result.append((start, end))
        return result
