"""真实 LLM 端到端集成测试（v0.5 新增）.

需要环境变量中设置 LLM API key：
- OPENAI_API_KEY (OpenAI 兼容)
- XFYUN_API_KEY (讯飞 MAAS)

如果没设置 key，所有测试自动 skip（不报错）。

跑法：
    export OPENAI_API_KEY=sk-xxx
    python -m pytest tests/integration/test_real_llm.py -v
"""

import os
import pytest

# 检查 key 是否存在
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
XFYUN_KEY = os.getenv("XFYUN_API_KEY")

skip_openai = pytest.mark.skipif(
    not OPENAI_KEY, reason="OPENAI_API_KEY not set, skipping real LLM test"
)
skip_xfyun = pytest.mark.skipif(
    not XFYUN_KEY, reason="XFYUN_API_KEY not set, skipping real LLM test"
)


@pytest.mark.integration
@skip_openai
def test_openai_real_chinese_split():
    """真实 OpenAI 跑中文分句。"""
    from splitter.tiers.tier1_llm import LLMSplitter

    splitter = LLMSplitter({
        "provider": "openai",
        "model": "gpt-4o-mini",
    })
    assert splitter.is_available() is True

    text = "今天天气真好。我们去公园散步。路上遇到了朋友。"
    result = splitter.split(text)
    assert len(result) >= 2
    # 验证每句含标点
    for s in result:
        assert s.text
        assert any(p in s.text for p in "。！？.!?;")


@pytest.mark.integration
@skip_openai
def test_openai_real_english_split():
    """真实 OpenAI 跑英文分句。"""
    from splitter.tiers.tier1_llm import LLMSplitter

    splitter = LLMSplitter({
        "provider": "openai",
        "model": "gpt-4o-mini",
    })
    text = "Hello world. How are you? I am fine."
    result = splitter.split(text)
    assert len(result) >= 2
    for s in result:
        assert s.text
        assert any(p in s.text for p in ".!?;")


@pytest.mark.integration
@skip_openai
def test_openai_in_pipeline():
    """真实 OpenAI 集成到 SmartSentenceSplitter。"""
    from splitter import SmartSentenceSplitter

    splitter = SmartSentenceSplitter({
        "enable_llm": True,
        "llm": {
            "provider": "openai",
            "model": "gpt-4o-mini",
        },
    })
    text = "今天天气真好。我们去公园。"
    result = splitter.split(text)
    # tier_used 应该是 tier1_llm
    assert result.tier_used is not None
    # tier_used 含 tier1_llm 或降级
    assert "tier" in result.tier_used or "rule" in result.tier_used


@pytest.mark.integration
@skip_xfyun
def test_xfyun_real_chinese_split():
    """真实讯飞 MAAS 跑中文分句。"""
    from splitter.tiers.tier1_llm import LLMSplitter

    splitter = LLMSplitter({
        "provider": "xfyun",
    })
    assert splitter.is_available() is True

    text = "今天天气真好。我们去公园散步。"
    result = splitter.split(text)
    assert len(result) >= 2


@pytest.mark.integration
@skip_xfyun
def test_xfyun_in_pipeline():
    """真实讯飞集成到 SmartSentenceSplitter。"""
    from splitter import SmartSentenceSplitter

    splitter = SmartSentenceSplitter({
        "enable_llm": True,
        "llm": {"provider": "xfyun"},
    })
    text = "今天天气真好。我们去公园。"
    result = splitter.split(text)
    assert result.tier_used is not None
