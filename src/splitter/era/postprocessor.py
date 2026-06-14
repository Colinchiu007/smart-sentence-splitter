"""EraPostprocessor — 把 EraDetector 包装为 postprocessor。

借鉴 HanLP MTL 思想：分句 + 时代检测联合输出，但作为独立 module。
"""

from __future__ import annotations
from typing import Callable, Optional

from ..postprocessor import BasePostprocessor
from ..models import SplitResult


class EraPostprocessor(BasePostprocessor):
    """时代检测后处理器。

    对每个 scene 跑 EraDetector（仅中文），写入 scene.era_info。
    Detector 延迟加载（factory callable）。
    """

    name = "era_detector"

    def __init__(
        self,
        detector_factory: Callable,
        only_for_language: str = "zh",
    ):
        """Args:
            detector_factory: callable 返回 EraDetector 实例（lazy）
            only_for_language: 仅对该语言文本做时代检测
        """
        self._factory = detector_factory
        self._detector = None
        self.only_for_language = only_for_language

    def _get_detector(self):
        if self._detector is None:
            self._detector = self._factory()
        return self._detector

    def is_available(self) -> bool:
        try:
            return self._get_detector() is not None
        except Exception:
            return False

    def adjust(self, result: SplitResult) -> SplitResult:
        if result.language != self.only_for_language:
            return result
        if not result.scenes:
            return result

        try:
            detector = self._get_detector()
            for scene in result.scenes:
                if scene.era_info is None:
                    scene.era_info = detector.detect(scene.text)
        except Exception as e:
            import logging
            logging.warning(f"EraPostprocessor failed: {e}")
        return result
