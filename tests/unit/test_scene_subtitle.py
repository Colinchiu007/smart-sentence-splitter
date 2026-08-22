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
        seg = SceneSegmenter(
            {
                "target_seconds": 6.0,
                "base_words_per_second": 3.3,
                "speech_rate": 1.0,
                "min_words_per_segment": 10,
                "max_words_per_segment": 50,
            }
        )
        target = seg.calculate_target_words()
        assert 10 <= target <= 50

    def test_segment_combines_sentences(self):
        seg = SceneSegmenter(
            {
                "target_seconds": 6.0,
                "base_words_per_segment": 3.3,
                "min_words_per_segment": 10,
                "max_words_per_segment": 50,
            }
        )
        sentences = [make_sentence(f"句子{i}。" * 2, i) for i in range(5)]
        scenes = seg.segment(sentences)
        assert len(scenes) >= 1
        assert all(scene.segment_id >= 0 for scene in scenes)

    def test_segment_no_split_inside_sentence(self):
        seg = SceneSegmenter(
            {
                "target_seconds": 6.0,
                "min_words_per_segment": 10,
                "max_words_per_segment": 50,
            }
        )
        sentences = [make_sentence("一个完整的句子，不能被切开。", 0)]
        scenes = seg.segment(sentences)
        assert len(scenes) == 1
        assert "一个完整的句子" in scenes[0].text

    def test_empty_input(self):
        seg = SceneSegmenter()
        assert seg.segment([]) == []


class TestSubtitleSegmenter:
    def test_basic_split(self):
        seg = SubtitleSegmenter(
            {
                "min_chars_per_block": 5,
                "max_chars_per_block": 10,
            }
        )
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
        seg_p = SubtitleSegmenter(
            {"min_chars_per_block": 5, "max_chars_per_block": 10, "time_calculation_method": "proportional"}
        )
        seg_e = SubtitleSegmenter(
            {"min_chars_per_block": 5, "max_chars_per_block": 10, "time_calculation_method": "equal"}
        )
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
        """字幕块末尾句内标点应被去除\uff08句号切分后的块除外\uff09。"""
        seg = self._make_seg()
        scene = make_scene("今天天气真好。我们去公园散步吧。")
        subs = seg.segment(scene)
        for sub in subs:
            # v0.12.0: 句号切分后的块可以。结尾\uff08句子终止符\uff09
            # 但句内标点\uff08，、；\uff09不应出现在末尾
            assert sub.text[-1] not in "，、；,.?;", f"字幕块末尾不应是句内标点: {sub.text!r}"

    def test_leading_punctuation_fixed(self):
        """字幕块不应以句内标点开头。"""
        seg = self._make_seg()
        # 构造一个较长文本，迫使字幕切分后下一块以标点开头
        scene = make_scene("西班牙士兵邦板牙土著战士以及五百名佩着野太刀的日本浪人悄无声息地完成了合围。")
        subs = seg.segment(scene)
        for sub in subs:
            assert sub.text[0] not in "，、。！？；", f"字幕块不应以标点开头: {sub.text!r}"

    def test_cross_block_quotes_removed(self):
        """跨块双引号应被去除。"""
        seg = self._make_seg()
        # 构造包含引号的场景，迫使引号跨块
        scene = make_scene("站在高处安抚惶惑的同胞：“把铁器卖了吧换笔钱图个平安。”")
        subs = seg.segment(scene)
        # 检查不应有孤立引号跨块的情况
        for i in range(len(subs) - 1):
            curr_end = subs[i].text[-1] if subs[i].text else ""
            next_start = subs[i + 1].text[0] if subs[i + 1].text else ""
            # 不应出现 左引号在块尾 + 右引号在下一块开头
            assert not (curr_end in '\u201c\u300c"' and next_start in '\u201d\u300d"'), (
                f"跨块引号未清理: block[{i}]={subs[i].text!r}, block[{i + 1}]={subs[i + 1].text!r}"
            )

    def test_merge_short_with_quotes(self):
        """纯引号尾块并入遵循 v1.2 长度守卫（场景 10 问题回归）。"""
        seg = self._make_seg()
        # 并入后 ≤ max：正常并入
        blocks = ["短文本", '"']
        merged = seg._merge_short(blocks)
        assert len(merged) == 1
        assert '"' in merged[0]
        # 并入后 > max：保持独立（交由 Step 5 引号清理，流水线不产出孤立纯引号块）
        blocks2 = ["他们开始行动。一开始装得彬彬有礼", '"']
        merged2 = seg._merge_short(blocks2)
        assert len(merged2) == 2
        assert merged2[1] == '"'


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


class TestQuoteAwareSplitting:
    """v0.11.0 R1: 引号感知字幕预分割。"""

    def _get_blocks(self, text: str) -> list:
        seg = SubtitleSegmenter()
        scene = make_scene(text)
        subs = seg.segment(scene)
        return [s.text for s in subs]

    def test_quote_narrative_boundary(self):
        """引号内容与叙述文字应分属不同块（规范 v1.0 Step 2：引号内容 >= min_chars 才分离）。"""
        # 短引号内容（"不对，"4 字 < min_chars=8）并入上下文，不强制分离
        blocks = self._get_blocks("“不对，”宴会散后，阿库尼亚对副官低语")
        assert blocks, "应有字幕块"
        assert "不对" in blocks[0]  # 短引号内容在第一块
        # 长引号内容（>= min_chars）应与叙述分离
        blocks2 = self._get_blocks("他说：“最近常来这里，清晨的空气最清新。”我点点头，继续往前走。")
        assert any("最近常来" in b for b in blocks2)
        assert any("我点点头" in b for b in blocks2)
        assert not any("最近常来" in b and "我点点头" in b for b in blocks2)

    def test_quote_exclamation_separate(self):
        """引号+叹号后跟叙述，应分开。"""
        blocks = self._get_blocks("\u201c\u5f02\u6559\u5f92\u201d\uff01\u4ed6\u4eec\u72de\u7b11\u7740\u3002")
        # “异教徒” 应在第一块
        assert "\u5f02\u6559\u5f92" in blocks[0]
        # 叙述应在单独的块
        assert any("\u4ed6\u4eec\u72de\u7b11\u7740" in b for b in blocks[1:])

    def test_colon_before_quote(self):
        """冒号+长引号内容：叙述与引号内容分开（跨块引号清理）。"""
        blocks = self._get_blocks("作陪的菲律宾酋长直接质问：“天朝凭什么来我们这儿勘测山川”？")
        # 应有两块以上
        assert len(blocks) >= 2
        # 冒号前的叙述保留
        assert any("质问" in b for b in blocks)
        # 引号内容保留（无孤立引号字符）
        assert any("勘测山川" in b for b in blocks)
        assert not any("“" in b or "”" in b for b in blocks)  # 跨块引号已清理

    def test_no_quotes_no_split(self):
        """无引号文本不受影响。"""
        blocks = self._get_blocks("西班牙总督设宴款待，酒过三巡")
        assert len(blocks) >= 1
        assert all(len(b) <= 15 for b in blocks)


class TestEnforceMaxLength:
    """v0.11.0 R2: 超长块强制再分割。"""

    def test_long_block_forced_split(self):
        """超过 max_chars 的块应被强制分割。"""
        seg = SubtitleSegmenter()
        # 直接测试 _enforce_max（规范 Step 6）
        blocks = ["这是一段很长的文本超过了十五个字符的限制"]
        result = seg._enforce_max(blocks)
        assert all(len(b) <= 15 for b in result)

    def test_enforce_max_balance_fallback_no_good_cut(self):
        """v1.2 回归：Step 6 平衡回退——切分窗口内无标点/无词边界好切点（尾字全为强黏着后缀）时，
        回退 balanced=min_pos 切分（10+8），不得因漏算 balanced 抛 NameError。
        """
        seg = SubtitleSegmenter()
        blocks = ["软件硬件网络设备端口接口模块组件服务"]
        result = seg._enforce_max(blocks)
        assert result == ["软件硬件网络设备端口", "接口模块组件服务"]

    def test_short_block_unchanged(self):
        """不超过 max_chars 的块不受影响。"""
        seg = SubtitleSegmenter()
        blocks = ["短文本", "另一个短文本"]
        result = seg._enforce_max(blocks)
        assert result == blocks

    def test_long_sentence_split(self):
        """26字长句应被分割。"""
        seg = SubtitleSegmenter()
        scene = make_scene("在马尼拉南郊的圣佩德罗·马卡蒂与西班牙正规军血战数日")
        subs = seg.segment(scene)
        assert all(len(s.text) <= 15 for s in subs)
        assert len(subs) >= 2


class TestSeparatorSceneFilter:
    """v0.11.0 R3: 分隔线场景过滤。"""

    def test_separator_not_scene(self):
        """纯分隔线段落不应生成场景。"""
        from splitter import SmartSentenceSplitter

        text = "海面空旷得令人心慌。\n---\n1639年冬，起义像野火般蔓延。"
        splitter = SmartSentenceSplitter({"enable_paragraph_aware": True})
        result = splitter.split(text)
        for scene in result.scenes:
            assert scene.text.strip() != "---"
            assert "---" not in scene.text

    def test_various_separators_filtered(self):
        """各种分隔线格式都应被过滤。"""
        from splitter import SmartSentenceSplitter

        text = "第一段。\n***\n第二段。\n===\n第三段。"
        splitter = SmartSentenceSplitter({"enable_paragraph_aware": True})
        result = splitter.split(text)
        all_text = "".join(s.text for s in result.scenes)
        assert "***" not in all_text
        assert "===" not in all_text


class TestEnumerationProtection:
    """v1.1 顿号枚举单元整体保护：max 切分锚点落在顿号上时，切分点移到枚举单元结束之后。"""

    def _blocks(self, text, min_chars=8, max_chars=15):
        seg = SubtitleSegmenter({"min_chars_per_block": min_chars, "max_chars_per_block": max_chars})
        return [s.text for s in seg.segment(make_scene(text))]

    def test_enumeration_kept_whole(self):
        # 用户实例：切分点原落在"柴火、"的顿号上，应移到谓词引导词"那"之前，枚举整体保留
        assert self._blocks("要知道在农耕社会，柴火、盐巴和香料那可都是绝对的硬通货。") == [
            "要知道在农耕社会",
            "柴火、盐巴和香料",
            "那可都是绝对的硬通货",
        ]

    def test_enumeration_with_connector(self):
        # 和/及/与 连接的末项属于枚举单元
        assert self._blocks("桌上摆着苹果、香蕉和梨子，它们都来自果园。") == [
            "桌上摆着苹果、香蕉和梨子",
            "它们都来自果园",
        ]

    def test_enumeration_not_split_by_step3_punct_cut(self):
        # 顿号不再作为 Step 3 常规切分锚点（优先级最低），逗号/句号仍是
        assert self._blocks("苹果、香蕉、橘子、葡萄和西瓜都是常见的水果，它们各有营养。") == [
            "苹果、香蕉、橘子",
            "葡萄和西瓜都是常见的水果",
            "它们各有营养",
        ]

    def test_enumeration_long_splits_at_punct(self):
        # 长枚举按顿号/枚举整体逐步切分：不产生超长块；切点处的顿号按 Step 5 清理
        text = "清单里有苹果、香蕉、橘子、葡萄、西瓜和哈密瓜这些都是常见的水果。"
        blocks = self._blocks(text)
        assert all(len(b) <= 15 for b in blocks)
        assert blocks[0] == "清单里有苹果、香蕉"
        assert blocks[-1] == "这些都是常见的水果"

    def test_enumeration_predicate_swallow_guard(self):
        # v1.2.1 吞并守卫：枚举项+谓语被 max 截断时，枚举保护不得吞并谓语整段
        # （否则 15+3 劈词孤尾：`呐喊声混成一锅滚` + `烫的粥`）
        assert self._blocks("枪声、爆炸声、呐喊声混成一锅滚烫的粥。") == [
            "枪声、爆炸声、呐喊声",
            "混成一锅滚烫的粥",
        ]

    def test_enumeration_predicate_unknown_verb_still_no_swallow(self):
        # 未知谓语动词（不在 predicate_starters，如"此起彼伏"）也受守卫保护：
        # 回退顿号锚点而非吞并到块尾；短头块并入超限时保持分开（v1.2 长度守卫），
        # 禁止出现 15+3 劈词孤尾
        blocks = self._blocks("风声、雨声、读书声此起彼伏地回荡在廊檐下。")
        assert blocks == ["风声、雨声", "读书声此起彼伏地回荡在廊檐下"]


class TestRoundingHalfUp:
    """时间戳四舍五入（half-up）与 TypeScript Math.round(x*100)/100 语义一致（v0.15.1）。

    Python round() 为银行家舍入（0.625→0.62），JS 为四舍五入（0.625→0.63）——
    差分测试证实两实现会在 .xx5 边界产生 0.01s 级分歧（等分场景累计 0.15s），本测试锁定统一为 half-up。
    """

    def test_proportional_xx5_rounding(self):
        # 1/16*10=0.625 → 0.63；15/16*10=9.375 → 9.38（half-up）
        seg = SubtitleSegmenter({})
        subs = seg.segment(make_scene("嗯。一二三四五六七八九十甲乙丙丁戊", duration=10.0))
        assert [s.duration for s in subs] == [0.63, 9.38]
        assert [s.start_time for s in subs] == [0.0, 0.63]

    def test_equal_xx5_rounding(self):
        # 16 块等分：10/16=0.625 → 每块 0.63，末块 start 累计到 9.45（与 TS 一致）
        seg = SubtitleSegmenter({"min_chars_per_block": 1, "max_chars_per_block": 1, "time_calculation_method": "equal"})
        text = "一二三四五六七八九十甲乙丙丁戊己。"
        subs = seg.segment(make_scene(text, duration=10.0))
        assert [s.duration for s in subs] == [0.63] * 16
        assert subs[-1].start_time == 9.45

class TestSubtitleV123WordAwareRegression:
    """v1.2.2/v1.2.3 回归：成词保护（no_cut_bigrams）、小数点豁免、good_tail_blockers、孤悬尾防护。

    覆盖用户实测投诉与验收样例：扶余国/电视剧/复杂/辽西/城邦/脖子/挥刀自宫 4 块期望、
    713.3 小数不劈、"能够/就是/做成/高高在上" 等成词不劈。
    """

    def _blocks(self, text: str) -> list:
        return SubtitleSegmenter({})._split_to_blocks(text)

    def test_no_cut_bigrams_word_intact(self):
        # 能|够、就|是、做|成、在|上 均不得被切开
        assert any("能够" in b for b in self._blocks("这套AI基建能够实时监控全域低空空域，为每一架无人机动态规划专属航线，自动避开高楼、人群、禁飞区。"))
        assert any("就是" in b for b in self._blocks("很多人以为低空经济就是造架无人机飞一飞，太天真了。"))
        assert any("做成" in b for b in self._blocks("于是深圳干了一件全世界都没干成的事：把AI空域调度做成城市标配基建。"))
        assert any("高高在上" in b for b in self._blocks("他们觉得自己是高高在上的现代国家，把文化和国家认同搅在一起，是落后操作。"))

    def test_user_complaint_words_intact(self):
        # 用户投诉：扶余国 / 电视剧 / 复杂 / 辽西以东 不再被硬切
        assert any("扶余国" in b for b in self._blocks("因此，在韩国的历史教科书里，能看到大量关于扶余国和扶余人的记载。"))
        assert any("电视剧" in b for b in self._blocks("2005年，韩国收视率最高的电视剧《朱蒙》播出，里面讲述的正是这位扶余王子的故事。"))
        assert any("复杂简单化" in b for b in self._blocks("历史上的族群迁徙与政权更迭本就复杂，而民族叙事则倾向于把一切复杂简单化、直线化。"))
        assert any("辽西以东的虚实" in b for b in self._blocks("西周人对东北的了解本就模糊，连分封在河北的燕国早期历史都空白一片，更不要说辽西以东的虚实。"))

    def test_mongol_tax_collectors_semantic_boundaries(self):
        assert self._blocks(
            "那时候蒙古统治者水平有限，对汉地的管理极其粗放，江南士绅摇身一变成了蒙元的包税人。大汗把权力一下放，收税成本蹭蹭往下降。"
        ) == [
            "那时候蒙古统治者水平有限",
            "对汉地的管理极其粗放",
            "江南士绅摇身一变",
            "成了蒙元的包税人",
            "大汗把权力一下放",
            "收税成本蹭蹭往下降",
        ]

    def test_common_words_and_unpaired_quote_body_intact(self):
        text = (
            "这种士大夫做大的局面，哪怕朱元璋建立大明也没能彻底翻转。"
            "暂时没法彻底打破士绅垄断。"
            '只是这里的"宽"被那些狼心狗肺的人硬说成是"宽仁"。'
            "那些人用实际行动展现出结果。"
            '居然还写诗怀念前朝。"字里行间全在抱怨元末的群雄挡了他给蒙元当奴才的路。'
        )
        blocks = self._blocks(text)
        joined = "".join(blocks)
        expected = text.translate(str.maketrans("", "", "。！？；.!?;…")).replace('前朝"字', "前朝字")
        assert joined == expected
        assert any("哪怕" in b for b in blocks)
        assert any("没法" in b for b in blocks)
        assert any("那些" in b for b in blocks)
        assert any("展现" in b for b in blocks)
        assert any("字里行间全在抱怨" in b for b in blocks)
        assert any('"宽"' in b for b in blocks)

    def test_user_acceptance_4_blocks(self):
        # 用户明确期望：挥刀自宫句切成 4 块
        assert self._blocks("这套政策根本经不起扒，说白了就是逼着全体华人为了挤进西方圈子，挥刀自宫搞文化阉割。") == [
            "这套政策根本经不起扒",
            "说白了就是逼着全体华人",
            "为了挤进西方圈子",
            "挥刀自宫搞文化阉割",
        ]

    def test_wendi_sentence_3_blocks(self):
        assert self._blocks("要理解文帝进京这件事，得先搞清楚一个前提：功臣集团为什么选他？") == [
            "要理解文帝进京这件事",
            "得先搞清楚一个前提：",
            "功臣集团为什么选他",
        ]

    def test_decimal_dot_not_split(self):
        # 713.3 的小数点不是句界/切分锚点
        blocks = self._blocks("今年夏天，台风肆虐导致广西暴雨如注，降雨量狂飙到一天713.3毫米。")
        assert any(b == "713.3毫米" for b in blocks)
        assert all("713" not in b or "713.3" in b for b in blocks)

    def test_good_tail_blocker_personality(self):
        # good_tail 入 "个" 后，"个性" 不得被切（good_tail_blockers 兜底）
        blocks = self._blocks("他们越来越强调个性独立，不愿再被贴上标签。")
        assert any("个性" in b for b in blocks)

    def test_enumeration_and_neck(self):
        blocks = self._blocks("枪声、爆炸声、呐喊声混成一锅滚烫的粥。")
        assert blocks[0] == "枪声、爆炸声、呐喊声"
        assert any("被掐着脖子" in b for b in self._blocks("说到底，新加坡华人也不想被掐着脖子不让说方言，也不想硬演一家亲，也怀疑政府在偷偷引进印度人。"))
