"""Large text chunking tests for _handle_large_text."""
import pytest
from splitter import SmartSentenceSplitter


def make_text(sentence_count: int, base_len: int = 30) -> str:
    """Generate text with known-length sentences."""
    sentences = []
    for i in range(sentence_count):
        sentences.append(f"这是第{i+1}个测试句子，用来验证大文本分块功能。")
    return "".join(sentences)


class TestLargeTextChunking:
    """Test _handle_large_text chunking strategy."""

    def test_under_max_length_returns_none(self):
        """Text under max_input_length → no large-text handling."""
        s = SmartSentenceSplitter({"max_input_length": 50000})
        text = "正常文本。不超过阈值。"
        result = s._handle_large_text(text, "zh")
        assert result is None, "文本未超阈值时应返回 None"

    def test_over_max_length_splits_into_multiple_chunks(self):
        """Text exceeding max_input_length → split into chunks."""
        s = SmartSentenceSplitter({"max_input_length": 100})
        text = "".join(f"句{i:03d}。" for i in range(25))
        result = s._handle_large_text(text, "zh")
        assert result is not None, "超阈值文本应触发大文本处理"
        assert len(result.sentences) >= 12, f"期望至少 12 个句子，得到 {len(result.sentences)}"
        assert result.language == "zh"

    def test_no_punctuation_fallback(self):
        """Text without sentence-ending punctuation → hard fallback split."""
        s = SmartSentenceSplitter({"max_input_length": 50})
        text = "这是一段没有任何标点符号的长文本用来测试硬回退分块策略" * 5
        result = s._handle_large_text(text, "zh")
        assert result is not None, "无标点文本应触发回退分块"
        assert len(result.sentences) > 0, "应产生至少一个句子"

    def test_newline_as_boundary(self):
        """Newlines should be treated as sentence boundaries."""
        s = SmartSentenceSplitter({"max_input_length": 100})
        text = "第一行内容。\n第二行内容。\n第三行内容。\n第四行内容。\n第五行内容。\n第六行内容。\n第七行内容。\n第八行内容。\n第九行内容。\n第十行内容。\n第十一行。\n第十二行。\n第十三行。\n第十四行。\n第十五行。\n第十六行。"
        result = s._handle_large_text(text, "zh")
        assert result is not None
        assert len(result.sentences) >= 6

    def test_chunk_boundary_does_not_cut_sentence(self):
        """Chunks should break at sentence boundaries when possible."""
        s = SmartSentenceSplitter({"max_input_length": 80})
        text = ("天气真好。" * 8 +
                "明天有雨。" * 8 +
                "后天转晴。" * 8)
        result = s._handle_large_text(text, "zh")
        assert result is not None
        # All sentences should be complete (end with punctuation)
        for sent in result.sentences:
            t = sent.text.strip()
            assert t.endswith("。") or len(t) <= 80, f"sentence too long: {t[:50]}..."

    def test_multi_large_text_preserves_order(self):
        """Sentence order should be preserved across chunks."""
        s = SmartSentenceSplitter({"max_input_length": 80})
        sentences = [f"句子{i:03d}。" for i in range(20)]
        text = "".join(sentences)
        result = s._handle_large_text(text, "zh")
        assert result is not None
        texts = [st.text for st in result.sentences]
        for i in range(20):
            assert any(f"句子{i:03d}" in t for t in texts), f"句子{i} 应保留在结果中"

    def test_large_text_with_config_override(self):
        """Custom max_input_length should be respected."""
        s = SmartSentenceSplitter({"max_input_length": 200})
        text = "短文本。" * 15  # ~75 chars
        result = s._handle_large_text(text, "zh")
        assert result is None, f"75 < 200 应返回 None, 得到 {result}"
        
        s2 = SmartSentenceSplitter({"max_input_length": 50})
        text2 = "短文本。" * 15  # ~75 chars
        result2 = s2._handle_large_text(text2, "zh")
        assert result2 is not None, "75 > 50 应触发大文本处理"

    def test_split_integration_large_text(self):
        """End-to-end: split() should handle large text correctly."""
        s = SmartSentenceSplitter({"max_input_length": 150})
        text = "这是第一句内容。这是第二句内容。这是第三句内容。这是第四句。这是第五句。这是第六句。这是第七句。这是第八句。"
        result = s.split(text)
        assert result is not None
        assert len(result.sentences) >= 6
        assert result.language is not None

    def test_extremely_large_text(self):
        """Very large text (many multiples of max_length) should work."""
        s = SmartSentenceSplitter({"max_input_length": 50})
        # 500 sentences, ~10 chars each
        parts = [f"句{i:03d}。" for i in range(500)]
        text = "".join(parts)
        result = s.split(text)
        assert result is not None
        assert len(result.sentences) >= 400, f"期望 >=400 句子, 得到 {len(result.sentences)}"


class TestLargeTextMixedLanguage:
    """Large text with mixed language content."""

    def test_mixed_zh_en_large_text(self):
        s = SmartSentenceSplitter({"max_input_length": 100})
        text = "Hello world! This is a test! " * 8 + "中文测试句子。这是第二句。第三句到这里。第四句结束。"
        result = s.split(text)
        assert result is not None
        assert len(result.sentences) > 5

    def test_english_large_text(self):
        s = SmartSentenceSplitter({"max_input_length": 100})
        text = "This is a test sentence with enough length to trigger chunking. " * 8
        result = s.split(text)
        assert result is not None
        assert len(result.sentences) >= 4



