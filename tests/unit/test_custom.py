"""Test AC automaton and Customization."""

import pytest
from splitter.languages.zh.ac import ACAutomaton, TriedTree
from splitter.languages.zh.custom import Customization


class TestACAutomaton:
    def test_empty_auto(self):
        ac = ACAutomaton()
        assert ac.search("hello") == []

    def test_single_word(self):
        ac = ACAutomaton()
        ac.add_word("hello")
        r = ac.search("hello world")
        assert (0, 5) in r

    def test_multiple_words(self):
        ac = ACAutomaton()
        ac.add_word("he")
        ac.add_word("hello")
        ac.add_word("world")
        r = ac.search("hello world")
        assert len(r) >= 2

    def test_no_match(self):
        ac = ACAutomaton()
        ac.add_word("xyz")
        assert ac.search("hello") == []

    def test_chinese_words(self):
        ac = ACAutomaton()
        ac.add_word("中华人民共和国")
        ac.add_word("中国人民")
        r = ac.search("中华人民共和国万岁")
        assert (0, 7) in r  # 中华人民共和国 7 个字

    def test_overlapping_matches(self):
        ac = ACAutomaton()
        ac.add_word("研究")
        ac.add_word("研究生")
        r = ac.search("研究生制度")
        # 应保留最长的
        has_long = any(end - start >= 3 for start, end in r)
        assert has_long

    def test_rebuild_raises(self):
        ac = ACAutomaton()
        ac.build()
        with pytest.raises(RuntimeError):
            ac.add_word("test")


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
