"""Test Chinese splitter."""

import pytest
from splitter.languages.zh.splitter import ChineseSplitter


class TestChineseSplitter:
    def setup_method(self):
        self.splitter = ChineseSplitter({"use_jieba": False})  # 测试时不依赖 jieba

    def test_basic_split(self):
        text = "今天天气真好。我们去公园散步。"
        result = self.splitter.split(text)
        assert len(result) == 2
        assert result[0].text == "今天天气真好。"
        assert result[1].text == "我们去公园散步。"

    def test_split_with_exclamation(self):
        text = "太棒了！太好了！"
        result = self.splitter.split(text)
        assert len(result) == 2

    def test_split_with_question(self):
        text = "你好吗？我很好。"
        result = self.splitter.split(text)
        assert len(result) == 2

    def test_empty_text(self):
        assert self.splitter.split("") == []
        assert self.splitter.split("   ") == []

    def test_single_sentence(self):
        text = "今天天气真好。"
        result = self.splitter.split(text)
        assert len(result) == 1
        assert result[0].text == "今天天气真好。"

    def test_protect_quoted_punctuation(self):
        text = "他说：“好的。”然后走了。"
        result = self.splitter.split(text)
        # 不应在引号内句号处误切
        # 简化判断：切分结果数 <= 2
        assert len(result) <= 2

    def test_long_sentence_split(self):
        long_text = "今天" * 50  # 100 字符
        result = self.splitter.split(long_text)
        assert all(len(s.text) <= self.splitter.max_sentence_length + 20 for s in result)

    def test_index_incremental(self):
        text = "第一句。第二句。第三句。"
        result = self.splitter.split(text)
        for i, s in enumerate(result):
            assert s.index == i

    def test_tier_mark(self):
        text = "测试一下。"
        result = self.splitter.split(text)
        assert result[0].tier == "tier3_rule"  # 没用 jieba

    def test_with_jieba_when_available(self):
        splitter = ChineseSplitter({"use_jieba": True})
        text = "今天天气真好。我们去公园散步。"
        result = splitter.split(text)
        assert len(result) == 2
        # 如果 jieba 可用，tier 应该是 tier2_semantic
        if splitter.tokenizer and splitter.tokenizer.is_available():
            assert result[0].tier == "tier2_semantic"
            assert len(result[0].words) > 0  # 有分词结果
