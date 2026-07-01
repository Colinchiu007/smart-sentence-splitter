"""Test PromptEngineExporter — PROJECT-012 → PROJECT-011 桥接."""

import pytest
from splitter.exporter.prompt_engine import PromptEngineExporter
from splitter.models import SentenceBlock, SceneSegment, EraInfo, SplitResult


def sentence(text, idx=0, language="zh", era=None, length_status="ok"):
    """快速构造 SentenceBlock。"""
    return SentenceBlock(
        text=text, index=idx, language=language,
        tier="tier2_semantic", length_status=length_status,
    )


class TestOptimizeRequest:
    def test_basic_conversion(self):
        exporter = PromptEngineExporter()
        s = sentence("今天天气真好。")
        req = exporter.to_optimize_request(s)
        assert req["prompt"] == "今天天气真好。"
        assert req["platform"] == "midjourney"  # zh → midjourney
        assert req["creative_level"] == 5
        assert req["max_length"] == 500

    def test_batch_conversion(self):
        exporter = PromptEngineExporter()
        sentences = [
            sentence("今天天气真好。", idx=0),
            sentence("我们去公园散步。", idx=1),
        ]
        batch = exporter.to_batch_request(sentences)
        assert len(batch) == 2
        assert batch[0]["prompt"] == "今天天气真好。"
        assert batch[1]["prompt"] == "我们去公园散步。"


class TestEraMapping:
    def test_ancient_to_style(self):
        exporter = PromptEngineExporter()
        s = sentence("昔日繁华今何在。", era="ancient")
        req = exporter.to_optimize_request(s, era="ancient")
        # ancient → style like traditional/classical
        assert req.get("style_hint") == "classical"

    def test_modern_to_style(self):
        exporter = PromptEngineExporter()
        s = sentence("今天AI技术发展很快。", era="modern")
        req = exporter.to_optimize_request(s, era="modern")
        assert req.get("style_hint") == "contemporary"


class TestLengthMapping:
    def test_too_long_shortens_max_length(self):
        exporter = PromptEngineExporter()
        s = sentence("这是一句很长很长的句子超过了最大字数限制", length_status="too_long")
        req = exporter.to_optimize_request(s)
        # too_long → 缩短输出
        assert req["max_length"] < 500

    def test_too_short_expands(self):
        exporter = PromptEngineExporter()
        s = sentence("好啊", length_status="too_short")
        req = exporter.to_optimize_request(s)
        assert req["creative_level"] >= 7  # 提高创意程度来扩写


class TestSplitResultExport:
    def test_from_split_result(self):
        """从 SplitResult 导出为批量请求。"""
        exporter = PromptEngineExporter()
        result = SplitResult(
            sentences=[sentence("今天天气真好。"), sentence("我们去公园散步。")],
            scenes=[],
            tier_used="tier2_semantic",
            language="zh",
            config_snapshot={},
        )
        batch = exporter.from_split_result(result)
        assert len(batch) == 2
        assert batch[0]["prompt"] == "今天天气真好。"


class TestEnglishMapping:
    def test_en_to_sd_platform(self):
        exporter = PromptEngineExporter()
        s = sentence("Hello world.", language="en")
        req = exporter.to_optimize_request(s)
        assert req["platform"] == "stable_diffusion"


class TestEdgeCases:
    def test_empty_text_returns_empty(self):
        exporter = PromptEngineExporter()
        req = exporter.to_batch_request([])
        assert req == []
