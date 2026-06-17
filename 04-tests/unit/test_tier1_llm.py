"""Test LLMSplitter (Tier 1) — v0.4 完整实做."""

import os
import json
import pytest
from unittest.mock import patch, MagicMock

from splitter.tiers.tier1_llm import LLMSplitter


class TestLLMSplitterInit:
    def test_default_config(self):
        with patch.dict(os.environ, {}, clear=True):
            s = LLMSplitter()
            assert s.provider_name == "openai"
            assert s.tier == "tier1_llm"
            assert s.language == "auto"

    def test_xfyun_config(self):
        s = LLMSplitter({"provider": "xfyun"})
        assert s.provider_name == "xfyun"

    def test_ollama_config(self):
        s = LLMSplitter({"provider": "ollama"})
        assert s.provider_name == "ollama"

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            LLMSplitter({"provider": "fake"})

    def test_repr_includes_provider(self):
        s = LLMSplitter({"provider": "openai"})
        r = repr(s)
        assert "openai" in r
        assert "gpt-4o-mini" in r


class TestLLMSplitterAvailability:
    def test_unavailable_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            s = LLMSplitter()
            assert s.is_available() is False

    def test_available_with_openai_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            s = LLMSplitter()
            assert s.is_available() is True

    def test_available_with_xfyun_key(self):
        with patch.dict(os.environ, {"XFYUN_API_KEY": "xf-test"}):
            s = LLMSplitter({"provider": "xfyun"})
            assert s.is_available() is True


class TestLLMSplitterParseResponse:
    """v0.4 关键：3 层容错解析。"""

    def setup_method(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            self.splitter = LLMSplitter()

    def test_parse_pure_json(self):
        response = '["句子1。", "句子2。", "句子3。"]'
        result = self.splitter._parse_response(response, "原文")
        assert result == ["句子1。", "句子2。", "句子3。"]

    def test_parse_json_with_markdown(self):
        """带 markdown 围栏的 JSON 也能解析。"""
        response = '''```json
["句子1。", "句子2。"]
```'''
        result = self.splitter._parse_response(response, "原文")
        assert result == ["句子1。", "句子2。"]

    def test_parse_json_with_surrounding_text(self):
        """前后有解释文字的 JSON 也能提取。"""
        response = '''这是分句结果：
["句子1。", "句子2。"]
完成。'''
        result = self.splitter._parse_response(response, "原文")
        assert result == ["句子1。", "句子2。"]

    def test_parse_invalid_json_fallback_to_lines(self):
        """非 JSON 但有标点 → 按行切分。"""
        response = "句子1。\n句子2！\n句子3？"
        result = self.splitter._parse_response(response, "原文")
        assert "句子1。" in result
        assert "句子2！" in result
        assert "句子3？" in result

    def test_parse_empty_response(self):
        result = self.splitter._parse_response("", "原文")
        assert result == []

    def test_parse_markdown_fallback(self):
        """markdown 标题被过滤。"""
        response = "# 标题\n## 副标题\n句子1。\n句子2。"
        result = self.splitter._parse_response(response, "原文")
        # 标题被过滤
        assert "标题" not in " ".join(result)
        assert "句子1。" in result
        assert "句子2。" in result

    def test_parse_no_punctuation_fallback_to_original(self):
        """LLM 返回没标点的纯文本 → 兜底按原文切。"""
        response = "乱七八糟无标点"
        result = self.splitter._parse_response(response, "原文。原文。")
        # 兜底回原文切分
        assert len(result) >= 1


class TestLLMSplitterSplit:
    def test_split_raises_when_unavailable(self):
        with patch.dict(os.environ, {}, clear=True):
            s = LLMSplitter()
            with pytest.raises(NotImplementedError, match="not available"):
                s.split("测试文本")

    def test_split_empty_text(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            s = LLMSplitter()
            result = s.split("")
            assert result == []
            result = s.split("   ")
            assert result == []

    def test_split_success(self):
        """mock provider.chat() 返回 JSON。"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            s = LLMSplitter()
            mock_response = '["今天天气真好。", "我们去公园。"]'
            with patch.object(s.provider, "chat", return_value=mock_response):
                result = s.split("今天天气真好。我们去公园。")
                assert len(result) == 2
                assert result[0].text == "今天天气真好。"
                assert result[1].text == "我们去公园。"
                assert result[0].tier == "tier1_llm"

    def test_split_with_retries(self):
        """第一次失败，第二次成功。"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            s = LLMSplitter({"max_retries": 2})
            mock_response = '["句子1。"]'
            with patch.object(
                s.provider,
                "chat",
                side_effect=[Exception("网络错误"), mock_response],
            ) as mock_chat:
                result = s.split("句子1。")
                assert len(result) == 1
                assert mock_chat.call_count == 2

    def test_split_all_retries_fail(self):
        """所有重试都失败 → 抛 RuntimeError。"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            s = LLMSplitter({"max_retries": 1})
            with patch.object(
                s.provider, "chat", side_effect=Exception("持续失败")
            ):
                with pytest.raises(RuntimeError, match="failed after"):
                    s.split("测试")

    def test_split_returns_sentence_blocks(self):
        """确认输出是 SentenceBlock 列表。"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            s = LLMSplitter()
            with patch.object(s.provider, "chat", return_value='["A。", "B。", "C。"]'):
                result = s.split("A。B。C。")
                for i, block in enumerate(result):
                    assert block.index == i
                    assert block.tier == "tier1_llm"
