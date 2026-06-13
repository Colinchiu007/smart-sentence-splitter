"""Test language detection utility."""

import pytest
from splitter.utils.language_detect import (
    detect_language,
    detect_language_with_confidence,
    is_chinese,
    is_japanese_kana,
    is_english_letter,
)


class TestIsChinese:
    def test_chinese_char_returns_true(self):
        assert is_chinese("中") is True
        assert is_chinese("文") is True
        assert is_chinese("测") is True

    def test_english_char_returns_false(self):
        assert is_chinese("a") is False
        assert is_chinese("Z") is False

    def test_digit_returns_false(self):
        assert is_chinese("1") is False

    def test_empty_string_returns_false(self):
        assert is_chinese("") is False

    def test_japanese_kana_returns_false(self):
        assert is_chinese("あ") is False
        assert is_chinese("ア") is False


class TestIsJapaneseKana:
    def test_hiragana_returns_true(self):
        assert is_japanese_kana("あ") is True
        assert is_japanese_kana("ん") is True

    def test_katakana_returns_true(self):
        assert is_japanese_kana("ア") is True
        assert is_japanese_kana("ン") is True

    def test_chinese_returns_false(self):
        assert is_japanese_kana("中") is False


class TestIsEnglishLetter:
    def test_ascii_letter_returns_true(self):
        assert is_english_letter("a") is True
        assert is_english_letter("Z") is True

    def test_chinese_returns_false(self):
        assert is_english_letter("中") is False

    def test_digit_returns_false(self):
        assert is_english_letter("1") is False


class TestDetectLanguage:
    def test_pure_chinese_returns_zh(self):
        text = "今天天气真好，我们去公园散步吧！"
        assert detect_language(text) == "zh"

    def test_pure_english_returns_en(self):
        text = "The quick brown fox jumps over the lazy dog."
        assert detect_language(text) == "en"

    def test_pure_japanese_returns_ja(self):
        text = "こんにちは、世界！"
        assert detect_language(text) == "ja"

    def test_mixed_returns_mixed(self):
        text = "今天我在 Apple Store 买了一个 iPhone"
        assert detect_language(text) == "mixed"

    def test_empty_returns_zh_fallback(self):
        assert detect_language("") == "zh"
        assert detect_language("   ") == "zh"

    def test_chinese_heavy_with_some_english(self):
        text = "深度学习是人工智能的一个重要分支。它在计算机视觉领域取得了突破性进展。"
        assert detect_language(text) == "zh"


class TestDetectLanguageWithConfidence:
    def test_pure_chinese_high_confidence(self):
        _, conf = detect_language_with_confidence("今天天气真好")
        assert conf > 0.8

    def test_pure_english_high_confidence(self):
        _, conf = detect_language_with_confidence("Hello world this is English")
        assert conf > 0.8

    def test_empty_returns_zero_confidence(self):
        _, conf = detect_language_with_confidence("")
        assert conf == 0.0
