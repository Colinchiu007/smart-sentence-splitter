"""真实 LLM 端到端验证 — 用 coo profile 的 key."""
import os, sys, yaml

# 从 coo profile 读 key
with open(r"C:\hermes-home\profiles\coo\config.yaml") as f:
    cfg = yaml.safe_load(f)

openrouter_key = cfg["providers"]["openrouter"]["api_key"]
os.environ["OPENAI_API_KEY"] = openrouter_key

from splitter.tiers.tier1_llm import LLMSplitter

# === OpenRouter (deepseek) ===
print("=" * 50)
print("=== OpenRouter deepseek-chat ===")
s = LLMSplitter({
    "provider": "openai",
    "model": "deepseek/deepseek-chat",
    "base_url": "https://openrouter.ai/api/v1",
    "timeout": 60,
})
print(f"available: {s.is_available()}")
if s.is_available():
    r = s.split("今天天气真好。我们去公园。路上遇到了多年未见的老朋友。")
    print(f"sentences: {len(r)}")
    for b in r:
        print(f"  [{b.index}] {b.text}")
else:
    print("SKIP - not available")

# === 英文 ===
print()
print("=" * 50)
print("=== OpenRouter — English ===")
s2 = LLMSplitter({
    "provider": "openai",
    "model": "deepseek/deepseek-chat",
    "base_url": "https://openrouter.ai/api/v1",
    "timeout": 60,
})
if s2.is_available():
    t = "Hello world. How are you today? Let me tell you a story about AI."
    r2 = s2.split(t)
    print(f"sentences: {len(r2)}")
    for b in r2:
        print(f"  [{b.index}] {b.text}")
else:
    print("SKIP")

# === pipeline 集成 ===
print()
print("=" * 50)
print("=== Pipeline 集成 (mode=precise + LLM) ===")
from splitter import SmartSentenceSplitter
splitter = SmartSentenceSplitter({
    "enable_llm": True,
    "llm": {
        "provider": "openai",
        "model": "deepseek/deepseek-chat",
        "base_url": "https://openrouter.ai/api/v1",
        "timeout": 60,
    },
})
r3 = splitter.split("今天天气真好。我们去公园散步。路上遇到了朋友。")
print(f"tier_used: {r3.tier_used}")
print(f"sentences: {len(r3.sentences)}")
for b in r3.sentences:
    print(f"  [{b.index}] {b.text}")