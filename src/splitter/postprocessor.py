"""后处理器统一抽象接口（借鉴 THULAC Postprocessor chain 模式）。

每个后处理器继承 BasePostprocessor，实现 adjust() 方法。
所有后处理器通过 Pipeline 统一调用。
"""

from __future__ import annotations
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from .models import SplitResult, SceneSegment, SentenceBlock


class BasePostprocessor(ABC):
    """后处理器抽象基类。

    对分句结果进行"后处理修正"，不修改输入输出格式。
    每个子类只做一件事，通过链式调用组合。
    """

    name: str = "base"

    @abstractmethod
    def adjust(self, result: SplitResult) -> SplitResult:
        """对分句结果做后处理修正。

        Args:
            result: 当前分句结果

        Returns:
            修正后的分句结果
        """
        raise NotImplementedError

    def is_available(self) -> bool:
        """后处理器是否可用（依赖是否安装等）。"""
        return True


class PostprocessorChain:
    """后处理器链——按顺序执行后处理器。"""

    def __init__(self, postprocessors: Optional[List[BasePostprocessor]] = None):
        self.postprocessors: List[BasePostprocessor] = postprocessors or []

    def add(self, processor: BasePostprocessor):
        """添加后处理器到链尾。"""
        self.postprocessors.append(processor)

    def run(self, result: SplitResult) -> SplitResult:
        """按顺序执行所有可用的后处理器。"""
        for processor in self.postprocessors:
            if not processor.is_available():
                continue
            try:
                result = processor.adjust(result)
            except Exception as e:
                # 后处理器不应影响主线
                import logging

                logging.warning(f"Postprocessor '{processor.name}' failed: {e}")
        return result


class CustomMergingProcessor(BasePostprocessor):
    """用户词典合并后处理器（复用 AC 自动机 + Customization）。"""

    name = "custom_merging"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        dict_path = config.get("user_dict_path")
        self.custom = None
        if dict_path:
            from .languages.zh.custom import Customization

            self.custom = Customization()
            self.custom.load_customization(dict_path)

    def adjust(self, result: SplitResult) -> SplitResult:
        if not self.custom or not result.sentences:
            return result
        original = [s.text for s in result.sentences]
        merged = self.custom.adjust(original)
        if len(merged) != len(original):
            # 有合并：重建 split result
            new_sentences = []
            for i, text in enumerate(merged):
                new_sentences.append(
                    SentenceBlock(
                        text=text,
                        index=i,
                        language=result.language,
                        tier=result.tier_used,
                    )
                )
            result.sentences = new_sentences
        return result

class SeparatorLineProcessor(BasePostprocessor):
    """过滤纯分隔线句子 (---, ***, ===, —— 等)。"""

    name = "separator_line"
    SEPARATOR_RE = re.compile(r'^[\s\-—\*\=\~\•]{2,}$')

    def adjust(self, result: SplitResult) -> SplitResult:
        if not result.sentences:
            return result
        result.sentences = [s for s in result.sentences if not self._is_separator(s.text)]
        return result

    @classmethod
    def _is_separator(cls, text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return True
        # 纯分隔符行: ---, ***, ===, ——, ••, 等
        if cls.SEPARATOR_RE.match(stripped):
            return True
        return False
