"""LLM Tier splitter (v0.3.1+ 实现).

v0.3 阶段：仅预留接口，is_available() 永远返回 False，split() 抛 NotImplementedError。
这是为了"接口稳定，行为渐进"——pipeline 在 v0.3 已经能识别 tier1_llm 这个名字，
但实际实现等 v0.3.1+ 完成 OpenAI/xfyun 适配器后再开。

用法（v0.3.1+）：
    splitter = LLMSplitter(
        provider="openai",
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    result = splitter.split("长文本...")
"""

from __future__ import annotations
from typing import List, Optional
import logging

from ..core.base_splitter import BaseSentenceSplitter
from ..models import SentenceBlock


logger = logging.getLogger(__name__)


class LLMSplitter(BaseSentenceSplitter):
    """Tier 1 LLM 语义分句。

    v0.3 状态：接口预留，is_available()=False，split() 抛 NotImplementedError。
    """

    language = "auto"  # 支持中英文（取决于 LLM prompt）
    tier = "tier1_llm"

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout

    def is_available(self) -> bool:
        """v0.3 暂不实现。v0.3.1+ 改为检查 API key 是否配置。"""
        # TODO v0.3.1: 返回 self.api_key is not None
        return False

    def split(self, text: str) -> List[SentenceBlock]:
        """v0.3 抛 NotImplementedError。"""
        raise NotImplementedError(
            "LLM Tier (Tier 1) is not implemented yet in v0.3. "
            "Will be available in v0.3.1+. "
            "Use tier2 (ChineseSplitter/TextTiling) or tier3 (Rule) for now."
        )

    def __repr__(self) -> str:
        return f"LLMSplitter(provider={self.provider!r}, model={self.model!r}, available={self.is_available()})"
