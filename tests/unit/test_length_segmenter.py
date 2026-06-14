"""Test length_strategy (A 重切 / B 标尺) — v0.6 新增."""

import pytest
from splitter.scene_subtitle.length_segmenter import LengthSegmenter
from splitter.models import SentenceBlock


def make_sentence(text, idx=0):
    return SentenceBlock(text=text, index=idx, tier="tier2_semantic", language="zh")


class TestLengthSegmenterConfig:
    def test_default_config(self):
        seg = LengthSegmenter()
        assert seg.strategy == "B"
        assert seg.min_chars == 3
        assert seg.max_chars == 15

    def test_invalid_strategy_raises(self):
        with pytest.raises(ValueError, match="strategy"):
            LengthSegmenter(strategy="X")

    def test_min_max_validation(self):
        with pytest.raises(ValueError, match="min_chars"):
            LengthSegmenter(min_chars=10, max_chars=5)


class TestLengthStrategyOff:
    def test_off_passthrough(self):
        seg = LengthSegmenter(strategy="off")
        sentences = [make_sentence("hello world", 0)]
        result = seg.segment(sentences)
        assert len(result) == 1
        assert result[0].text == "hello world"
        assert result[0].length_status == "ok"
        assert result[0].length_strategy_applied == "none"


class TestLengthStrategyB:
    """B 模式：标尺，不切，标记状态。"""

    def test_b_ok_status(self):
        seg = LengthSegmenter(strategy="B", min_chars=3, max_chars=15)
        result = seg.segment([make_sentence("今天天气真好", 0)])
        assert len(result) == 1
        assert result[0].length_status == "ok"

    def test_b_too_short_status(self):
        seg = LengthSegmenter(strategy="B", min_chars=3, max_chars=15)
        result = seg.segment([make_sentence("好啊", 0)])
        assert len(result) == 1
        assert result[0].length_status == "too_short"

    def test_b_too_long_status(self):
        seg = LengthSegmenter(strategy="B", min_chars=3, max_chars=15)
        result = seg.segment([make_sentence("这是一句很长很长的句子超过了最大字数限制", 0)])
        assert len(result) == 1
        assert result[0].length_status == "too_long"

    def test_b_does_not_split(self):
        """B 模式不切，仅打标。"""
        seg = LengthSegmenter(strategy="B", min_chars=3, max_chars=15)
        long_text = "这是一句很长很长的句子超过了最大字数限制"
        result = seg.segment([make_sentence(long_text, 0)])
        assert len(result) == 1
        assert result[0].text == long_text
        assert result[0].length_strategy_applied == "B"

    def test_b_collects_warnings(self):
        seg = LengthSegmenter(strategy="B", min_chars=3, max_chars=15)
        sentences = [
            make_sentence("好啊", 0),                                          # too_short
            make_sentence("今天天气真好", 1),                                # ok
            make_sentence("这是一句很长很长的句子超过了最大字数限制", 2),    # too_long
        ]
        result = seg.segment(sentences)
        assert len(seg.warnings) == 2
        assert any("too_short" in w for w in seg.warnings)
        assert any("too_long" in w for w in seg.warnings)

    def test_b_no_warnings_on_ok(self):
        seg = LengthSegmenter(strategy="B", min_chars=3, max_chars=15)
        result = seg.segment([
            make_sentence("今天天气真好", 0),
            make_sentence("我们去公园", 1),
        ])
        assert len(seg.warnings) == 0


class TestLengthStrategyA:
    """A 模式：按字数重切。"""

    def test_a_short_passthrough(self):
        """短句不切。"""
        seg = LengthSegmenter(strategy="A", min_chars=3, max_chars=15)
        result = seg.segment([make_sentence("今天天气真好", 0)])
        assert len(result) == 1
        assert result[0].text == "今天天气真好"

    def test_a_split_at_punctuation(self):
        """长句在标点处切。"""
        seg = LengthSegmenter(strategy="A", min_chars=3, max_chars=15)
        long_text = "今天天气真好，阳光明媚，我们决定去公园散步"
        result = seg.segment([make_sentence(long_text, 0)])
        # 期望: 在 '，' 处切
        assert len(result) >= 2
        # 第一块应在标点处结束
        assert any("，" in r.text or "。" in r.text for r in result[:-1])

    def test_a_no_substring_split_when_punctuation_available(self):
        """如果有标点可用，不应在中文字符中间硬切。

        18 字 > 15，所以应切。
        """
        seg = LengthSegmenter(strategy="A", min_chars=3, max_chars=15)
        text = "今天天气真好，阳光明媚，天气预报说明天更好"  # 18 字
        result = seg.segment([make_sentence(text, 0)])
        # 18 字 > 15, 应切
        assert len(result) >= 2
        # 验证每块都在标点处结束 (除最后一块)
        for r in result[:-1]:
            assert any(p in r.text for p in "，。！？；.!?;"), f"应标点结尾: {r.text!r}"

    def test_a_force_split_when_no_punctuation(self):
        """无标点时按 max_chars 强制切。"""
        seg = LengthSegmenter(strategy="A", min_chars=3, max_chars=15)
        # 30 字无标点
        text = "今天天气很好我们决定出门走走一路看风景心情好极了"
        result = seg.segment([make_sentence(text, 0)])
        # 至少 2 块
        assert len(result) >= 2
        # 每块不应超 max_chars
        for r in result:
            assert len(r.text) <= 15, f"块超长: {r.text!r}"

    def test_a_marks_strategy_in_block(self):
        seg = LengthSegmenter(strategy="A", min_chars=3, max_chars=15)
        result = seg.segment([make_sentence("今天天气真好，阳光明媚", 0)])
        for r in result:
            assert r.length_strategy_applied == "A"

    def test_a_english_uses_english_punctuation(self):
        """英文文本用 . , 切。"""
        seg = LengthSegmenter(strategy="A", min_chars=3, max_chars=15)
        text = "Hello world, this is a long sentence that needs splitting for sure"
        result = seg.segment([make_sentence(text, 0)])
        # 应该在 ',' 处切
        assert len(result) >= 2
        # 第一块不应超 15
        for r in result:
            assert len(r.text) <= 15

    def test_a_min_chars_respected(self):
        """切完后每块至少 min_chars (除最后一块)."""
        seg = LengthSegmenter(strategy="A", min_chars=3, max_chars=10)
        text = "今天天气真好，我们决定去公园，阳光明媚，花儿盛开"
        result = seg.segment([make_sentence(text, 0)])
        # 除最后一块外，都 >= min_chars
        for r in result[:-1]:
            assert len(r.text) >= 3, f"块过短: {r.text!r}"


class TestLengthSegmenterEdgeCases:
    def test_empty_input(self):
        seg = LengthSegmenter(strategy="A")
        result = seg.segment([])
        assert result == []

    def test_empty_sentence(self):
        """输入中含空字符串应被过滤。"""
        seg = LengthSegmenter(strategy="A")
        # 用 non-empty sentence 测
        result = seg.segment([make_sentence("hello", 0)])
        assert all(r.text for r in result)
        # 空输入列表
        result = seg.segment([])
        assert result == []

    def test_single_char(self):
        seg = LengthSegmenter(strategy="A", min_chars=3, max_chars=15)
        result = seg.segment([make_sentence("啊", 0)])
        # < min_chars, 但无标点, 应保留
        assert len(result) == 1
        assert result[0].text == "啊"

    def test_preserves_language(self):
        seg = LengthSegmenter(strategy="A")
        result = seg.segment([make_sentence("Hello world, this is English", 0)])
        for r in result:
            assert r.language in ("zh", "en", "auto", "mixed")
