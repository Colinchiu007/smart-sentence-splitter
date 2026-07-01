"""Test SceneSegment 升级 + storyboard exporter."""

import pytest
from splitter.models import SentenceBlock, SceneSegment, EraInfo
from splitter.exporter.storyboard import StoryboardExporter


# ===== SceneSegment 扩展字段测试 =====

class TestSceneSegmentExtended:
    def test_new_fields_have_defaults(self):
        """新字段有默认值，不破坏旧代码。"""
        scene = SceneSegment(
            text="小明走进超市",
            segment_id=0,
            estimated_duration=3.0,
            target_words=10,
        )
        assert scene.characters == []
        assert scene.setting == ""
        assert scene.mood == ""
        assert scene.story_phase == ""

    def test_new_fields_serialize(self):
        """新字段在 to_dict 中。"""
        scene = SceneSegment(
            text="小明走进超市",
            segment_id=0,
            estimated_duration=3.0,
            target_words=10,
            characters=["小明"],
            setting="超市",
            mood="紧张",
            story_phase="开头",
        )
        d = scene.to_dict()
        assert d["characters"] == ["小明"]
        assert d["setting"] == "超市"
        assert d["mood"] == "紧张"
        assert d["story_phase"] == "开头"

    def test_setting_influences_image_prompt(self):
        """setting 影响 image_prompt 生成。"""
        scene = SceneSegment(
            text="小明在超市货架前",
            segment_id=0,
            estimated_duration=3.0,
            target_words=6,
            characters=["小明"],
            setting="超市",
            mood="焦虑",
        )
        prompt = scene.to_image_hint()
        assert "小明" in prompt
        assert "超市" in prompt


# ===== StoryboardExporter 测试 =====

class TestStoryboardExporter:
    def test_to_storyboard_minimal(self):
        exporter = StoryboardExporter()
        scenes = [
            SceneSegment(text="小明走进超市", segment_id=0, estimated_duration=3.0, target_words=5),
        ]
        storyboard = exporter.to_storyboard(scenes, synopsis="一个故事")
        assert storyboard["story_synopsis"] == "一个故事"
        assert len(storyboard["scenes"]) == 1

    def test_to_storyboard_with_characters(self):
        exporter = StoryboardExporter()
        scenes = [
            SceneSegment(
                text="小明走进超市",
                segment_id=0,
                estimated_duration=3.0,
                target_words=5,
                characters=["小明"],
                setting="超市",
                mood="平静",
            ),
        ]
        storyboard = exporter.to_storyboard(
            scenes,
            synopsis="小明的故事",
            characters=[{"name": "小明", "description": "Q版少年"}],
        )
        assert len(storyboard["characters"]) == 1
        assert "小明" in storyboard["scenes"][0]["characters"]
        assert storyboard["scenes"][0]["image_hint"] is not None

    def test_storyboard_includes_duration(self):
        exporter = StoryboardExporter()
        scenes = [
            SceneSegment(text="小明走进超市", segment_id=0, estimated_duration=3.0, target_words=5),
            SceneSegment(text="他拿了一瓶水", segment_id=1, estimated_duration=4.0, target_words=6),
        ]
        storyboard = exporter.to_storyboard(scenes)
        assert len(storyboard["scenes"]) == 2
        assert storyboard["total_duration"] == pytest.approx(7.0)

    def test_to_storyboard_preserves_context(self):
        exporter = StoryboardExporter()
        scenes = [
            SceneSegment(
                text="小明走进超市",
                segment_id=0, estimated_duration=3.0, target_words=5,
                characters=["小明"], setting="超市", mood="焦虑",
                story_phase="开头",
            ),
        ]
        storyboard = exporter.to_storyboard(
            scenes, synopsis="末世故事",
            characters=[{"name": "小明", "description": "Q版少女"}],
        )
        # 输出应包含 context 信息
        scene = storyboard["scenes"][0]
        assert scene["phase"] == "开头"
        assert scene.get("scene_context") is not None


class TestStoryboardIntegration:
    """全流程集成测试。"""

    def test_split_to_storyboard(self):
        """SmartSentenceSplitter → StoryboardExporter 全流程。"""
        from splitter import SmartSentenceSplitter
        splitter = SmartSentenceSplitter({
            "length": {"strategy": "A", "max_chars": 15},
            "enable_era": True,
        })
        result = splitter.split("小明走进超市。他拿了一瓶水。然后离开了。")
        exporter = StoryboardExporter()
        storyboard = exporter.to_storyboard(result.scenes, synopsis="小明的日常")
        assert len(storyboard["scenes"]) >= 1
        # scenes 应该有 duration 和 image_hint
        for scene in storyboard["scenes"]:
            assert "duration_s" in scene
            assert "image_hint" in scene
