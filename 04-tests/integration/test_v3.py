"""v0.3 集成测试."""
import pytest
from splitter import SmartSentenceSplitter
from splitter.postprocessor import PostprocessorChain, BasePostprocessor
from splitter.tiers.tier1_llm import LLMSplitter
from splitter.languages.zh.ac import Match


class TestV3PostprocessorIntegration:
    def test_chain_runs_in_pipeline(self):
        splitter = SmartSentenceSplitter({"enable_era": True})
        result = splitter.split("今天天气真好。")
        assert result is not None

    def test_chain_silent_on_error(self):
        class BrokenPostprocessor(BasePostprocessor):
            name = "broken"
            def adjust(self, result):
                raise RuntimeError("simulated failure")
            def is_available(self):
                return True
        chain = PostprocessorChain([BrokenPostprocessor()])
        from splitter.models import SplitResult
        r = SplitResult(language="zh")
        new = chain.run(r)
        assert new is r

    def test_postprocessor_chain_in_pipeline(self):
        splitter = SmartSentenceSplitter()
        assert isinstance(splitter.postprocessor_chain, PostprocessorChain)


class TestV3LazyEraDetector:
    def test_era_detector_not_loaded_by_default(self):
        splitter = SmartSentenceSplitter()
        assert splitter._era_detector_instance is None

    def test_era_detector_loaded_on_demand(self):
        splitter = SmartSentenceSplitter({"enable_era": True})
        assert splitter._era_detector_instance is None
        _ = splitter.era_detector
        assert splitter._era_detector_instance is not None


class TestV3ModePrecise:
    def test_mode_precise_enables_topic_seg(self):
        splitter = SmartSentenceSplitter({"mode": "precise"})
        splitter._apply_mode()
        assert splitter.config.get("enable_topic_segmentation") is True
        assert splitter._override_min_tier == 1

    def test_mode_fast_disables_topic_seg(self):
        splitter = SmartSentenceSplitter({"mode": "fast", "enable_topic_segmentation": True})
        splitter._apply_mode()
        # fast 模式不应改 enable_topic_segmentation（但 min_tier 应为 3）
        assert splitter._override_min_tier == 3

    def test_mode_balanced_default(self):
        splitter = SmartSentenceSplitter()
        original_topic = splitter.config["enable_topic_segmentation"]
        original_tier = splitter.config["min_tier"]
        splitter._apply_mode()
        assert splitter.config["enable_topic_segmentation"] == original_topic
        assert splitter.config["min_tier"] == original_tier


class TestV3LLMTierStub:
    def test_llm_splitter_unavailable(self):
        s = LLMSplitter()
        assert s.is_available() is False

    def test_llm_splitter_split_raises(self):
        s = LLMSplitter()
        with pytest.raises(NotImplementedError):
            s.split("测试文本")

    def test_llm_splitter_repr(self):
        s = LLMSplitter({"provider": "openai", "model": "gpt-4o-mini"})
        r = repr(s)
        assert "openai" in r
        assert "gpt-4o-mini" in r
