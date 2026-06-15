"""Language router.

按语言路由到对应分句器：
- zh: ChineseSplitter (jieba 增强)
- en: EnglishSplitter
- mixed: 段落级路由（先用 zh splitter，en 段落单独处理）
- auto: 自动检测
"""

from __future__ import annotations
from typing import List, Tuple
from ..languages.zh.splitter import ChineseSplitter
from ..languages.en.splitter import EnglishSplitter
from ..languages.ja.splitter import JapaneseSplitter
from ..utils.language_detect import detect_language


class LanguageRouter:
    """多语言分句器路由。"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.zh_splitter = ChineseSplitter(self.config.get("zh", {}))
        self.en_splitter = EnglishSplitter(self.config.get("en", {}))
        self.ja_splitter = JapaneseSplitter(self.config.get("ja", {}))

    def route(self, text: str) -> Tuple[str, object]:
        """根据配置/自动检测路由到对应分句器。

        Returns:
            (detected_language, splitter_instance)
        """
        mode = self.config.get("language", "auto")

        if mode == "auto":
            lang = detect_language(text)
        else:
            lang = mode

        if lang == "zh":
            return "zh", self.zh_splitter
        elif lang == "en":
            return "en", self.en_splitter
        elif lang == "ja":
            return "ja", self.ja_splitter
        else:  # mixed
            # 简化处理：mixed 模式下，zh splitter 处理中文部分，en 部分由 en 兜底
            return "zh", self.zh_splitter

    def route_paragraphs(self, text: str) -> List[Tuple[str, str, object]]:
        """段落级路由（按段落切分，每段独立检测+分句）。

        Returns:
            [(lang, paragraph_text, splitter), ...]
        """
        paragraphs = [p for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [text]

        result = []
        for para in paragraphs:
            lang, splitter = self.route(para)
            result.append((lang, para, splitter))
        return result
