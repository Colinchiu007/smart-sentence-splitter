"""真实运行验证 length_strategy."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from splitter import SmartSentenceSplitter

text = "今天天气真好，阳光明媚，我们决定去郊外的公园散步，享受难得的周末时光。"

print("=" * 60)
print("=== 默认 (B 模式) ===")
s = SmartSentenceSplitter()  # 默认
r = s.split(text)
print(f"句子数: {len(r.sentences)}")
for x in r.sentences:
    print(f"  [{x.index}] {x.text} (status={x.length_status}, applied={x.length_strategy_applied})")

print()
print("=" * 60)
print("=== A 模式 (重切) ===")
s = SmartSentenceSplitter({"length": {"strategy": "A", "min_chars": 3, "max_chars": 15}})
r = s.split(text)
print(f"句子数: {len(r.sentences)}")
for x in r.sentences:
    print(f"  [{x.index}] {x.text} (status={x.length_status}, applied={x.length_strategy_applied})")

print()
print("=" * 60)
print("=== off 模式 (透传) ===")
s = SmartSentenceSplitter({"length": {"strategy": "off"}})
r = s.split(text)
print(f"句子数: {len(r.sentences)}")
for x in r.sentences:
    print(f"  [{x.index}] {x.text} (status={x.length_status}, applied={x.length_strategy_applied})")
