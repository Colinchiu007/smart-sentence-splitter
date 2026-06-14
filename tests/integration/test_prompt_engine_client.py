"""Test PROJECT-011 HTTP 桥接 — v0.8 端到端."""

import pytest
from splitter.exporter.prompt_engine import PromptEngineExporter
from splitter.exporter.prompt_engine_client import PromptEngineClient
from splitter.models import SentenceBlock, SceneSegment
from splitter import SmartSentenceSplitter


class TestPromptEngineClientUnit:
    """HTTP 客户端单元测试 (mock HTTP)."""

    def test_client_init_default(self):
        client = PromptEngineClient()
        assert client.base_url == "http://localhost:8013"

    def test_client_init_custom_url(self):
        client = PromptEngineClient(base_url="http://api.example.com")
        assert client.base_url == "http://api.example.com"

    def test_build_request_payload(self):
        client = PromptEngineClient()
        exporter = PromptEngineExporter()
        sentences = [SentenceBlock(text="test", index=0, language="zh")]
        req = exporter.to_optimize_request(sentences[0])
        payload = client.build_optimize_payload(req)
        assert "prompt" in payload
        assert "platform" in payload
        assert payload["prompt"] == "test"

    def test_parse_response(self):
        client = PromptEngineClient()
        resp = {
            "optimized_prompt": "enhanced",
            "platform": "mj",
            "tokens_used": 100,
            "duration_ms": 500,
        }
        parsed = client.parse_optimize_response(resp)
        assert parsed["optimized_prompt"] == "enhanced"
        assert parsed["tokens_used"] == 100


class TestPromptEngineClientEndToEnd:
    """端到端测试 — 真实调用 PROJECT-011 (需 xfyun key).

    跑法:
        export OPENAI_API_KEY=*** 或
        xfyun key 自动从 prompt-engine config.yaml 读
        pytest tests/integration/test_prompt_engine_client.py -v
    """
    import os

    @pytest.mark.skipif(
        not os.getenv("RUN_PROMPT_ENGINE_E2E"),
        reason="需要 RUN_PROMPT_ENGINE_E2E=1 真实调用 PROJECT-011"
    )
    def test_real_health(self):
        client = PromptEngineClient(base_url="http://localhost:8013", timeout=10)
        is_healthy = client.health_check()
        assert is_healthy is True

    @pytest.mark.skipif(
        not os.getenv("RUN_PROMPT_ENGINE_E2E"),
        reason="需要 RUN_PROMPT_ENGINE_E2E=1 真实调用 PROJECT-011"
    )
    def test_real_optimize_one(self):
        client = PromptEngineClient()
        req = {"prompt": "今天天气真好", "platform": "mj", "creative_level": 5}
        result = client.optimize(req)
        assert result["optimized_prompt"]
        assert result["tokens_used"] > 0


class TestStoryboardPipeline:
    """端到端: splitter → prompt_engine client。"""

    def test_split_to_payloads_no_http(self):
        """纯数据转换测试 (无 HTTP)."""
        splitter = SmartSentenceSplitter({
            "length": {"strategy": "A", "max_chars": 15},
        })
        result = splitter.split("今天天气真好。阳光明媚。")
        exporter = PromptEngineExporter()
        client = PromptEngineClient()

        # 模拟批量请求 (不真发 HTTP)
        scenes = result.scenes
        payloads = []
        for scene in scenes:
            for sentence in scene.sentences:
                req = exporter.to_optimize_request(sentence)
                payload = client.build_optimize_payload(req)
                payloads.append(payload)

        assert len(payloads) >= 1
        for p in payloads:
            assert "prompt" in p
            assert "platform" in p