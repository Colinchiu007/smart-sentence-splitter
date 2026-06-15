"""Japanese splitter tests (v0.9.9 新增)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from splitter.languages.ja.splitter import JapaneseSplitter


class TestJapaneseSplitter:
    """Japanese splitter unit tests."""

    def setup_method(self):
        self.s = JapaneseSplitter()

    def test_three_sentences(self):
        blocks = self.s.split("今日はいい天気ですね。公園を散歩しましょう。友達に会いました。")
        assert len(blocks) == 3
        assert "今日" in blocks[0].text
        assert "公園" in blocks[1].text
        assert "友達" in blocks[2].text

    def test_quotes_protected(self):
        """句点在「」内不分割。"""
        blocks = self.s.split("彼は「行きます。後で会いましょう」と言った。本当です。")
        assert len(blocks) == 2
        assert "「行きます。後で会いましょう」" in blocks[0].text

    def test_exclamation_and_question(self):
        blocks = self.s.split("やった！すごい！本当ですか？はいそうです。")
        assert len(blocks) == 4

    def test_newline_as_boundary(self):
        blocks = self.s.split("最初の文。\n次の文。最後の文。")
        assert len(blocks) == 3

    def test_empty_text(self):
        assert self.s.split("") == []
        assert self.s.split("   ") == []

    def test_no_eos(self):
        blocks = self.s.split("句点のない文")
        assert len(blocks) == 1

    def test_mixed_quotes(self):
        """複数の括弧を正しく処理。"""
        blocks = self.s.split("「かっこ1」と「かっこ2」。そして最後。")
        assert len(blocks) == 2
