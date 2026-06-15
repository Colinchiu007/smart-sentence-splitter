"""PromptEngineExporter — PROJECT-012 → PROJECT-011 (prompt-engine) 桥接。

将 PROJECT-012 的 SentenceBlock / SplitResult 转换为
PROJECT-011 (prompt-engine) 的 OptimizeRequest 格式。

v0.9.1 新增: 上下文 (context) 注入，支持角色/场景一致性。

用法:
    from splitter.exporter.prompt_engine import PromptEngineExporter
    exporter = PromptEngineExporter()
    req = exporter.to_optimize_request(sentence_block, context={...})
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from ..models import SentenceBlock, SplitResult


class PromptEngineExporter:
    """PROJECT-012 → PROJECT-011 数据桥接器。"""

    def __init__(
        self,
        default_platform: str = None,
        default_creative_level: int = 5,
        default_max_length: int = 500,
        era_to_style: Optional[Dict[str, str]] = None,
    ):
        self.default_platform = default_platform
        self.default_creative_level = default_creative_level
        self.default_max_length = default_max_length
        self.era_to_style = era_to_style or {
            "ancient": "classical",
            "modern": "contemporary",
            "mixed": "eclectic",
        }

    def _get_era_style(self, era: Optional[str] = None) -> Optional[str]:
        if era and era in self.era_to_style:
            return self.era_to_style[era]
        return None

    # ===== 核心转换 =====

    def to_optimize_request(
        self,
        sentence: SentenceBlock,
        era: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """单个 SentenceBlock → PROJECT-011 OptimizeRequest dict。

        Args:
            sentence: PROJECT-012 分句结果
            era: 时代标签 (ancient / modern / mixed), 可选
            context: 上下文 (v0.9.1), 用于角色/场景一致性
                {
                    "synopsis": "故事梗概",
                    "character": {"name": "小明"},
                    "setting": "超市",
                    "character_list": [{"name": "小明"}, {"name": "小红"}],
                }
        """
        platform = self._infer_platform(sentence.language)
        max_length = self._compute_max_length(sentence)
        creative_level = self._compute_creative_level(sentence)
        style_hint = self._get_era_style(era)

        req: Dict[str, Any] = {
            "prompt": sentence.text,
            "platform": platform,
            "creative_level": creative_level,
            "max_length": max_length,
            "num_candidates": 1,
            "auto_detect_style": True,
        }
        if style_hint:
            req["style_hint"] = style_hint
        if context:
            req["context"] = context
        return req

    def to_batch_request(
        self,
        sentences: List[SentenceBlock],
        eras: Optional[List[str]] = None,
        contexts: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """批量 SentenceBlock → batch 请求 body。"""
        results = []
        for i, s in enumerate(sentences):
            era = eras[i] if eras and i < len(eras) else None
            ctx = contexts[i] if contexts and i < len(contexts) else None
            results.append(self.to_optimize_request(s, era=era, context=ctx))
        return results

    def from_split_result(self, result: SplitResult) -> List[Dict[str, Any]]:
        """SplitResult → 批量请求 body（含上下文）。

        遍历 scenes → sentences，从 scene 和 script_analysis 中提取上下文。
        """
        sa = result.script_analysis or {}
        synopsis = sa.get("synopsis", "")
        all_characters = sa.get("characters", [])

        # 全局角色列表
        character_list = [{"name": c} for c in all_characters]

        contexts: List[Optional[Dict[str, Any]]] = []
        eras: List[Optional[str]] = []

        for scene in result.scenes:
            for s in scene.sentences:
                era = scene.era_info.era if scene.era_info else None
                eras.append(era)

                # 构建本句上下文
                ctx: Dict[str, Any] = {}
                if synopsis:
                    ctx["synopsis"] = synopsis
                if all_characters:
                    ctx["character_list"] = character_list
                if scene.characters:
                    ctx["character"] = {"name": scene.characters[0]}
                if scene.setting:
                    ctx["setting"] = scene.setting
                contexts.append(ctx if ctx else None)

        return self.to_batch_request(result.sentences, eras=eras, contexts=contexts)

    # ===== 转换规则 =====

    def _infer_platform(self, language: str) -> str:
        mapping = {
            "zh": "midjourney",
            "en": "stable_diffusion",
            "ja": "jimeng",
            "auto": "generic",
            "mixed": "midjourney",
        }
        return mapping.get(language, self.default_platform or "generic")

    def _compute_max_length(self, sentence: SentenceBlock) -> int:
        base = self.default_max_length
        if sentence.length_status == "too_long":
            return min(base, 200)
        if sentence.length_status == "too_short":
            return max(base, 700)
        return base

    def _compute_creative_level(self, sentence: SentenceBlock) -> int:
        base = self.default_creative_level
        if sentence.length_status == "too_short":
            return min(base + 3, 10)
        if sentence.length_status == "too_long":
            return max(base - 2, 1)
        return base