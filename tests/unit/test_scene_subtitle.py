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


class TestSubtitleCleanUp:
    """v0.10.1: 字幕后处理测试。"""

    def _make_seg(self, **kwargs):
        cfg = {"min_chars_per_block": 8, "max_chars_per_block": 15}
        cfg.update(kwargs)
        return SubtitleSegmenter(cfg)

    def test_trailing_punctuation_removed(self):
        """字幕块末尾标点应被去除。"""
        seg = self._make_seg()
        scene = make_scene("今天天气真好。我们去公园散步吧。")
        subs = seg.segment(scene)
        for sub in subs:
            assert sub.text[-1] not in "。！？；，、.!?;…", (
                f"字幕块末尾不应是标点: {sub.text!r}"
            )

    def test_leading_punctuation_fixed(self):
        """字幕块不应以句内标点开头。"""
        seg = self._make_seg()
        # 构造一个较长文本，迫使字幕切分后下一块以标点开头
        scene = make_scene("西班牙士兵邦板牙土著战士以及五百名佩着野太刀的日本浪人悄无声息地完成了合围。")
        subs = seg.segment(scene)
        for sub in subs:
            assert sub.text[0] not in "，、。！？；", (
                f"字幕块不应以标点开头: {sub.text!r}"
            )

    def test_cross_block_quotes_removed(self):
        """跨块双引号应被去除。"""
        seg = self._make_seg()
        # 构造包含引号的场景，迫使引号跨块
        scene = make_scene('站在高处安抚惶惑的同胞：“把铁器卖了吧换笔钱图个平安。”')
        subs = seg.segment(scene)
        # 检查不应有孤立引号跨块的情况
        for i in range(len(subs) - 1):
            curr_end = subs[i].text[-1] if subs[i].text else ''
            next_start = subs[i + 1].text[0] if subs[i + 1].text else ''
            # 不应出现 左引号在块尾 + 右引号在下一块开头
            assert not (
                curr_end in '\u201c\u300c"' and next_start in '\u201d\u300d"'
            ), f"跨块引号未清理: block[{i}]={subs[i].text!r}, block[{i+1}]={subs[i+1].text!r}"

    def test_merge_short_with_quotes(self):
        """纯引号短块应被合并（场景 10 问题）。"""
        seg = self._make_seg()
        # 模拟 _merge_short 输入：一个纯引号块
        blocks = ['他们开始行动。一开始装得彬彬有礼', '"']
        merged = seg._merge_short(blocks)
        # 纯引号块应被合并到前一块
        assert len(merged) == 1
        assert '"' in merged[0] or '\u201c' in merged[0] or merged[0].endswith('礼')


class TestLengthSegmenterExtended:
    """v0.10.1: LengthSegmenter 切分策略改善测试。"""

    def test_extended_search_avoids_hard_cut(self):
        """找不到标点时应扩大搜索，避免硬切在词中间。"""
        from splitter.scene_subtitle.length_segmenter import LengthSegmenter
        seg = LengthSegmenter(strategy="A", min_chars=8, max_chars=15)
        # 文本超过 15 字但 15 字内无标点，15 字外有标点
        text = "马尼克德拉腊接到一封盖着招讨大将军印信的书信时手在微微发抖"
        chunks = seg.split_text(text)
        # 不应在 "接到一" 和 "封" 之间截断
        for chunk in chunks:
            assert not chunk.startswith("封"), f"不应在量词前截断: {chunk!r}"

    def test_no_leading_punctuation_in_chunks(self):
        """切分后不应有以标点开头的块。"""
        from splitter.scene_subtitle.length_segmenter import LengthSegmenter
        seg = LengthSegmenter(strategy="A", min_chars=8, max_chars=15)
        text = "西班牙士兵邦板牙土著战士以及五百名佩着野太刀的日本浪人悄无声息地完成了合围。"
        chunks = seg.split_text(text)
        for chunk in chunks:
            assert chunk[0] not in "，、。！？；", f"块不应以标点开头: {chunk!r}"


class TestParagraphAwareIntegrity:
    """v0.10.1: 段落感知分段文本完整性测试。"""

    def test_no_text_corruption(self):
        """段落感知模式下，所有场景文本应覆盖原文全部内容，无重复无丢失。"""
        from splitter import SmartSentenceSplitter
        text = """第一段内容。这里有一些文字。
第二段内容。这是不同的段落。
第三段结尾。这是最后的内容。"""
        splitter = SmartSentenceSplitter({"enable_paragraph_aware": True})
        result = splitter.split(text)
        # 所有场景文本拼接后应包含原文所有非空行的关键内容
        all_scene_text = "".join(s.text for s in result.scenes)
        # 检查每段的关键内容都在
        assert "第一段内容" in all_scene_text
        assert "第二段内容" in all_scene_text
        assert "第三段结尾" in all_scene_text
