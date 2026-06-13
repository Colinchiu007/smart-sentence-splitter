"""End-to-end integration test: full pipeline."""

import pytest
from splitter import SmartSentenceSplitter


class TestPipelineChinese:
    def test_basic_chinese_pipeline(self):
        splitter = SmartSentenceSplitter()
        text = "今天天气真好。我们去公园散步。路上遇到了朋友。"
        result = splitter.split(text)
        assert len(result.scenes) >= 1
        assert result.language == "zh"
        assert len(result.sentences) >= 3

    def test_zh_pipeline_with_era(self):
        splitter = SmartSentenceSplitter({"enable_era": True})
        text = "清军在甲午战争中死磕到底。这是一场惨烈的战争。"
        result = splitter.split(text)
        assert result.language == "zh"
        # 第一段应检测为 ancient
        if result.scenes:
            # 至少有一个 scene 的 era_info 是 ancient
            assert any(
                s.era_info and s.era_info.era == "ancient"
                for s in result.scenes
            )

    def test_chinese_with_jieba(self):
        # 装好 jieba 的环境
        splitter = SmartSentenceSplitter()
        text = "今天天气真好。"
        result = splitter.split(text)
        assert len(result.sentences) >= 1
        # 至少 tier 名称应该存在
        assert "tier" in result.tier_used


class TestPipelineEnglish:
    def test_basic_english_pipeline(self):
        splitter = SmartSentenceSplitter()
        text = "Hello world. This is a test. How are you?"
        result = splitter.split(text)
        assert len(result.scenes) >= 1
        assert result.language == "en"
        assert len(result.sentences) >= 2

    def test_english_with_abbreviation(self):
        splitter = SmartSentenceSplitter()
        text = "Dr. Smith and Mr. Wang went to the U.S. yesterday."
        result = splitter.split(text)
        # 缩写不应触发切分
        # 至少不应该切成 4 句（每个 . 都切）
        assert len(result.sentences) <= 2


class TestPipelineMixed:
    def test_auto_detect_mixed(self):
        splitter = SmartSentenceSplitter()
        text = "今天我在 Apple Store 买了一个 iPhone 真的很好用"
        result = splitter.split(text)
        # auto 模式应识别为 mixed 或 zh
        assert result.language in ("zh", "mixed", "en")


class TestPipelineConfig:
    def test_custom_scene_config(self):
        splitter = SmartSentenceSplitter({
            "scene": {
                "target_seconds": 3.0,
                "min_words_per_segment": 5,
                "max_words_per_segment": 20,
            }
        })
        text = "今天天气真好。明天也会很好。"
        result = splitter.split(text)
        # 较小目标字数 → 较多场景
        assert result.total_scenes >= 1

    def test_empty_input(self):
        splitter = SmartSentenceSplitter()
        result = splitter.split("")
        assert result.total_scenes == 0
        assert result.total_words == 0

    def test_result_to_dict(self):
        splitter = SmartSentenceSplitter()
        text = "今天天气真好。"
        result = splitter.split(text)
        d = result.to_dict()
        assert "sentences" in d
        assert "scenes" in d
        assert "tier_used" in d
        assert "language" in d
        assert "total_duration" in d
