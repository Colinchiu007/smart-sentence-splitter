"""LLM Tier splitter (Tier 1) — v0.4 完整实做.

支持 provider:
- OpenAI (OpenAI 协议)
- Xfyun MAAS (讯飞 - OpenAI 协议)
- Ollama (本地 - OpenAI 协议)

所有 provider 共享 OpenAI 协议，通过 base_url 切换。

用法：
    from splitter.tiers.tier1_llm import LLMSplitter
    splitter = LLMSplitter({"provider": "openai", "model": "gpt-4o-mini"})
    if splitter.is_available():
        result = splitter.split("长文本...")
    else:
        # API key 未配置，自动降级
        pass
"""

from __future__ import annotations
import json
import re
import logging
from typing import List, Optional, Dict, Any

from ..core.base_splitter import BaseSentenceSplitter
from ..models import SentenceBlock
from ..llm import (
    LLMProvider,
    OpenAIProvider,
    XfyunProvider,
    OllamaProvider,
    build_split_prompt,
)

logger = logging.getLogger(__name__)


class LLMSplitter(BaseSentenceSplitter):
    """Tier 1 LLM 语义分句。"""

    language = "auto"
    tier = "tier1_llm"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.provider_name = self.config.get("provider", "openai")
        self.provider: LLMProvider = self._build_provider()
        self.max_retries = self.config.get("max_retries", 2)
        self.timeout = self.config.get("timeout", 30)
        self.temperature = self.config.get("temperature", 0.0)
        self.max_tokens = self.config.get("max_tokens", 4096)
        self.prompt_language = self.config.get("language", "auto")

    def _build_provider(self) -> LLMProvider:
        name = self.provider_name
        cfg = self.config
        if name == "openai":
            return OpenAIProvider(
                model=cfg.get("model", "gpt-4o-mini"),
                base_url=cfg.get("base_url"),
                timeout=cfg.get("timeout", 30),
            )
        elif name == "xfyun":
            return XfyunProvider(
                model=cfg.get("model", "astron-code-latest"),
                base_url=cfg.get("base_url"),
                timeout=cfg.get("timeout", 30),
            )
        elif name == "ollama":
            return OllamaProvider(
                model=cfg.get("model", "qwen2.5:7b"),
                base_url=cfg.get("base_url"),
                timeout=cfg.get("timeout", 60),
            )
        else:
            raise ValueError(
                f"Unknown LLM provider: {name}. "
                f"Supported: openai, xfyun, ollama"
            )

    def is_available(self) -> bool:
        """检查 provider 是否就绪（API key + 端点）。"""
        try:
            return self.provider.is_available()
        except Exception as e:
            logger.warning(f"LLM provider availability check failed: {e}")
            return False

    def split(self, text: str) -> List[SentenceBlock]:
        if not text or not text.strip():
            return []

        if not self.is_available():
            raise NotImplementedError(
                f"LLM Tier ({self.provider_name}) is not available. "
                f"Set the appropriate env var (OPENAI_API_KEY / XFYUN_API_KEY) "
                f"or start Ollama. Use tier2 (ChineseSplitter/TextTiling) for now."
            )

        prompt = build_split_prompt(text, language=self.prompt_language)
        messages = [
            {"role": "system", "content": "你是一个文本分句专家。"},
            {"role": "user", "content": prompt},
        ]

        # 重试
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.provider.chat(
                    messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                sentences = self._parse_response(response, text)
                return [self._make_block(s, i) for i, s in enumerate(sentences)]
            except Exception as e:
                last_error = e
                logger.warning(f"LLM split attempt {attempt + 1} failed: {e}")
                continue

        raise RuntimeError(
            f"LLM split failed after {self.max_retries + 1} attempts: {last_error}"
        )

    def _parse_response(self, response: str, original_text: str) -> List[str]:
        """解析 LLM 响应，3 层容错。

        1. 直接 JSON 解析
        2. 正则提取 JSON 数组
        3. 兜底按行切分
        """
        if not response or not response.strip():
            return []

        # 1. 直接 JSON
        try:
            data = json.loads(response)
            if isinstance(data, list):
                return [str(s).strip() for s in data if s and str(s).strip()]
        except (json.JSONDecodeError, ValueError):
            pass

        # 2. 正则提取 JSON 数组
        match = re.search(r"\[.*?\]", response, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, list):
                    return [str(s).strip() for s in data if s and str(s).strip()]
            except (json.JSONDecodeError, ValueError):
                pass

        # 3. 兜底：按行切分 + 过滤非句子行
        lines = [line.strip() for line in response.splitlines() if line.strip()]
        # 过滤 markdown / 解释性文本
        sentences = []
        for line in lines:
            # 跳过 markdown 标题
            if line.startswith("#") or line.startswith("```"):
                continue
            # 跳过纯解释（不含中文标点也不含英文标点）
            if not any(p in line for p in "。！？.!?;，,;："):
                continue
            sentences.append(line)

        if sentences:
            return sentences

        # 4. 最后兜底：把原文按标点切
        return [s for s in re.split(r"(?<=[。！？.!?;])\s*", original_text) if s]

    def _make_block(self, text: str, index: int) -> SentenceBlock:
        text = text.strip()
        if not text:
            text = "(empty)"
        return SentenceBlock(
            text=text,
            index=index,
            tier=self.tier,
            language=self.language,
        )

    def __repr__(self) -> str:
        return (
            f"LLMSplitter(provider={self.provider_name!r}, "
            f"model={self.provider.model!r}, available={self.is_available()})"
        )
