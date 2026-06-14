"""PromptEngineExporter — PROJECT-012 → PROJECT-011 (prompt-engine) 桥接。

将 PROJECT-012 的 SentenceBlock / SplitResult 转换为
PROJECT-011 (prompt-engine) 的 OptimizeRequest 格式。

用法:
    from splitter.exporter.prompt_engine import PromptEngineExporter
    exporter = PromptEngineExporter()

    # 单个句子 → /v1/optimize
    req = exporter.to_optimize_request(sentence_block)
    # requests.post("http://localhost:8000/v1/optimize", json=req)

    # 批量
    batch = exporter.from_split_result(split_result)
    # requests.post("http://localhost:8000/v1/optimize/batch", json=batch)
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from ..models import SentenceBlock, SplitResult


class PromptEngineExporter:
    """PROJECT-012 → PROJECT-011 数据桥接器。

    Args:
        default_platform: 默认目标平台
        default_creative_level: 默认创意程度
        default_max_length: 默认最大字数
        era_to_style: 时代→风格映射表
    """

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
        """从时代标签推断风格。"""
        if era and era in self.era_to_style:
            return self.era_to_style[era]
        return None

    # ===== 核心转换 =====

    def to_optimize_request(
        self, sentence: SentenceBlock, era: Optional[str] = None
    ) -> Dict[str, Any]:
        """单个 SentenceBlock → PROJECT-011 OptimizeRequest dict。

        Args:
            sentence: PROJECT-012 分句结果
            era: 时代标签 (ancient / modern / mixed), 可选
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
        return req

    def to_batch_request(
        self, sentences: List[SentenceBlock], eras: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """批量 SentenceBlock → batch 请求 body。

        Args:
            sentences: 句子列表
            eras: 可选时代标签列表，长度与 sentences 一致
        """
        results = []
        for i, s in enumerate(sentences):
            era = eras[i] if eras and i < len(eras) else None
            results.append(self.to_optimize_request(s, era=era))
        return results

    def from_split_result(self, result: SplitResult) -> List[Dict[str, Any]]:
        """SplitResult → 批量请求 body。

        尝试从 scenes 中提取 era_info（如有）。
        """
        # 如果 scenes 有 era_info，按 scene 映射到 sentence
        era_map: Dict[int, str] = {}
        if result.scenes:
            for scene in result.scenes:
                if scene.era_info and scene.era_info.era:
                    # 这个 scene 里的所有 sentence 共享 era
                    for s in scene.sentences:
                        era_map[s.index] = scene.era_info.era

        eras = [era_map.get(s.index) for s in result.sentences]
        return self.to_batch_request(result.sentences, eras=eras)

    # ===== 转换规则 =====

    def _infer_platform(self, language: str) -> str:
        """根据语言推断目标平台。

        zh → midjourney (PROJECT-011 平台名)
        en → stable_diffusion
        ja → jimeng (日文走即梦)
        auto → generic
        mixed → midjourney
        """
        mapping = {
            "zh": "midjourney",
            "en": "stable_diffusion",
            "ja": "jimeng",
            "auto": "generic",
            "mixed": "midjourney",
        }
        return mapping.get(language, self.default_platform or "generic")

    def _compute_max_length(self, sentence: SentenceBlock) -> int:
        """根据字数状态调整 max_length。"""
        base = self.default_max_length
        if sentence.length_status == "too_long":
            return min(base, 200)
        if sentence.length_status == "too_short":
            return max(base, 700)
        return base

    def _compute_creative_level(self, sentence: SentenceBlock) -> int:
        """根据字数状态调整 creative_level。"""
        base = self.default_creative_level
        if sentence.length_status == "too_short":
            return min(base + 3, 10)
        if sentence.length_status == "too_long":
            return max(base - 2, 1)
        return base