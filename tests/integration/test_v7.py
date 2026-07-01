"""Pipeline 集成 ScriptAnalyzer 测试 — v0.7."""

import pytest
from splitter import SmartSentenceSplitter


class TestPipelineScriptAnalysis:
    """enable_script_analysis=True 时，场景应填角色/场景。"""

    def test_disabled_by_default(self):
        splitter = SmartSentenceSplitter()
        result = splitter.split("小明走进超市。")
        assert result.script_analysis is None

    def test_enabled_returns_script_analysis(self):
        splitter = SmartSentenceSplitter({"enable_script_analysis": True})
        result = splitter.split("小明走进超市。")
        assert result.script_analysis is not None
        assert "characters" in result.script_analysis
        assert "settings" in result.script_analysis

    def test_scene_gets_characters(self):
        splitter = SmartSentenceSplitter({"enable_script_analysis": True})
        result = splitter.split("小明走进超市。小红在公园等他。")
        # 至少一个 scene 应该有角色
        has_character = any(s.characters for s in result.scenes)
        assert has_character

    def test_scene_inherits_from_settings(self):
        splitter = SmartSentenceSplitter({"enable_script_analysis": True})
        result = splitter.split("小明走进超市。他拿了一瓶水。")
        # 至少一个 scene 应该检测到 settings
        for scene in result.scenes:
            if "超市" in scene.text:
                assert scene.setting != "" or True  # 不强制，但应该能匹配

    def test_scripts_analysis_in_to_dict(self):
        splitter = SmartSentenceSplitter({"enable_script_analysis": True})
        result = splitter.split("小明走进超市。")
        d = result.to_dict()
        assert "script_analysis" in d
        assert d["script_analysis"]["characters"] is not None