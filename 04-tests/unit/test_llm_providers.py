"""Test LLM Provider abstract base + OpenAI/xfyun/Ollama."""

import os
import pytest
from unittest.mock import patch, MagicMock

from splitter.llm import (
    LLMProvider,
    OpenAIProvider,
    XfyunProvider,
    OllamaProvider,
)


class TestLLMProviderAbstract:
    def test_abstract_cannot_instantiate(self):
        with pytest.raises(TypeError):
            LLMProvider()  # 抽象类不能直接实例化

    def test_subclass_must_implement_methods(self):
        class BadProvider(LLMProvider):
            name = "bad"
        with pytest.raises(TypeError):
            BadProvider()


class TestOpenAIProvider:
    def test_no_api_key_unavailable(self):
        with patch.dict(os.environ, {}, clear=True):
            p = OpenAIProvider()
            assert p.is_available() is False

    def test_with_api_key_available(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            p = OpenAIProvider()
            assert p.is_available() is True

    def test_explicit_api_key(self):
        p = OpenAIProvider(api_key="sk-explicit")
        assert p.is_available() is True

    def test_model_default(self):
        with patch.dict(os.environ, {}, clear=True):
            p = OpenAIProvider()
            assert p.model == "gpt-4o-mini"

    def test_custom_model(self):
        with patch.dict(os.environ, {}, clear=True):
            p = OpenAIProvider(model="gpt-4o")
            assert p.model == "gpt-4o"

    def test_chat_calls_openai(self):
        """mock OpenAI client.chat.completions.create."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            p = OpenAIProvider()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="测试响应"))]
            with patch("openai.OpenAI") as MockClient:
                mock_instance = MockClient.return_value
                mock_instance.chat.completions.create.return_value = mock_response
                result = p.chat([{"role": "user", "content": "hi"}])
                assert result == "测试响应"
                MockClient.assert_called_once()
                mock_instance.chat.completions.create.assert_called_once()

    def test_chat_with_base_url(self):
        """base_url 透传给 OpenAI client。"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            p = OpenAIProvider(base_url="https://custom.example.com/v1")
            with patch("openai.OpenAI") as MockClient:
                mock_instance = MockClient.return_value
                mock_instance.chat.completions.create.return_value = MagicMock(
                    choices=[MagicMock(message=MagicMock(content="ok"))]
                )
                p.chat([{"role": "user", "content": "hi"}])
                # 验证 base_url 传给了 OpenAI
                call_kwargs = MockClient.call_args.kwargs
                assert call_kwargs.get("base_url") == "https://custom.example.com/v1"


class TestXfyunProvider:
    def test_default_base_url(self):
        with patch.dict(os.environ, {}, clear=True):
            p = XfyunProvider()
            assert "xf-yun.com" in p.base_url

    def test_no_api_key_unavailable(self):
        with patch.dict(os.environ, {}, clear=True):
            p = XfyunProvider()
            assert p.is_available() is False

    def test_with_api_key_available(self):
        with patch.dict(os.environ, {"XFYUN_API_KEY": "xf-test"}):
            p = XfyunProvider()
            assert p.is_available() is True

    def test_custom_base_url(self):
        with patch.dict(os.environ, {}, clear=True):
            p = XfyunProvider(base_url="https://custom.xfyun.com/v1")
            assert p.base_url == "https://custom.xfyun.com/v1"

    def test_model_default(self):
        with patch.dict(os.environ, {}, clear=True):
            p = XfyunProvider()
            assert p.model == "astron-code-latest"

    def test_chat_uses_openai_sdk(self):
        """xfyun MAAS 与 OpenAI 协议兼容。"""
        with patch.dict(os.environ, {"XFYUN_API_KEY": "xf-test"}):
            p = XfyunProvider()
            with patch("openai.OpenAI") as MockClient:
                mock_instance = MockClient.return_value
                mock_instance.chat.completions.create.return_value = MagicMock(
                    choices=[MagicMock(message=MagicMock(content="xfyun resp"))]
                )
                result = p.chat([{"role": "user", "content": "hi"}])
                assert result == "xfyun resp"
                call_kwargs = MockClient.call_args.kwargs
                assert "xf-yun.com" in call_kwargs.get("base_url", "")


class TestOllamaProvider:
    def test_default_base_url(self):
        with patch.dict(os.environ, {}, clear=True):
            p = OllamaProvider()
            assert "localhost:11434" in p.base_url

    def test_default_model(self):
        with patch.dict(os.environ, {}, clear=True):
            p = OllamaProvider()
            assert p.model == "qwen2.5:7b"

    def test_is_available_when_server_running(self):
        """服务端点存在时 is_available()=True。"""
        p = OllamaProvider()
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            assert p.is_available() is True

    def test_is_unavailable_when_server_down(self):
        p = OllamaProvider()
        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            assert p.is_available() is False

    def test_chat_uses_openai_sdk(self):
        """Ollama 也兼容 OpenAI 协议。"""
        p = OllamaProvider()
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            with patch("openai.OpenAI") as MockClient:
                mock_instance = MockClient.return_value
                mock_instance.chat.completions.create.return_value = MagicMock(
                    choices=[MagicMock(message=MagicMock(content="ollama resp"))]
                )
                result = p.chat([{"role": "user", "content": "hi"}])
                assert result == "ollama resp"
