"""SmartSentenceSplitter - main entry point.

Facade that ties together:
- Multi-language routing (LanguageRouter)
- Three-tier degradation (TierChain)
  - Tier 2A: TextTilingSemanticSplitter (if enabled)
  - Tier 2B: ChineseSplitter / EnglishSplitter (jieba + rule)
  - Tier 3: ChineseRuleSplitter / EnglishRuleSplitter (rule-only fallback)
- Scene segmentation (SceneSegmenter)
- Subtitle segmentation (SubtitleSegmenter)
- Era detection (EraDetector, optional)

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
from .models import SplitResult, SentenceBlock
from .utils.config_loader import load_config


class SmartSentenceSplitter:
    """语义分句引擎主入口。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: 配置字典，None 时使用默认配置
        """
        self.config = load_config(config)
        self.router = LanguageRouter(self.config.get("sentence_tokenizer", {}))
        self.enable_topic_seg = self.config.get("enable_topic_segmentation", False)

        # === 对每种语言构建独立的 tier 链 ===
        from .languages.zh.splitter import ChineseSplitter
        from .languages.en.splitter import EnglishSplitter
        from .tiers.tier3_rule import ChineseRuleSplitter, EnglishRuleSplitter
        from .texttiling.splitter import TextTilingSemanticSplitter

        # 中文 splitter 链
        zh_splitters: List[BaseSentenceSplitter] = []
        if self.enable_topic_seg:
            zh_splitters.append(TextTilingSemanticSplitter(
                self.config.get("texttiling", {})
            ))
        zh_splitters.append(ChineseSplitter(
            self.config.get("sentence_tokenizer", {}).get("language_specific", {}).get("zh", {})
        ))
        zh_splitters.append(ChineseRuleSplitter())
        self._zh_chain = TierChain(splitters=zh_splitters, min_tier=self.config.get("min_tier", 2))

        # 英文 splitter 链
        en_splitters: List[BaseSentenceSplitter] = []
        if self.enable_topic_seg:
            en_splitters.append(TextTilingSemanticSplitter(
                self.config.get("texttiling", {})
            ))
        en_splitters.append(EnglishSplitter(
            self.config.get("sentence_tokenizer", {}).get("language_specific", {}).get("en", {})
        ))
        en_splitters.append(EnglishRuleSplitter())
        self._en_chain = TierChain(splitters=en_splitters, min_tier=self.config.get("min_tier", 2))

        # 场景 + 字幕
        self.scene_segmenter = SceneSegmenter(self.config.get("scene", {}))
        self.subtitle_segmenter = SubtitleSegmenter(self.config.get("subtitle", {}))

        # 时代检测（可选）
        self.era_detector = None
        if self.config.get("enable_era", False):
            from .era.detector import EraDetector
            self.era_detector = EraDetector()

    def _detect_lang(self, text: str) -> str:
        """检测文本语言（使用 router 的 detect 逻辑）。"""
        from .utils.language_detect import detect_language
        mode = self.config.get("language", "auto")
        if mode == "auto":
            return detect_language(text)
        return mode

    def split(self, text: str) -> SplitResult:
        """处理文本，返回 SplitResult。"""
        if not text or not text.strip():
            return SplitResult(config_snapshot=self.config)

        # 1. 多语言检测
        detected_lang = self._detect_lang(text)

        # 2. 大文本兜底（借鉴 THULAC __cutRaw 思路）
        max_length = self.config.get("max_input_length", 50000)
        if len(text) > max_length:
            # 按句末标点切块，每块不超过 max_length
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
            # 对每块递归调用 split
            all_sentences = []
            last_tier = ""
            for chunk in chunked:
                result = self.split(chunk)  # 递归
                all_sentences.extend(result.sentences)
                if result.tier_used:
                    last_tier = result.tier_used
            if all_sentences:
                # 重建 scenes
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

        # 3. mode 映射（快速/平衡/精确）
        mode = self.config.get("mode", "balanced")
        if mode == "fast":
            self.config["min_tier"] = 3
        elif mode == "precise":
            self.config["min_tier"] = 1
        # "balanced" → 不变，默认 min_tier=2

        # 4. 选对应的 tier 链
        if detected_lang == "en":
            chain = self._en_chain
            lang_tag = "en"
        else:
            chain = self._zh_chain          # zh / mixed / ja 统一走中文链
            lang_tag = detected_lang

        # 3. 分句
        sentences, tier_used = chain.split(text)

        # 4. 修正 language 标签
        for s in sentences:
            s.language = s.language if s.language != "zh" else lang_tag

        # 5. 场景级分割
        scenes = self.scene_segmenter.segment(sentences)

        # 6. 字幕级分割
        for scene in scenes:
            subtitles = self.subtitle_segmenter.segment(scene)
            scene.subtitles = subtitles

        # 7. 时代检测（可选，仅中文）
        if self.era_detector and detected_lang == "zh":
            for scene in scenes:
                scene.era_info = self.era_detector.detect(scene.text)

        # 8. 返回结果
        return SplitResult(
            sentences=sentences,
            scenes=scenes,
            tier_used=tier_used,
            language=detected_lang,
            config_snapshot=self.config,
        )
