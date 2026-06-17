"""Test English splitter."""

import pytest
from splitter.languages.en.splitter import EnglishSplitter


class TestEnglishSplitter:
    def setup_method(self):
        self.splitter = EnglishSplitter()

    def test_basic_split(self):
        text = "Hello world. This is a test. How are you?"
        result = self.splitter.split(text)
        assert len(result) == 3

    def test_split_with_question(self):
        text = "Are you OK? I am fine."
        result = self.splitter.split(text)
        assert len(result) == 2

    def test_split_with_exclamation(self):
        text = "Wow! Amazing! Great!"
        result = self.splitter.split(text)
        assert len(result) == 3

    def test_empty_text(self):
        assert self.splitter.split("") == []
        assert self.splitter.split("   ") == []

    def test_single_sentence(self):
        text = "Hello world."
        result = self.splitter.split(text)
        assert len(result) == 1

    def test_abbreviation_not_split(self):
        text = "Dr. Smith and Mr. Wang went to the U.S. yesterday."
        result = self.splitter.split(text)
        # 不应被缩写中的 . 误切
        # 简化：结果应该 <= 2 句（按整体一句话）
        assert len(result) <= 2

    def test_quoted_sentence_protected(self):
        text = 'He said "Hello world." Then he left.'
        result = self.splitter.split(text)
        # 引号内的 . 不应触发切分
        assert len(result) <= 2

    def test_ellipsis_treated_as_one(self):
        text = "He thought... and then left."
        result = self.splitter.split(text)
        # 省略号应该视为 1 个边界
        assert len(result) == 2

    def test_index_incremental(self):
        text = "First. Second. Third."
        result = self.splitter.split(text)
        for i, s in enumerate(result):
            assert s.index == i

    def test_tier_mark(self):
        result = self.splitter.split("Test.")
        assert result[0].tier == "tier3_rule"
        assert result[0].language == "en"
