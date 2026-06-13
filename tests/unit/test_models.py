"""Test data models."""

import pytest
from splitter.models import (
    SentenceBlock,
    SubtitleBlock,
    EraInfo,
    SceneSegment,
    SplitResult,
)


class TestSentenceBlock:
    def test_basic_creation(self):
        s = SentenceBlock(text="今天天气真好。", index=0)
        assert s.text == "今天天气真好。"
        assert s.index == 0
        assert s.char_count == 7  # auto calculated
        assert s.tier == "tier3_rule"
        assert s.confidence == 1.0

    def test_empty_text_raises(self):
        with pytest.raises(ValueError):
            SentenceBlock(text="", index=0)

    def test_negative_index_raises(self):
        with pytest.raises(ValueError):
            SentenceBlock(text="hello", index=-1)

    def test_invalid_confidence_raises(self):
        with pytest.raises(ValueError):
            SentenceBlock(text="hello", index=0, confidence=1.5)
        with pytest.raises(ValueError):
            SentenceBlock(text="hello", index=0, confidence=-0.1)

    def test_to_dict(self):
        s = SentenceBlock(text="hello", index=0, language="en", tier="tier1_llm")
        d = s.to_dict()
        assert d["text"] == "hello"
        assert d["language"] == "en"
        assert d["tier"] == "tier1_llm"

    def test_words_and_pos_tags(self):
        s = SentenceBlock(
            text="今天 天气 真好",
            index=0,
            words=["今天", "天气", "真好"],
            pos_tags=["t", "n", "a"],
        )
        assert len(s.words) == 3
        assert len(s.pos_tags) == 3


class TestSubtitleBlock:
    def test_basic_creation(self):
        sub = SubtitleBlock(
            text="今天天气真好",
            display_order=0,
            start_time=0.0,
            duration=2.0,
            parent_segment_id=0,
        )
        assert sub.text == "今天天气真好"
        assert sub.duration == 2.0

    def test_negative_time_raises(self):
        with pytest.raises(ValueError):
            SubtitleBlock(text="hi", display_order=0, start_time=-1, duration=1, parent_segment_id=0)

    def test_to_dict(self):
        sub = SubtitleBlock(text="hi", display_order=0, start_time=0.5, duration=1.5, parent_segment_id=2)
        d = sub.to_dict()
        assert d["parent_segment_id"] == 2


class TestEraInfo:
    def test_valid_eras(self):
        for era in ("modern", "ancient", "mixed"):
            info = EraInfo(era=era, confidence=0.8, keywords=["test"])
            assert info.era == era

    def test_invalid_era_raises(self):
        with pytest.raises(ValueError):
            EraInfo(era="future", confidence=0.5)

    def test_invalid_confidence_raises(self):
        with pytest.raises(ValueError):
            EraInfo(era="modern", confidence=1.5)


class TestSceneSegment:
    def test_basic_creation(self):
        from splitter.models import SentenceBlock
        sentences = [SentenceBlock(text="句子1", index=0), SentenceBlock(text="句子2", index=1)]
        scene = SceneSegment(
            text="句子1句子2",
            segment_id=0,
            estimated_duration=6.0,
            target_words=20,
            sentences=sentences,
        )
        assert scene.segment_id == 0
        assert len(scene.sentences) == 2

    def test_add_sentence(self):
        scene = SceneSegment(text="", segment_id=0, estimated_duration=6.0, target_words=0)
        scene.add_sentence(SentenceBlock(text="测试", index=0))
        assert len(scene.sentences) == 1

    def test_to_dict_contains_era_and_subtitles(self):
        from splitter.models import SubtitleBlock
        scene = SceneSegment(
            text="段落",
            segment_id=0,
            estimated_duration=6.0,
            target_words=10,
            era_info=EraInfo(era="modern", confidence=0.8),
            subtitles=[SubtitleBlock(text="子", display_order=0, start_time=0, duration=2, parent_segment_id=0)],
        )
        d = scene.to_dict()
        assert d["era_info"]["era"] == "modern"
        assert len(d["subtitles"]) == 1


class TestSplitResult:
    def test_empty_result(self):
        r = SplitResult()
        assert r.sentences == []
        assert r.scenes == []

    def test_auto_calculate_totals(self):
        from splitter.models import SceneSegment
        scenes = [
            SceneSegment(text="段落1", segment_id=0, estimated_duration=6.0, target_words=20),
            SceneSegment(text="段落2", segment_id=1, estimated_duration=5.0, target_words=15),
        ]
        r = SplitResult(scenes=scenes)
        assert r.total_scenes == 2
        assert r.total_duration == 11.0
        # "段落1" + "段落2" = 6 字符
        assert r.total_words == 6

    def test_to_dict_structure(self):
        r = SplitResult(tier_used="tier2_semantic", language="zh")
        d = r.to_dict()
        assert "sentences" in d
        assert "scenes" in d
        assert d["tier_used"] == "tier2_semantic"
        assert d["language"] == "zh"
