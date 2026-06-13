"""Aho-Corasick 自动机（纯 Python 实现）。

用于多模式匹配：在 O(n) 时间内找出文本中所有词典匹配。
源自 baidu/lac 的 Customization 机制。

用法：
    ac = ACAutomaton()
    ac.add_word("北京大学")
    ac.add_word("人工智能")
    ac.build()
    matches = ac.search("北京大学位于北京")
    # matches → [(0, 4), (2, 3)]
"""

from __future__ import annotations
from typing import List, Tuple, Dict, Optional


class ACAutomaton:
    """Aho-Corasick 多模式匹配自动机。"""

    def __init__(self):
        # 每个节点：dict[char → node_id]
        self.goto: List[Dict[str, int]] = [{}]  # goto 表
        self.fail: List[int] = [0]               # fail 指针
        self.output: List[List[int]] = [[]]      # 匹配输出（模式串 id）
        self.patterns: List[str] = []            # 模式串列表
        self._built = False

    def add_word(self, word: str) -> int:
        """添加一个模式串。

        Returns:
            模式串 id
        """
        if self._built:
            raise RuntimeError("Cannot add words after build()")
        word = word.strip()
        if not word:
            return -1
        pattern_id = len(self.patterns)
        self.patterns.append(word)

        # 沿 goto 链向下走
        node = 0
        for char in word:
            if char not in self.goto[node]:
                self.goto[node][char] = len(self.goto)
                self.goto.append({})
                self.fail.append(0)
                self.output.append([])
            node = self.goto[node][char]

        # 标记匹配
        self.output[node].append(pattern_id)
        return pattern_id

    def build(self):
        """构建 fail 指针（BFS）。"""
        from collections import deque

        # root 的 fail = 0（自己）
        q = deque()

        # 第一层节点的 fail 指向 root
        for char, next_node in self.goto[0].items():
            self.fail[next_node] = 0
            q.append(next_node)

        # BFS 构建 fail 指针
        while q:
            node = q.popleft()
            for char, next_node in self.goto[node].items():
                # 找 fail 指针
                f = self.fail[node]
                while f != 0 and char not in self.goto[f]:
                    f = self.fail[f]
                self.fail[next_node] = self.goto[f].get(char, 0)

                # 合并 fail 节点的输出
                fail_node = self.fail[next_node]
                if self.output[fail_node]:
                    self.output[next_node] = list(set(
                        self.output[next_node] + self.output[fail_node]
                    ))

                q.append(next_node)

        self._built = True

    def search(self, text: str) -> List[Tuple[int, int]]:
        """在 text 中搜索所有模式串。

        Returns:
            [(start, end), ...] 每个匹配的起止位置（含 start，不含 end）
        """
        if not self._built:
            self.build()

        node = 0
        matches: List[Tuple[int, int]] = []
        seen = set()

        for pos, char in enumerate(text):
            # 沿 fail 链找匹配路径
            while node != 0 and char not in self.goto[node]:
                node = self.fail[node]
            node = self.goto[node].get(char, 0)

            # 输出所有匹配
            for pattern_id in self.output[node]:
                pattern = self.patterns[pattern_id]
                start = pos + 1 - len(pattern)
                end = pos + 1
                key = (start, end)
                if key in seen:
                    continue
                # 去重（重叠匹配只保留最长的）
                seen.add(key)
                matches.append((start, end))

        # 按位置排序
        matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        # 去重 + 保留最长
        result: List[Tuple[int, int]] = []
        last_end = -1
        for start, end in matches:
            if start >= last_end:
                result.append((start, end))
                last_end = end
            elif end - start > last_end - start:
                # 更长的匹配替换之前的
                if result:
                    result[-1] = (start, end)
                last_end = end

        return result


class TriedTree:
    """简化版 Trie 树（与 LAC prefix_tree.py 兼容）。

    用于快速检查某个词是否在字典中。
    """

    def __init__(self):
        self.tree: Dict[str, int] = {}

    def add_word(self, word: str):
        """添加单词。"""
        self.tree[word] = len(word)
        for i in range(1, len(word)):
            wfrag = word[:i]
            if wfrag not in self.tree:
                self.tree[wfrag] = None

    def search(self, content: str) -> List[Tuple[int, int]]:
        """搜索所有匹配。"""
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
