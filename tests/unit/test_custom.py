"""Test AC automaton and Customization."""

import pytest
from splitter.languages.zh.ac import ACAutomaton, TriedTree, Match
from splitter.languages.zh.custom import Customization


class TestACAutomaton:
    def test_empty_auto(self):
        ac = ACAutomaton()
        assert ac.search("hello") == []

    def test_single_word(self):
        ac = ACAutomaton()
        ac.add_word("hello")
        r = ac.search("hello world")
        assert any(m.keyword == "hello" and m.start == 0 and m.end == 5 for m in r)

    def test_multiple_words(self):
        ac = ACAutomaton()
        ac.add_word("he")
        ac.add_word("hello")
        ac.add_word("world")
        r = ac.search("hello world")
        # longest_only=True 默认 → "hello" 优先于 "he"
        keywords = [m.keyword for m in r]
        assert "hello" in keywords
        assert "world" in keywords

    def test_no_match(self):
        ac = ACAutomaton()
        ac.add_word("xyz")
        assert ac.search("hello") == []

    def test_chinese_words(self):
        ac = ACAutomaton()
        ac.add_word("中华人民共和国")
        ac.add_word("中国人民")
        r = ac.search("中华人民共和国万岁")
        assert any(m.keyword == "中华人民共和国" for m in r)

    def test_overlapping_matches(self):
        ac = ACAutomaton()
        ac.add_word("研究")
        ac.add_word("研究生")
        r = ac.search("研究生制度")
        # longest_only → 只保留 "研究生"
        assert len(r) == 1
        assert r[0].keyword == "研究生"

    def test_rebuild_raises(self):
        ac = ACAutomaton()
        ac.build()
        with pytest.raises(RuntimeError):
            ac.add_word("test")

    # ===== v0.3 新增：Match dataclass + emit 合并 =====

    def test_match_dataclass(self):
        """F1: 返回 Match 对象而非 tuple。"""
        ac = ACAutomaton()
        ac.add_word("北京")
        r = ac.search("北京欢迎你")
        assert len(r) == 1
        m = r[0]
        assert isinstance(m, Match)
        assert m.keyword == "北京"
        assert m.start == 0
        assert m.end == 2
        assert m.length == 2

    def test_match_invalid_raises(self):
        """Match 验证：start < 0 抛异常。"""
        with pytest.raises(ValueError):
            Match(start=-1, end=2, keyword="x")

    def test_emit_merging_via_fail(self):
        """F1: fail 节点 emit 合并（标准 AC）。

        "he" 和 "she" → 'she' 节点（路径最深）应同时含 {"she", "he"}。
        """
        ac = ACAutomaton()
        ac.add_word("he")
        ac.add_word("she")
        ac.build()
        # 找含 'she' 的节点（'she' 路径的最深节点）
        last_node = None
        for n in ac._nodes:
            if "she" in n.emits:
                last_node = n
        assert last_node is not None
        # fail 链 emit 合并：'she' 节点的 fail 指向 'he' 节点
        # → 'she' 节点应同时含 'she' 和 'he'
        assert "he" in last_node.emits

    def test_longest_only_false(self):
        """保留所有匹配（包含短的）。"""
        ac = ACAutomaton()
        ac.add_word("研")
        ac.add_word("研究")
        ac.add_word("研究生")
        r = ac.search("研究生", longest_only=False)
        # 3 个匹配
        assert len(r) == 3

    def test_emit_set_includes_overlapping(self):
        """F1: emit 集合预合并（build 时）。

        "abc" 和 "bc" → "abc" 节点 emit 包含两者
        """
        ac = ACAutomaton()
        ac.add_word("abc")
        ac.add_word("bc")
        ac.build()
        # node 路径: 0 -> a(1) -> b(2) -> c(3)
        # 走完 'c' 时 node 3 的 emit 应同时含 "abc" 和 "bc"
        last_node = ac._nodes[3]
        assert "abc" in last_node.emits
        assert "bc" in last_node.emits


class TestTriedTree:
    def test_basic(self):
        t = TriedTree()
        t.add_word("hello")
        r = t.search("hello world")
        assert len(r) >= 1

    def test_no_match(self):
        t = TriedTree()
        t.add_word("xyz")
        assert t.search("hello") == []


class TestCustomization:
    def test_add_word(self):
        c = Customization()
        c.add_word("中华人民共和国")
        result = c.adjust(["中华", "人民共和国", "万岁"])
        assert "中华人民共和国" in result

    def test_no_change_when_no_match(self):
        c = Customization()
        c.add_word("北京大学")
        result = c.adjust(["今天", "天气", "真好"])
        assert result == ["今天", "天气", "真好"]

    def test_empty_result(self):
        c = Customization()
        assert c.adjust([]) == []
        # 全空字符串输入也返回空
        result = c.adjust(["", ""])
        assert all(not s.strip() for s in result) or result == []

    def test_long_phrase_over_split(self):
        c = Customization()
        c.add_word("自然语言处理")
        result = c.adjust(["自然", "语言", "处理", "是", "AI", "的", "分支"])
        assert "自然语言处理" in result

    def test_multiple_phrases(self):
        c = Customization()
        c.add_word("人工智能")
        c.add_word("机器学习")
        result = c.adjust(["人工", "智能", "和", "机器", "学习"])
        assert "人工智能" in result
        assert "机器学习" in result

    def test_parse_word_with_tag(self):
        c = Customization()
        phrase = c._parse_word("北京/n 大学/n")
        assert phrase == "北京大学"

    def test_parse_word_simple(self):
        c = Customization()
        phrase = c._parse_word("中华人民共和国")
        assert phrase == "中华人民共和国"

    # ===== v0.3 新增：DAG+DP 加权合并 =====

    def test_adjust_dag_no_seg(self):
        """F2: DAG+DP 合并，无已有分词结果。"""
        c = Customization()
        c.add_word("自然语言处理")
        result = c.adjust_dag("自然语言处理是AI分支")
        assert "自然语言处理" in result
        assert "是" in result

    def test_adjust_dag_with_seg(self):
        """F2: DAG+DP 合并 + 已有分词。"""
        c = Customization()
        c.add_word("自然语言处理")
        # 已有分词把"自然语言处理"切散了
        segs = ["自然", "语言", "处理", "是", "AI", "分支"]
        result = c.adjust_dag("自然语言处理是AI分支", segs)
        # 应在分词结果上重新优化
        assert "自然语言处理" in result

    def test_adjust_dag_user_dict_overrides(self):
        """F2: 用户词典权重应覆盖已有分词。"""
        c = Customization()
        c.add_word("北京大学")
        # 已有分词：["北京", "大学"]
        segs = ["北京", "大学", "是", "名校"]
        result = c.adjust_dag("北京大学是名校", segs)
        # 北京大学应合并
        assert "北京大学" in result

    def test_adjust_dag_empty(self):
        """F2: 空输入返回空。"""
        c = Customization()
        c.add_word("测试")
        assert c.adjust_dag("") == []
