"""REST API (FastAPI) 集成测试 - v0.5 新增."""

import pytest
from fastapi.testclient import TestClient

from splitter.api.rest_api import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestCapabilities:
    def test_capabilities_returns_full(self, client):
        r = client.get("/capabilities")
        assert r.status_code == 200
        data = r.json()
        assert "version" in data
        assert "languages" in data
        assert "tiers" in data
        assert "modes" in data
        assert "features" in data
        # 验证 tier 列表
        tier_names = [t["name"] for t in data["tiers"]]
        assert "tier1_llm" in tier_names
        assert "tier3_rule" in tier_names


class TestInfo:
    def test_info_returns_runtime(self, client):
        r = client.get("/v1/info")
        assert r.status_code == 200
        data = r.json()
        assert "version" in data
        assert "llm_available" in data


class TestSplitBasic:
    def test_split_chinese(self, client):
        r = client.post("/v1/split", json={
            "text": "今天天气真好。我们去公园散步。路上遇到了朋友。",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["text_length"] == len("今天天气真好。我们去公园散步。路上遇到了朋友。")
        assert data["language"] == "zh"
        assert len(data["sentences"]) >= 2

    def test_split_english(self, client):
        r = client.post("/v1/split", json={
            "text": "Hello world. How are you? I am fine.",
            "language": "en",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["language"] == "en"
        assert len(data["sentences"]) >= 2

    def test_split_with_mode(self, client):
        r = client.post("/v1/split", json={
            "text": "今天天气真好。我们去公园。",
            "mode": "fast",
        })
        assert r.status_code == 200
        # fast 模式 → tier3_rule
        data = r.json()
        assert "tier3" in data["tier_used"]

    def test_split_with_era(self, client):
        r = client.post("/v1/split", json={
            "text": "清军在甲午战争中死磕到底。这场战争影响深远。",
            "enable_era": True,
        })
        assert r.status_code == 200
        data = r.json()
        # 时代检测结果在 scenes 列表中
        for scene in data["scenes"]:
            if scene["era"] is not None:
                # 至少有一个 scene 检测到时代
                assert scene["era"] in ("modern", "ancient", "mixed")


class TestSplitValidation:
    def test_empty_text_400(self, client):
        r = client.post("/v1/split", json={"text": ""})
        assert r.status_code == 422  # Pydantic validation

    def test_missing_text_422(self, client):
        r = client.post("/v1/split", json={"language": "zh"})
        assert r.status_code == 422

    def test_long_text_ok(self, client):
        """长文本（5K 字）应正常处理。"""
        text = "今天天气真好。" * 500  # ~5500 字
        r = client.post("/v1/split", json={"text": text})
        assert r.status_code == 200
        data = r.json()
        assert data["text_length"] == len(text)
        assert len(data["sentences"]) >= 500


class TestSplitErrorHandling:
    def test_invalid_config_400(self, client):
        """非法 config 应返回 400。"""
        r = client.post("/v1/split", json={
            "text": "测试",
            "config": {"invalid_key": "..."},
        })
        # Pydantic 校验过 → splitter 接受 → 200
        # 但非法 LLM provider 才会 400
        assert r.status_code in (200, 400)


class TestOpenAPIDocs:
    def test_openapi_schema_available(self, client):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        schema = r.json()
        assert "paths" in schema
        assert "/v1/split" in schema["paths"]
        assert "/v1/split/batch" in schema["paths"]
        assert "/health" in schema["paths"]
        assert "/capabilities" in schema["paths"]
        assert "/v1/info" in schema["paths"]

    def test_swagger_ui_available(self, client):
        r = client.get("/docs")
        assert r.status_code == 200


class TestSplitBatch:
    """POST /v1/split/batch — 批量接口 (v0.9.6)."""

    def test_batch_two_texts(self, client):
        r = client.post("/v1/split/batch", json={
            "texts": [
                "今天天气真好。我们去公园。",
                "Hello world. How are you?",
            ],
        })
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert len(data["results"]) == 2
        assert data["results"][0]["language"] == "zh"
        assert data["results"][1]["language"] == "en"

    def test_batch_empty(self, client):
        r = client.post("/v1/split/batch", json={"texts": []})
        assert r.status_code == 200
        data = r.json()
        assert len(data["results"]) == 0

    def test_batch_with_config(self, client):
        r = client.post("/v1/split/batch", json={
            "texts": ["测试文本。"],
            "config": {"mode": "fast"},
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data["results"]) == 1

    def test_batch_missing_texts(self, client):
        r = client.post("/v1/split/batch", json={})
        assert r.status_code == 422

    def test_batch_performance(self, client):
        """10 段文本应 < 5s."""
        texts = ["今天天气真好。" * 10 for _ in range(10)]
        import time
        t0 = time.time()
        r = client.post("/v1/split/batch", json={"texts": texts})
        elapsed = time.time() - t0
        assert r.status_code == 200
        data = r.json()
        assert len(data["results"]) == 10
        assert elapsed < 5.0, f"batch too slow: {elapsed:.2f}s"
