"""SmartSentenceSplitter - main entry point.

Facade that ties together:
- Multi-language routing (LanguageRouter)
- Three-tier degradation (TierChain)
  - Tier 2A: TextTilingSemanticSplitter (if enabled)
  - Tier 2B: ChineseSplitter / EnglishSplitter (jieba + rule)
  - Tier 3: ChineseRuleSplitter / EnglishRuleSplitter (rule-only fallback)
- Scene segmentation (SceneSegmenter)
- Subtitle segmentation (SubtitleSegmenter)
- Era detection (EraPostprocessor, lazy-loaded)
- Postprocessor chain (THULAC-inspired, v0.3)

Usage:
    from splitter import SmartSentenceSplitter
    splitter = SmartSentenceSplitter()
    result = splitter.split("long text...")
"""

from __future__ import annotations
from typing import Dict, Any, Optional, List

from .core.tier_chain import TierChain
from .core.base_splitter import BaseSentenceSplitter
from .core.language_router import LanguageRouter
from .scene_subtitle.scene_segmenter import SceneSegmenter
from .scene_subtitle.subtitle_segmenter import SubtitleSegmenter
from .models import SplitResult
from .postprocessor import (
    BasePostprocessor,
    PostprocessorChain,
)
from .utils.config_loader import load_config


class SmartSentenceSplitter:
    """语义分句引擎主入口。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = load_config(config)
        self.router = LanguageRouter(self.config.get("sentence_tokenizer", {}))
        self.enable_topic_seg = self.config.get("enable_topic_segmentation", False)

        # === 对每种语言构建独立的 tier 链 ===
        from .languages.zh.splitter import ChineseSplitter
        from .languages.en.splitter import EnglishSplitter
        from .languages.ja.splitter import JapaneseSplitter
        from .tiers.tier3_rule import ChineseRuleSplitter, EnglishRuleSplitter
        from .texttiling.splitter import TextTilingSemanticSplitter

        # v0.4: LLM Tier (Tier 1) — 真实可用时加入链头
        from .tiers.tier1_llm import LLMSplitter

        self.llm_enabled = self.config.get("enable_llm", False)
        self._llm_splitter_instance = None

        # 中文 splitter 链
        zh_splitters: List[BaseSentenceSplitter] = []
        if self.llm_enabled:
            try:
                llm = self._get_llm_splitter()
                if llm.is_available():
                    zh_splitters.append(llm)
            except Exception:
                pass  # LLM 不可用就跳过
        if self.enable_topic_seg:
            zh_splitters.append(TextTilingSemanticSplitter(self.config.get("texttiling", {})))
        zh_splitters.append(
            ChineseSplitter(self.config.get("sentence_tokenizer", {}).get("language_specific", {}).get("zh", {}))
        )
        zh_splitters.append(ChineseRuleSplitter())
        # 关键：TierChain min_tier 来自一个可调用的 lambda，每次 split 都重新读
        self._zh_chain = TierChain(
            splitters=zh_splitters,
            min_tier_provider=lambda: self._get_effective_min_tier(),
        )

        # 英文 splitter 链
        en_splitters: List[BaseSentenceSplitter] = []
        if self.llm_enabled:
            try:
                llm = self._get_llm_splitter()
                if llm.is_available():
                    en_splitters.append(llm)
            except Exception:
                pass
        if self.enable_topic_seg:
            en_splitters.append(TextTilingSemanticSplitter(self.config.get("texttiling", {})))
        en_splitters.append(
            EnglishSplitter(self.config.get("sentence_tokenizer", {}).get("language_specific", {}).get("en", {}))
        )
        en_splitters.append(EnglishRuleSplitter())
        self._en_chain = TierChain(
            splitters=en_splitters,
            min_tier_provider=lambda: self._get_effective_min_tier(),
        )

        # 日文 splitter 链 (v0.9.9)
        ja_splitters: List[BaseSentenceSplitter] = [
            JapaneseSplitter(self.config.get("sentence_tokenizer", {}).get("language_specific", {}).get("ja", {}))
        ]
        self._ja_chain = TierChain(
            splitters=ja_splitters,
            min_tier_provider=lambda: self._get_effective_min_tier(),
        )

        # 场景 + 字幕
        self.scene_segmenter = SceneSegmenter(self.config.get("scene", {}))
        self.subtitle_segmenter = SubtitleSegmenter(self.config.get("subtitle", {}))

        # ====== v0.3 改动 ======

        # F3: Lazy EraDetector — 不在 __init__ 实例化
        self._era_detector_instance = None

        # F5/F6: Postprocessor chain（包含 EraPostprocessor）
        self.postprocessor_chain = PostprocessorChain()
        self._init_postprocessors()

    def _init_postprocessors(self):
        """F5: 初始化 postprocessor chain。"""
        # F6: EraPostprocessor（lazy 检测）
        if self.config.get("enable_era", False):
            from .era.postprocessor import EraPostprocessor

            self.postprocessor_chain.add(
                EraPostprocessor(
                    detector_factory=self._get_era_detector,
                    only_for_language="zh",
                )
            )

        # 未来的用户词典后处理器（如果配置）
        user_dict_path = self.config.get("user_dict_path")
        if user_dict_path:
            from .postprocessor import CustomMergingProcessor

            self.postprocessor_chain.add(CustomMergingProcessor({"user_dict_path": user_dict_path}))

    def _get_era_detector(self):
        """F3: Lazy 加载 EraDetector。"""
        if self._era_detector_instance is None:
            from .era.detector import EraDetector

            self._era_detector_instance = EraDetector()
        return self._era_detector_instance

    def _get_llm_splitter(self):
        """v0.4: Lazy 加载 LLM Tier。"""
        if self._llm_splitter_instance is None:
            from .tiers.tier1_llm import LLMSplitter

            self._llm_splitter_instance = LLMSplitter(self.config.get("llm", {}))
        return self._llm_splitter_instance

    # ===== v0.7: 剧本分析 =====

    def _analyze_script(self, text: str, scenes: List) -> Optional[Dict[str, Any]]:
        """对全文做剧本分析，注入角色/场景到每个 SceneSegment。"""
        from .script.script_analyzer import ScriptAnalyzer

        analyzer = ScriptAnalyzer()
        return analyzer.analyze(text)

    def _enrich_scenes(self, scenes: List, script_analysis: Dict[str, Any]) -> None:
        """把角色/场景列表注入到每个 SceneSegment 中。

        对每个场景，检查文本中是否包含角色名或场景名，
        匹配的则填到对应字段。
        """
        characters = script_analysis.get("characters", [])
        settings = script_analysis.get("settings", [])

        for scene in scenes:
            text = scene.text
            # 角色匹配
            scene_chars = [c for c in characters if c in text]
            if scene_chars:
                scene.characters = scene_chars
            # 场景匹配
            scene_setting = [s for s in settings if s in text]
            if scene_setting:
                scene.setting = scene_setting[0]
            # 简单情绪启发式
            scene.mood = self._infer_mood(text)

    def _infer_mood(self, text: str) -> str:
        """简单情绪启发式。"""
        mood_map = {
            "愤怒": "angry",
            "生气": "angry",
            "怒": "angry",
            "悲伤": "sad",
            "哭了": "sad",
            "哭": "sad",
            "开心": "happy",
            "笑": "happy",
            "高兴": "happy",
            "紧张": "tense",
            "担心": "tense",
            "急": "tense",
            "平静": "calm",
            "安静": "calm",
        }
        for kw, mood in mood_map.items():
            if kw in text:
                return mood
        return ""

    @property
    def era_detector(self):
        """向后兼容：暴露 era_detector 属性（lazy）。"""
        if self.config.get("enable_era", False):
            return self._get_era_detector()
        return None

    def _paragraph_aware_segment(
        self, sentences: List, text: str
    ) -> List:
        """段落感知场景分组。

        按原文的 \\n 将句子映射到所属段落，每个段落独立调用
        scene_segmenter.segment()，最后合并并统一编号。

        段落边界 = 强制场景边界，不可跨段落合并。
        """
        if not sentences:
            return []

        # 1. 提取段落及其在原文中的起始位置
        paragraphs = []  # [(para_text, start_offset), ...]
        offset = 0
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped:
                idx = text.find(stripped, offset)
                if idx >= 0:
                    paragraphs.append((stripped, idx))
                    offset = idx + len(stripped)

        if not paragraphs:
            # 回退：无段落信息，走普通分段
            return self.scene_segmenter.segment(sentences)

        # 2. 将每个句子映射到所属段落
        para_groups: dict = {i: [] for i in range(len(paragraphs))}
        search_offset = 0
        for sent in sentences:
            sent_text = sent.text.strip()
            if not sent_text:
                continue
            # 在原文中查找该句子的位置
            pos = text.find(sent_text, search_offset)
            if pos < 0:
                # 查找失败（可能被引号保护等），尝试从当前位置向后找
                pos = text.find(sent_text)
            if pos < 0:
                # 实在找不到，归入上一个段落
                para_groups[len(paragraphs) - 1].append(sent)
                continue

            # 确定属于哪个段落：找 pos 落在哪个段落区间
            assigned = False
            for pi in range(len(paragraphs) - 1, -1, -1):
                if pos >= paragraphs[pi][1]:
                    para_groups[pi].append(sent)
                    assigned = True
                    break
            if not assigned:
                para_groups[0].append(sent)

            search_offset = pos + len(sent_text)

        # 3. 每个段落独立做场景分段
        all_scenes = []
        scene_id = 0
        for pi in range(len(paragraphs)):
            para_sents = para_groups[pi]
            if not para_sents:
                continue
            para_scenes = self.scene_segmenter.segment(para_sents)
            # 3.5 段落内合并短场景
            para_scenes = self._merge_short_scenes(
                para_scenes,
                merge_threshold=self.config.get("scene", {}).get("target_seconds", 12.0),
            )
            for scene in para_scenes:
                scene.segment_id = scene_id
                all_scenes.append(scene)
                scene_id += 1

        return all_scenes

    def _merge_short_scenes(self, scenes: List, merge_threshold: float = 12.0) -> List:
        """段落内合并连续短场景。

        贪心策略：从左到右遍历，将时长不足 merge_threshold 的场景
        与下一个场景合并，直到累计时长 >= merge_threshold 或没有下一个场景。

        合并时保留所有句子和字幕，文本/时长累加。
        """
        if not scenes or len(scenes) <= 1:
            return scenes

        merged = []
        buf = None  # 当前累积的场景

        for scene in scenes:
            if buf is None:
                buf = scene
                continue

            # 尝试合并：当前累积时长 < threshold 则继续吞
            if buf.estimated_duration < merge_threshold:
                buf = self._combine_scenes(buf, scene)
            else:
                merged.append(buf)
                buf = scene

        if buf is not None:
            merged.append(buf)

        return merged

    @staticmethod
    def _combine_scenes(a, b):
        """将两个 SceneSegment 合并为一个（就地修改 a）。"""
        a.text = a.text + b.text
        a.estimated_duration = a.estimated_duration + b.estimated_duration
        a.sentences.extend(b.sentences)
        a.subtitles.extend(b.subtitles)
        # 分镜元数据合并
        for c in b.characters:
            if c not in a.characters:
                a.characters.append(c)
        if b.setting and not a.setting:
            a.setting = b.setting
        if b.mood and not a.mood:
            a.mood = b.mood
        return a

    def _detect_lang(self, text: str) -> str:
        from .utils.language_detect import detect_language

        mode = self.config.get("language", "auto")
        if mode == "auto":
            return detect_language(text)
        return mode

    def _apply_mode(self):
        """F7: mode 映射 → min_tier。

        使用局部变量而非修改 self.config，避免副作用。

        fast:    min_tier=3（仅规则）
        balanced: min_tier=2（语义+规则）默认
        precise: min_tier=1 + 自动启用 TextTiling
        """
        mode = self.config.get("mode", "balanced")
        if mode == "fast":
            self._override_min_tier = 3
        elif mode == "precise":
            self._override_min_tier = 1
            # 强制启用 topic seg（setdefault 仅在 key 不存在时生效，这里直接覆写）
            self.config["enable_topic_segmentation"] = True

    def _get_effective_min_tier(self) -> int:
        """获取生效的 min_tier（优先 override）。"""
        return getattr(self, "_override_min_tier", None) or self.config.get("min_tier", 2)

    def _handle_large_text(self, text: str, detected_lang: str) -> Optional[SplitResult]:
        """大文本分块兜底。

        改进策略:
        1. 更全面的句子边界字符（含 \n 和英文句点）
        2. 无边界时的硬回退（按 max_length 切）
        3. 超大块子分块（避免递归溢出）
        """
        max_length = self.config.get("max_input_length", 200000)
        if len(text) <= max_length:
            return None

        import re as _re

        # 句子边界字符（含 \n、英文句点、省略号）
        sent_chars = r"。！？；!?.\n…"
        sent_re = _re.compile(rf".*?[{sent_chars}]")

        blocks = sent_re.findall(text)

        # 回退 1: 无边界 -> 硬切
        if not blocks:
            blocks = [text[i:i + max_length] for i in range(0, len(text), max_length)]
        else:
            # 回退 2: 补上尾部无标点残留
            merged = "".join(blocks)
            remaining = text[len(merged):]
            if remaining:
                blocks.append(remaining)

        chunked = []
        current = ""
        for block in blocks:
            if len(current) + len(block) > max_length:
                if current.strip():
                    chunked.append(current.strip())
                if len(block) > max_length:
                    # 超大块内部硬切
                    for i in range(0, len(block), max_length):
                        sub = block[i:i + max_length]
                        if sub.strip():
                            chunked.append(sub.strip())
                    current = ""
                else:
                    current = block
            else:
                current += block
        if current.strip():
            chunked.append(current.strip())

        # 安全阀：跳过与父文本相同或更大的块（防止递归溢出）

        all_sentences = []
        last_tier = ""
        for chunk in chunked:
            if len(chunk) >= len(text):
                # 安全阀：跳过大于等于父文本的块
                continue
            result = self.split(chunk)  # 递归
            all_sentences.extend(result.sentences)
            if result.tier_used:
                last_tier = result.tier_used
        if all_sentences:
            scenes = self.scene_segmenter.segment(all_sentences)
            for scene in scenes:
                subtitles = self.subtitle_segmenter.segment(scene)
                scene.subtitles = subtitles
            return SplitResult(
                sentences=all_sentences,
                scenes=scenes,
                tier_used=last_tier,
                language=detected_lang,
                config_snapshot=self.config,
            )
        # 终极回退：让 split() 处理（比递归死循环好）
        return None
    def split(self, text: str) -> SplitResult:
        if not text or not text.strip():
            return SplitResult(config_snapshot=self.config)

        # 1. 多语言检测
        detected_lang = self._detect_lang(text)

        # 2. 大文本兜底
        large_result = self._handle_large_text(text, detected_lang)
        if large_result is not None:
            return self.postprocessor_chain.run(large_result)

        # 3. F7: mode 映射
        self._apply_mode()

        # 4. 选对应的 tier 链
        if detected_lang == "en":
            chain = self._en_chain
            lang_tag = "en"
        elif detected_lang == "ja":
            chain = self._ja_chain
            lang_tag = "ja"
        else:
            chain = self._zh_chain
            lang_tag = detected_lang

        # 5. 分句
        sentences, tier_used = chain.split(text)

        # 6. 修正 language 标签
        for s in sentences:
            s.language = s.language if s.language != "zh" else lang_tag

        # 6.5 v0.6: 字数控制策略 (默认 B, 不切)
        from .scene_subtitle.length_segmenter import LengthSegmenter

        length_cfg = self.config.get("length", {})
        length_seg = LengthSegmenter(
            strategy=length_cfg.get("strategy", "B"),
            min_chars=length_cfg.get("min_chars", 3),
            max_chars=length_cfg.get("max_chars", 15),
            prefer_punctuation=length_cfg.get("prefer_punctuation", True),
            warning_on_violation=length_cfg.get("warning_on_violation", True),
        )
        sentences = length_seg.segment(sentences)

        # 7. 场景级分割
        if self.config.get("enable_paragraph_aware", False):
            scenes = self._paragraph_aware_segment(sentences, text)
        else:
            scenes = self.scene_segmenter.segment(sentences)

        # 7.5 v0.7: 剧本分析 + 角色/场景注入
        script_analysis = None
        if self.config.get("enable_script_analysis", False):
            script_analysis = self._analyze_script(text, scenes)
            # 把角色/场景注入到每个 SceneSegment
            if script_analysis and "characters" in script_analysis:
                self._enrich_scenes(scenes, script_analysis)

        # 8. 字幕级分割
        for scene in scenes:
            subtitles = self.subtitle_segmenter.segment(scene)
            scene.subtitles = subtitles

        result = SplitResult(
            sentences=sentences,
            scenes=scenes,
            tier_used=tier_used,
            language=detected_lang,
            config_snapshot=self.config,
            script_analysis=script_analysis,
        )

        # 9. F5: Postprocessor chain
        result = self.postprocessor_chain.run(result)

        return result
