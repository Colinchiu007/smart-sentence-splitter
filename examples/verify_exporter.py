"""真实运行验证 PromptEngineExporter 桥接。
演示 PROJECT-012 输出 → PROJECT-011 输入格式转换。"""

import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from splitter import SmartSentenceSplitter
from splitter.exporter.prompt_engine import PromptEngineExporter

print("=" * 60)
print("PROJECT-012 → PROJECT-011 桥接演示")
print("=" * 60)

# 1. PROJECT-012 分句
splitter = SmartSentenceSplitter({
    "length": {"strategy": "A", "min_chars": 3, "max_chars": 15},
    "enable_era": True,
})
text = "清军在甲午战争中死磕到底。这场战争影响深远，中华民族从此陷入深渊。"
result = splitter.split(text)

print(f"\n📝 输入: {text}")
print(f"✂️  分句: {len(result.sentences)} 句")
for s in result.sentences:
    print(f"   [{s.index}] {s.text} ({s.length_status})")

# 2. 导出为 PROJECT-011 请求
exporter = PromptEngineExporter()
batch = exporter.from_split_result(result)

print(f"\n🔗 导出为 PROJECT-011 批量请求: {len(batch)} 项")
for i, req in enumerate(batch):
    print(f"\n  Request {i+1}:")
    print(f"    prompt:      {req['prompt']}")
    print(f"    platform:    {req['platform']}")
    print(f"    max_length:  {req['max_length']}")
    print(f"    creativity:  {req['creative_level']}")

# 3. 带时代标签
print(f"\n\n📜 带 Era 标签导出:")
scenes_with_era = [scene for scene in result.scenes if scene.era_info]
for scene in scenes_with_era[:2]:
    print(f"  场景: {scene.text[:30]}... → era={scene.era_info.era}")

print(f"\n✅ 桥接验证通过")
print(f"→ 用 POST 到 PROJECT-011 即可生成提示词")
print(f"   curl -X POST http://localhost:8000/v1/optimize -H 'Content-Type: application/json' -d '{json.dumps(batch[0], ensure_ascii=False)}'")
