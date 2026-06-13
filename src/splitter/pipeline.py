"""SmartSentenceSplitter - main entry point.

Facade that ties together:
- Multi-language routing (LanguageRouter)
- Three-tier degradation (TierChain)
- Scene segmentation (SceneSegmenter)
- Subtitle segmentation (SubtitleSegmenter)
- Era detection (EraDetector, optional)

Usage:
    from splitter import SmartSentenceSplitter
    splitter = SmartSentenceSplitter()
    result = splitter.split("long text...")
"""

from __future__ import annotations
from typing import Dict, Any, Optional

from .core.tier_chain import TierChain
from .core.language_router import LanguageRouter
from .scene_subtitle.scene_segmenter import SceneSegmenter
from .scene_subtitle.subtitle_segmenter import SubtitleSegmenter
from .models import SplitResult
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

        # 构建 tier 链：tier2 + tier3（tier1 暂不实现）
        from .languages.zh.splitter import ChineseSplitter
        from .languages.en.splitter import EnglishSplitter
        zh_splitter = ChineseSplitter(self.config.get("sentence_tokenizer", {}).get("language_specific", {}).get("zh", {}))
        en_splitter = EnglishSplitter(self.config.get("sentence_tokenizer", {}).get("language_specific", {}).get("en", {}))

        self.splitters = {
            "zh": zh_splitter,
            "en": en_splitter,
        }
        self.chain = TierChain(
            splitters=[zh_splitter, en_splitter],
            min_tier=self.config.get("min_tier", 2),
        )

        self.scene_segmenter = SceneSegmenter(self.config.get("scene", {}))
        self.subtitle_segmenter = SubtitleSegmenter(self.config.get("subtitle", {}))

        # 时代检测（可选）
        self.era_detector = None
        if self.config.get("enable_era", False):
            from .era.detector import EraDetector
            self.era_detector = EraDetector()

    def split(self, text: str) -> SplitResult:
        """处理文本，返回 SplitResult。"""
        if not text or not text.strip():
            return SplitResult(config_snapshot=self.config)

        # 1. 多语言路由
        detected_lang, splitter = self.router.route(text)

        # 2. 分句（用对应语言的分句器）
        # 单独构造对应语言的 chain
        from .core.tier_chain import TierChain
        local_chain = TierChain(
            splitters=[splitter, splitter],  # 单个分句器
            min_tier=self.config.get("min_tier", 2),
        )
        sentences, tier_used = local_chain.split(text)

        # 修正每句的 language 标签
        for s in sentences:
            s.language = detected_lang

        # 3. 场景级分割
        scenes = self.scene_segmenter.segment(sentences)

        # 4. 字幕级分割
        for scene in scenes:
            subtitles = self.subtitle_segmenter.segment(scene)
            scene.subtitles = subtitles

        # 5. 时代检测（可选，仅中文）
        if self.era_detector and detected_lang == "zh":
            for scene in scenes:
                scene.era_info = self.era_detector.detect(scene.text)

        # 6. 返回结果
        return SplitResult(
            sentences=sentences,
            scenes=scenes,
            tier_used=tier_used,
            language=detected_lang,
            config_snapshot=self.config,
        )
