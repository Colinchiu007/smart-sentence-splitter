"""Test era detector (Chinese)."""

import pytest
from splitter.era.detector import EraDetector


class TestEraDetector:
    def setup_method(self):
        self.detector = EraDetector()

    def test_ancient_text(self):
        result = self.detector.detect("清军在甲午战争中死磕到底")
        assert result.era == "ancient"

    def test_modern_text(self):
        result = self.detector.detect("台风过境后，居民在社区服务中心领取救济物资")
        assert result.era == "modern"

    def test_mixed_text(self):
        result = self.detector.detect("今天天气真好")
        assert result.era == "mixed"

    def test_wang_yangming_ancient(self):
        result = self.detector.detect("王阳明在龙场悟道")
        assert result.era == "ancient"

    def test_smartphone_modern(self):
        result = self.detector.detect("华为发布新款智能手机")
        assert result.era == "modern"

    def test_empty_returns_mixed(self):
        result = self.detector.detect("")
        assert result.era == "mixed"
        assert result.confidence == 0.0

    def test_short_text_returns_mixed(self):
        result = self.detector.detect("hi")
        assert result.era == "mixed"

    def test_confidence_in_range(self):
        result = self.detector.detect("清军甲午战争")
        assert 0.0 <= result.confidence <= 1.0

    def test_keywords_returned(self):
        result = self.detector.detect("清军在甲午战争中死磕到底")
        assert len(result.keywords) > 0
        assert any("清" in kw or "甲午" in kw for kw in result.keywords)

    def test_batch(self):
        texts = [
            "清军甲午战争",
            "华为智能手机发布",
            "今天天气真好",
        ]
        results = self.detector.detect_batch(texts)
        assert len(results) == 3
        assert results[0].era == "ancient"
        assert results[1].era == "modern"
        assert results[2].era == "mixed"
