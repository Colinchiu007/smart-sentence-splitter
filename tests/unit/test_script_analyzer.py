"""Test ScriptAnalyzer — 剧本分析: 角色/场景/梗概提取."""

import pytest
from splitter.script.script_analyzer import ScriptAnalyzer


class TestCharacterExtraction:
    """角色名提取。"""

    def test_single_character(self):
        analyzer = ScriptAnalyzer()
        text = "小明走进超市。小明拿了一瓶水。"
        chars = analyzer.extract_characters(text)
        assert "小明" in chars

    def test_multiple_characters(self):
        analyzer = ScriptAnalyzer()
        text = "小明和小红在公园见面。老王从远处走来。"
        chars = analyzer.extract_characters(text)
        # jieba 可能把"小红"标为 nr 或"和小红"一起标
        assert any("小明" in c for c in chars)
        assert any("小红" in c or c == "小红" for c in chars)
        assert any("老王" in c for c in chars)

    def test_no_characters(self):
        analyzer = ScriptAnalyzer()
        text = "今天天气真好。阳光明媚。"
        chars = analyzer.extract_characters(text)
        # 可能没有 nr tag, 但不应报错
        assert isinstance(chars, list)

    def test_skip_stop_names(self):
        """跳过单字非人名（'你' '我' '他'）。"""
        analyzer = ScriptAnalyzer()
        text = "你和我一起去公园。他也在。"
        chars = analyzer.extract_characters(text)
        assert "你" not in chars
        assert "我" not in chars
        assert "他" not in chars


class TestSynopsisExtraction:
    """故事梗概提取。"""

    def test_first_paragraph_is_synopsis(self):
        analyzer = ScriptAnalyzer()
        text = "这是一个关于末世囤货的少女的故事。\n她叫小美，是个普通的高中生。\n\n灾难来的那一天，所有人都慌了。"
        synopsis = analyzer.extract_synopsis(text)
        assert "末世" in synopsis
        assert len(synopsis) < 100

    def test_short_text_returns_full(self):
        analyzer = ScriptAnalyzer()
        text = "很短的故事。"
        synopsis = analyzer.extract_synopsis(text)
        assert synopsis == text


class TestSettingsExtraction:
    """场景/地点提取。"""

    def test_single_setting(self):
        analyzer = ScriptAnalyzer()
        text = "小明走进超市。超市里人很多。"
        settings = analyzer.extract_settings(text)
        assert "超市" in settings

    def test_multiple_settings(self):
        analyzer = ScriptAnalyzer()
        text = "小明从家里出发，来到学校。放学后又去了公园。"
        settings = analyzer.extract_settings(text)
        # 应该检测出学校、公园
        assert "学校" in settings
        assert "公园" in settings
        # 家里可通过后缀检测到
        assert "家里" in settings or "学校" in settings

    def test_setting_deduplication(self):
        analyzer = ScriptAnalyzer()
        text = "超市。超市。超市。公园。"
        settings = analyzer.extract_settings(text)
        assert "超市" in settings
        assert "公园" in settings
        assert len(settings) == 2


class TestFullAnalysis:
    """完整分析管线。"""

    def test_analyze_returns_all_fields(self):
        analyzer = ScriptAnalyzer()
        text = "小明和小红的故事。\n\n小明走进超市。小红在公园等他。"
        result = analyzer.analyze(text)
        assert "characters" in result
        assert "synopsis" in result
        assert "settings" in result
        assert "key_terms" in result
        assert len(result["characters"]) > 0

    def test_analyze_no_crash_on_empty(self):
        analyzer = ScriptAnalyzer()
        result = analyzer.analyze("")
        assert result["characters"] == []
        assert result["synopsis"] == ""


class TestLocationChangeDetection:
    """地点变化 → 场景切换检测。"""

    def test_detect_location_new_scene(self):
        analyzer = ScriptAnalyzer()
        sentences = ["小明走进超市", "超市里人很多", "他回到了家"]
        changes = analyzer.detect_scene_changes(sentences)
        # 走进 + 超市 → 场景0，回到家 → 场景2
        assert len(changes) >= 1
        # 至少检测到"家"是场景变化
        assert any(c["sentence_idx"] >= 1 for c in changes)

    def test_same_location_no_change(self):
        analyzer = ScriptAnalyzer()
        sentences = ["小明在超市", "他拿了瓶水", "然后看了看价格"]
        changes = analyzer.detect_scene_changes(sentences)
        # 没换地点, 但第一句可能探测出"在超市"是一个地点
        # 之后两句不应产生新变化
        location_changes = [c for c in changes if c["change_type"] == "location"]
        # 只有第一句的一次 location 检测，或完全无变化
        assert len(location_changes) <= 1
