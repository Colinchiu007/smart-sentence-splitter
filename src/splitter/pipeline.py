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
            zh_splitters.append(TextTilingSemanticSplitter(
                self.config.get("texttiling", {})
            ))
        zh_splitters.append(ChineseSplitter(
            self.config.get("sentence_tokenizer", {}).get("language_specific", {}).get("zh", {})
        ))
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
            en_splitters.append(TextTilingSemanticSplitter(
                self.config.get("texttiling", {})
            ))
        en_splitters.append(EnglishSplitter(
            self.config.get("sentence_tokenizer", {}).get("language_specific", {}).get("en", {})
        ))
        en_splitters.append(EnglishRuleSplitter())
        self._en_chain = TierChain(
            splitters=en_splitters,
            min_tier_provider=lambda: self._get_effective_min_tier(),
        )

        # 日文 splitter 链 (v0.9.9)
        ja_splitters: List[BaseSentenceSplitter] = [JapaneseSplitter(
            self.config.get("sentence_tokenizer", {}).get("language_specific", {}).get("ja", {})
        )]
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
            self.postprocessor_chain.add(
                CustomMergingProcessor({"user_dict_path": user_dict_path})
            )

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

    def _analyze_script(
        self, text: str, scenes: List
    ) -> Optional[Dict[str, Any]]:
        """对全文做剧本分析，注入角色/场景到每个 SceneSegment。"""
        from .script.script_analyzer import ScriptAnalyzer
        analyzer = ScriptAnalyzer()
        return analyzer.analyze(text)

    def _enrich_scenes(
        self, scenes: List, script_analysis: Dict[str, Any]
    ) -> None:
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
            "愤怒": "angry", "生气": "angry", "怒": "angry",
            "悲伤": "sad", "哭了": "sad", "哭": "sad",
            "开心": "happy", "笑": "happy", "高兴": "happy",
            "紧张": "tense", "担心": "tense", "急": "tense",
            "平静": "calm", "安静": "calm",
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
        """借鉴 THULAC __cutRaw：大文本兜底。"""
        max_length = self.config.get("max_input_length", 50000)
        if len(text) <= max_length:
            return None

        import re as _re
        blocks = _re.findall(r'.*?[。！？；;!?]', text)
        chunked = []
        current = ""
        for block in blocks:
            if len(current) + len(block) > max_length:
                chunked.append(current.strip())
                current = block
            else:
                current += block
        if current.strip():
            chunked.append(current.strip())

        all_sentences = []
        last_tier = ""
        for chunk in chunked:
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
