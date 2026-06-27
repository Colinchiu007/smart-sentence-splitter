"""Tier 3 规则分句器（包中转）。"""

from ..languages.zh.splitter import ChineseSplitter
from ..languages.en.splitter import EnglishSplitter


class ChineseRuleSplitter(ChineseSplitter):
    """中文规则分句器（强制 Tier 3 模式，不用 jieba）。"""

    tier = "tier3_rule"

    def __init__(self, config: dict = None):
        cfg = (config or {}).copy()
        cfg["use_jieba"] = False  # 强制不用 jieba
        super().__init__(cfg)


class EnglishRuleSplitter(EnglishSplitter):
    """英文规则分句器。"""

    tier = "tier3_rule"
