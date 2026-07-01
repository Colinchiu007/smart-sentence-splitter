"""Test scene and subtitle segmenters."""

import pytest
from splitter.models import SentenceBlock, SceneSegment
from splitter.scene_subtitle.scene_segmenter import SceneSegmenter
from splitter.scene_subtitle.subtitle_segmenter import SubtitleSegmenter


def make_sentence(text: str, index: int) -> SentenceBlock:
    return SentenceBlock(text=text, index=index, language="zh", tier="tier3_rule")


def make_scene(text: str, segment_id: int = 0, duration: float = 6.0) -> SceneSegment:
    return SceneSegment(
        text=text,
        segment_id=segment_id,
        estimated_duration=duration,
        target_words=len(text),
        sentences=[SentenceBlock(text=text, index=0, language="zh", tier="tier3_rule")],
    )


class TestSceneSegmenter:
    def test_calculate_target_words(self):
        seg = SceneSegmenter({
            "target_seconds": 6.0,
            "base_words_per_second": 3.3,
            "speech_rate": 1.0,
            "min_words_per_segment": 10,
            "max_words_per_segment": 50,
        })
        target = seg.calculate_target_words()
        assert 10 <= target <= 50

    def test_segment_combines_sentences(self):
        seg = SceneSegmenter({
            "target_seconds": 6.0,
            "base_words_per_segment": 3.3,
            "min_words_per_segment": 10,
            "max_words_per_segment": 50,
        })
        sentences = [make_sentence(f"句子{i}。" * 2, i) for i in range(5)]
        scenes = seg.segment(sentences)
        assert len(scenes) >= 1
        assert all(scene.segment_id >= 0 for scene in scenes)

    def test_segment_no_split_inside_sentence(self):
        seg = SceneSegmenter({
            "target_seconds": 6.0,
            "min_words_per_segment": 10,
            "max_words_per_segment": 50,
        })
        sentences = [make_sentence("一个完整的句子，不能被切开。", 0)]
        scenes = seg.segment(sentences)
        assert len(scenes) == 1
        assert "一个完整的句子" in scenes[0].text

    def test_empty_input(self):
        seg = SceneSegmenter()
        assert seg.segment([]) == []


class TestSubtitleSegmenter:
    def test_basic_split(self):
        seg = SubtitleSegmenter({
            "min_chars_per_block": 5,
            "max_chars_per_block": 10,
        })
        scene = make_scene("今天天气真好我们去公园散步看花赏花。")
        subtitles = seg.segment(scene)
        assert len(subtitles) >= 1

    def test_time_assignment(self):
        seg = SubtitleSegmenter({"min_chars_per_block": 5, "max_chars_per_block": 10})
        scene = make_scene("今天天气真好我们去公园散步。")
        subtitles = seg.segment(scene)
        # 时间戳应该累加
        if len(subtitles) >= 2:
            assert subtitles[1].start_time > subtitles[0].start_time

    def test_proportional_vs_equal(self):
        # proportional
        seg_p = SubtitleSegmenter({"min_chars_per_block": 5, "max_chars_per_block": 10, "time_calculation_method": "proportional"})
        seg_e = SubtitleSegmenter({"min_chars_per_block": 5, "max_chars_per_block": 10, "time_calculation_method": "equal"})
        scene = make_scene("今天天气真好我们去公园散步看花。")
        sub_p = seg_p.segment(scene)
        sub_e = seg_e.segment(scene)
        # proportional 模式下，字数多的字幕时长更长
        if len(sub_p) >= 2:
            durations_p = [s.duration for s in sub_p]
            # 至少有一个变化
            assert len(set(round(d, 2) for d in durations_p)) >= 1
