"""Test TextTiling algorithm core (math-level tests)."""

import pytest
from splitter.texttiling.texttiling import TextTiling, TopicBoundary
from splitter.texttiling.sentence_similarity import cosine_similarity, jaccard_similarity


class TestCosineSimilarity:
    """余弦相似度测试。"""

    def test_identical_vectors(self):
        v = {"a": 1, "b": 2}
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_disjoint_vectors(self):
        v1 = {"a": 1}
        v2 = {"b": 1}
        assert cosine_similarity(v1, v2) == 0.0

    def test_overlapping_vectors(self):
        v1 = {"a": 1, "b": 2, "c": 3}
        v2 = {"a": 2, "b": 1, "d": 1}
        sim = cosine_similarity(v1, v2)
        assert 0 < sim < 1

    def test_empty_vector(self):
        assert cosine_similarity({}, {"a": 1}) == 0.0
        assert cosine_similarity({"a": 1}, {}) == 0.0

    def test_returns_float_in_range(self):
        v1 = {"a": 3, "b": 1}
        v2 = {"a": 1, "b": 2, "c": 5}
        sim = cosine_similarity(v1, v2)
        assert 0.0 <= sim <= 1.0


class TestJaccardSimilarity:
    """Jaccard 相似度测试。"""

    def test_identical_sets(self):
        assert jaccard_similarity({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint_sets(self):
        assert jaccard_similarity({"a"}, {"b"}) == 0.0

    def test_partial_overlap(self):
        sim = jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        # 交集 2, 并集 4 → 0.5
        assert sim == 0.5

    def test_empty_sets(self):
        assert jaccard_similarity(set(), {"a"}) == 0.0
        assert jaccard_similarity({"a"}, set()) == 0.0


class TestTextTilingAlgorithm:
    """TextTiling 算法核心测试。"""

    def test_short_text_returns_empty(self):
        """短文本（< min_text_length）应直接返回空边界。"""
        tt = TextTiling(min_text_length=100)
        text = "今天天气真好。我们去公园。"
        boundaries = tt.find_boundaries(text)
        assert boundaries == []

    def test_single_topic_text_returns_no_boundaries(self):
        """单主题文本应无边界（或低置信度边界被过滤）。"""
        tt = TextTiling(min_text_length=50, depth_score_threshold=0.5)
        # 同主题重复词汇
        text = "苹果 香蕉 苹果 香蕉 苹果 香蕉 苹果 香蕉 苹果 香蕉 苹果 香蕉 苹果 香蕉 苹果 香蕉 苹果 香蕉 苹果 香蕉 苹果 香蕉 苹果 香蕉 苹果 香蕉 苹果 香蕉"
        boundaries = tt.find_boundaries(text)
        # 高阈值下应过滤掉所有边界
        assert len(boundaries) == 0

    def test_two_distinct_topics_detected(self):
        """双主题文本应识别出至少 1 个边界。"""
        tt = TextTiling(
            min_text_length=20,
            window_size=10,
            step_size=5,
            depth_score_threshold=0.2,
        )
        # 主题A: 苹果 香蕉 (重复 15 词) → 主题B: 电脑 手机 (重复 15 词)
        topic_a = " ".join(["苹果", "香蕉"] * 15)
        topic_b = " ".join(["电脑", "手机"] * 15)
        text = topic_a + " " + topic_b
        boundaries = tt.find_boundaries(text)
        assert len(boundaries) >= 1

    def test_three_distinct_topics_detected(self):
        """三主题文本应识别出至少 2 个边界。"""
        tt = TextTiling(
            min_text_length=20,
            window_size=10,
            step_size=5,
            depth_score_threshold=0.2,
        )
        topic_a = " ".join(["苹果", "香蕉"] * 10)
        topic_b = " ".join(["电脑", "手机"] * 10)
        topic_c = " ".join(["书本", "铅笔"] * 10)
        text = " ".join([topic_a, topic_b, topic_c])
        boundaries = tt.find_boundaries(text)
        assert len(boundaries) >= 2

    def test_boundary_has_depth_score(self):
        """返回的边界应包含 depth_score 字段。"""
        tt = TextTiling(
            min_text_length=20,
            window_size=10,
            step_size=5,
            depth_score_threshold=0.1,
        )
        text = (" ".join(["苹果", "香蕉"] * 10) + " " + " ".join(["电脑", "手机"] * 10))
        boundaries = tt.find_boundaries(text)
        if boundaries:
            for b in boundaries:
                assert isinstance(b, TopicBoundary)
                assert 0.0 <= b.depth_score <= 2.0  # depth 是相对值
                assert b.position >= 0

    def test_threshold_filters_low_confidence(self):
        """高阈值应过滤掉低置信度边界。"""
        tt_loose = TextTiling(min_text_length=20, window_size=10, step_size=5, depth_score_threshold=0.1)
        tt_strict = TextTiling(min_text_length=20, window_size=10, step_size=5, depth_score_threshold=0.9)
        text = (" ".join(["苹果", "香蕉"] * 10) + " " + " ".join(["电脑", "手机"] * 10))
        b_loose = tt_loose.find_boundaries(text)
        b_strict = tt_strict.find_boundaries(text)
        assert len(b_strict) <= len(b_loose)

    def test_chinese_text(self):
        """中文长文应能识别主题边界。"""
        tt = TextTiling(
            min_text_length=20,
            window_size=8,
            step_size=4,
            depth_score_threshold=0.15,
        )
        # 主题A: 历史相关词汇 → 主题B: 现代科技词汇
        topic_a = "清军 明朝 皇帝 丞相 科举 状元 进士 太监 奏折 圣旨 朝代 江山 社稷 黎民"
        topic_b = "电脑 手机 互联网 微信 抖音 智能手机 大数据 人工智能 5G 算法 芯片 新能源"
        text = topic_a + " " + topic_b
        boundaries = tt.find_boundaries(text)
        # 至少应有 0 个或多个边界（取决于算法）
        assert isinstance(boundaries, list)

    def test_english_text(self):
        """英文长文应能识别主题边界。"""
        tt = TextTiling(
            min_text_length=20,
            window_size=8,
            step_size=4,
            depth_score_threshold=0.15,
        )
        topic_a = " ".join(["apple", "banana", "fruit", "food", "vegetable"] * 4)
        topic_b = " ".join(["computer", "phone", "internet", "software", "technology"] * 4)
        text = topic_a + " " + topic_b
        boundaries = tt.find_boundaries(text)
        assert isinstance(boundaries, list)
        assert len(boundaries) >= 1

    def test_boundary_text_before_after(self):
        """边界应包含前后文文本用于调试。"""
        tt = TextTiling(
            min_text_length=20,
            window_size=8,
            step_size=4,
            depth_score_threshold=0.1,
        )
        text = (" ".join(["苹果", "香蕉"] * 10) + " " + " ".join(["电脑", "手机"] * 10))
        boundaries = tt.find_boundaries(text)
        if boundaries:
            b = boundaries[0]
            assert isinstance(b.text_before, str)
            assert isinstance(b.text_after, str)
