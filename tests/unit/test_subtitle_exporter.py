"""Test SRT/ASS SubtitleExporter — v0.8 新增."""

import pytest
from splitter.exporter.subtitle_exporter import SubtitleExporter
from splitter.models import SceneSegment, SubtitleBlock, EraInfo


def make_scene(segment_id, text, subs, duration=6.0, era=None, characters=None, setting=""):
    scene = SceneSegment(
        text=text,
        segment_id=segment_id,
        estimated_duration=duration,
        target_words=10,
        era_info=EraInfo(era=era, confidence=0.8) if era else None,
        characters=characters or [],
        setting=setting,
    )
    scene.subtitles = subs
    return scene


def make_sub(text, order, start, duration, parent_id=0):
    return SubtitleBlock(
        text=text,
        display_order=order,
        start_time=start,
        duration=duration,
        parent_segment_id=parent_id,
    )


class TestSRTFormat:
    """SRT 格式测试。"""

    def test_basic_srt(self):
        exporter = SubtitleExporter()
        scenes = [
            make_scene(0, "今天天气真好", [
                make_sub("今天天气真好", 0, 0.0, 3.0, parent_id=0),
            ], duration=3.0),
        ]
        srt = exporter.to_srt(scenes)
        # 序号 + 时间戳 + 文本 + 空行
        assert "1\n" in srt
        assert "00:00:00,000 --> 00:00:03,000" in srt
        assert "今天天气真好" in srt

    def test_multiple_subtitles_sequential(self):
        exporter = SubtitleExporter()
        scenes = [
            make_scene(0, "句1+句2", [
                make_sub("句1", 0, 0.0, 2.0),
                make_sub("句2", 1, 2.5, 2.0),
            ], duration=4.5),
        ]
        srt = exporter.to_srt(scenes)
        assert "1\n" in srt
        assert "2\n" in srt
        assert "00:00:00,000 --> 00:00:02,000" in srt
        assert "00:00:02,500 --> 00:00:04,500" in srt

    def test_timing_calculation(self):
        """跨场景时，下个场景的字幕从累计时间开始。"""
        exporter = SubtitleExporter()
        scenes = [
            make_scene(0, "S1", [make_sub("字幕1", 0, 0.0, 3.0)], duration=3.0),
            make_scene(1, "S2", [make_sub("字幕2", 0, 0.0, 3.0)], duration=3.0),
        ]
        srt = exporter.to_srt(scenes)
        # 场景 1: 0-3s, 场景 2: 3-6s
        assert "00:00:00,000 --> 00:00:03,000" in srt
        assert "00:00:03,000 --> 00:00:06,000" in srt

    def test_srt_with_empty_scenes(self):
        exporter = SubtitleExporter()
        srt = exporter.to_srt([])
        assert srt.strip() == ""


class TestASSFormat:
    """ASS 格式测试。"""

    def test_basic_ass_structure(self):
        exporter = SubtitleExporter()
        scenes = [
            make_scene(0, "测试", [
                make_sub("测试", 0, 0.0, 3.0),
            ], duration=3.0),
        ]
        ass = exporter.to_ass(scenes)
        # ASS 头部
        assert "[Script Info]" in ass
        assert "[V4+ Styles]" in ass
        assert "[Events]" in ass
        assert "Format:" in ass
        # 事件行
        assert "Dialogue:" in ass
        assert "测试" in ass

    def test_ass_uses_time_format(self):
        exporter = SubtitleExporter()
        scenes = [
            make_scene(0, "测试", [
                make_sub("测试", 0, 0.0, 3.0),
            ], duration=3.0),
        ]
        ass = exporter.to_ass(scenes)
        # ASS 时间格式: 0:00:00.00 (小数点)
        assert "0:00:00.00" in ass or "0:00:00,00" in ass
        assert "0:00:03.00" in ass or "0:00:03,00" in ass


class TestSubtitleExporterUtility:
    """通用工具测试。"""

    def test_format_srt_time(self):
        exporter = SubtitleExporter()
        assert exporter._format_srt_time(0.0) == "00:00:00,000"
        assert exporter._format_srt_time(3.5) == "00:00:03,500"
        assert exporter._format_srt_time(65.123) == "00:01:05,123"
        assert exporter._format_srt_time(3661.0) == "01:01:01,000"

    def test_format_ass_time(self):
        exporter = SubtitleExporter()
        assert exporter._format_ass_time(0.0) == "0:00:00.00"
        assert exporter._format_ass_time(3.5) == "0:00:03.50"

    def test_subtitle_count(self):
        exporter = SubtitleExporter()
        scenes = [
            make_scene(0, "S0", [make_sub("A", 0, 0, 1), make_sub("B", 1, 0, 1)]),
            make_scene(1, "S1", [make_sub("C", 0, 0, 1)]),
        ]
        assert exporter.count_subtitles(scenes) == 3

    def test_total_duration(self):
        exporter = SubtitleExporter()
        scenes = [
            make_scene(0, "S0", [], duration=3.0),
            make_scene(1, "S1", [], duration=4.0),
        ]
        assert exporter.total_duration(scenes) == 7.0


class TestIntegrationPipeline:
    """端到端: splitter → subtitle exporter."""

    def test_pipeline_to_srt(self):
        from splitter import SmartSentenceSplitter
        splitter = SmartSentenceSplitter({
            "length": {"strategy": "A", "max_chars": 10},
        })
        result = splitter.split("今天天气真好。阳光明媚。我们去公园散步。")
        exporter = SubtitleExporter()
        srt = exporter.to_srt(result.scenes)
        # 应该有字幕
        assert srt.strip() != ""
        # 有时间戳
        assert "00:00:" in srt
        # 有文本
        assert "今天" in srt or "天气" in srt

    def test_pipeline_to_ass(self):
        from splitter import SmartSentenceSplitter
        splitter = SmartSentenceSplitter({
            "length": {"strategy": "A", "max_chars": 10},
        })
        result = splitter.split("今天天气真好。阳光明媚。")
        exporter = SubtitleExporter()
        ass = exporter.to_ass(result.scenes)
        assert "[Script Info]" in ass
        assert "Dialogue:" in ass