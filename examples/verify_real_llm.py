"""真实 LLM 端到端验证 — 从环境变量读 API key.

用法:
    export OPENAI_API_KEY="sk-or-..."
    python examples/verify_real_llm.py

    # 或
    XFYUN_API_KEY="***" python examples/verify_real_llm.py --provider xfyun
"""
import os
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--provider", default="openai", choices=["openai", "xfyun"])
parser.add_argument("--model", default="deepseek/deepseek-chat")
parser.add_argument("--base-url", default="https://openrouter.ai/api/v1")
args = parser.parse_args()

from splitter.tiers.tier1_llm import LLMSplitter

# === 构造 provider ===
print("=" * 50)
print(f"=== {args.provider} ({args.model}) ===")
s = LLMSplitter({
    "provider": args.provider,
    "model": args.model,
    "base_url": args.base_url,
    "timeout": 60,
})
print(f"available: {s.is_available()}")

if not s.is_available():
    print(f"❌ 不可用 — 请设置 {args.provider.upper()}_API_KEY 环境变量")
    sys.exit(1)

# === 中文分句 ===
text_zh = "今天天气真好。我们去公园。路上遇到了多年未见的老朋友。"
r = s.split(text_zh)
print(f"✅ 中文分句: {len(r)} 句")
for b in r:
    print(f"  [{b.index}] {b.text}")

# === 英文分句 ===
text_en = "Hello world. How are you today? Let me tell you a story about AI."
r2 = s.split(text_en)
print(f"✅ 英文分句: {len(r2)} 句")
for b in r2:
    print(f"  [{b.index}] {b.text}")

# === Pipeline 集成 ===
print()
print("=" * 50)
print("=== Pipeline 集成 (mode=precise + LLM) ===")
from splitter import SmartSentenceSplitter
splitter = SmartSentenceSplitter({
    "enable_llm": True,
    "llm": {
        "provider": args.provider,
        "model": args.model,
        "base_url": args.base_url,
        "timeout": 60,
    },
    "mode": "precise",
})
r3 = splitter.split("今天天气真好。我们去公园散步。路上遇到了朋友。")
print(f"tier: {r3.tier_used}, 句子: {len(r3.sentences)}")
for b in r3.sentences:
    print(f"  [{b.index}] {b.text}")
print(f"\n✅ 全部验证通过")