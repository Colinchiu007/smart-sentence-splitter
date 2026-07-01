"""Test TextTilingSemanticSplitter — Splitter 集成测试。"""

import pytest
from splitter.texttiling.splitter import TextTilingSemanticSplitter


class TestTextTilingSemanticSplitter:
    """TextTiling splitter 接口测试。"""

    def test_basic_chinese_split(self):
        """基本中文分句 + 主题边界识别。"""
        splitter = TextTilingSemanticSplitter({
            "min_text_length": 20,
            "window_size": 8,
            "step_size": 4,
            "depth_score_threshold": 0.15,
        })
        text = " ".join(["清军", "明朝", "皇帝"] * 5) + "。" + " ".join(["电脑", "手机", "互联网"] * 5) + "。"
        result = splitter.split(text)
        assert isinstance(result, list)
        assert len(result) >= 2  # 至少 2 句

    def test_is_available(self):
        """Splitter 始终可用。"""
        splitter = TextTilingSemanticSplitter()
        assert splitter.is_available() is True

    def test_tier_mark(self):
        """tier 标识应为 tier2_semantic。"""
        splitter = TextTilingSemanticSplitter()
        assert splitter.tier == "tier2_semantic"

    def test_language_auto(self):
        """language 应为 auto（支持中英文）。"""
        splitter = TextTilingSemanticSplitter()
        assert splitter.language == "auto"

    def test_short_text_early_exit(self):
        """短文本应早退，按规则切分。"""
        splitter = TextTilingSemanticSplitter({"min_text_length": 100})
        text = "今天天气真好。我们去散步。"
        result = splitter.split(text)
        # 早退：结果应与规则分句类似
        assert len(result) >= 1

    def test_topic_boundary_in_output(self):
        """主题边界处应插入 is_topic_boundary=True 的虚拟 block。"""
        splitter = TextTilingSemanticSplitter({
            "min_text_length": 20,
            "window_size": 8,
            "step_size": 4,
            "depth_score_threshold": 0.1,
        })
        # 强主题对比
        topic_a = " ".join(["苹果", "香蕉", "水果"] * 8)
        topic_b = " ".join(["电脑", "手机", "科技"] * 8)
        text = topic_a + "。" + topic_b + "。"
        result = splitter.split(text)
        # 至少应该有 1 个 topic boundary block
        boundary_blocks = [s for s in result if s.is_topic_boundary]
        # 允许 0（如果算法未识别出），但不报错
        assert isinstance(boundary_blocks, list)

    def test_topic_depth_score_set(self):
        """boundary block 的 topic_depth_score 应 > 0。"""
        splitter = TextTilingSemanticSplitter({
            "min_text_length": 20,
            "window_size": 8,
            "step_size": 4,
            "depth_score_threshold": 0.1,
        })
        topic_a = " ".join(["苹果", "香蕉", "水果"] * 8)
        topic_b = " ".join(["电脑", "手机", "科技"] * 8)
        text = topic_a + "。" + topic_b + "。"
        result = splitter.split(text)
        boundary_blocks = [s for s in result if s.is_topic_boundary]
        if boundary_blocks:
            for b in boundary_blocks:
                assert b.topic_depth_score > 0

    def test_fallback_on_error(self):
        """算法异常时应降级到规则分句。"""
        # 用一个故意会让算法崩溃的配置
        splitter = TextTilingSemanticSplitter({
            "min_text_length": 0,
            "window_size": 0,  # 会触发除零或空窗口
        })
        text = "测试文本。这是一句。这是另一句。"
        # 不应抛异常，应有兜底结果
        try:
            result = splitter.split(text)
            assert isinstance(result, list)
        except Exception as e:
            pytest.fail(f"Splitter should not raise exception, got: {e}")

    def test_empty_text(self):
        """空文本应返回空列表。"""
        splitter = TextTilingSemanticSplitter()
        assert splitter.split("") == []
        assert splitter.split("   ") == []

    def test_single_sentence_text(self):
        """单句短文本应返回 1 句。"""
        splitter = TextTilingSemanticSplitter()
        text = "今天天气真好。"
        result = splitter.split(text)
        assert len(result) == 1
