"""完整剧本→分镜实测"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from splitter import SmartSentenceSplitter
from splitter.script.script_analyzer import ScriptAnalyzer
from splitter.exporter.storyboard import StoryboardExporter

print("=" * 60)
print("剧本→故事梗概→角色→分镜 全流程")
print("=" * 60)

# 输入: 一段剧本
script = """小明是一个普通的高中生。一天，他走进超市，发现货架快空了。

他在货架前犹豫要不要买最后一瓶水。这时小红走过来，说："快拿吧，不然没了。"

小明拿了水，回到家。妈妈问他怎么了，他说超市快空了。

第二天，学校停课了。小明和小红决定去公园碰碰运气。"""

print(f"\n📜 剧本 ({len(script)}字):")
print(script[:200])

# 1. 剧本分析
analyzer = ScriptAnalyzer()
info = analyzer.analyze(script)
print(f"\n🔍 剧本分析:")
print(f"  角色: {info['characters']}")
print(f"  场景: {info['settings']}")
print(f"  梗概: {info['synopsis'][:60]}...")

# 2. 分句 + 场景打包
splitter = SmartSentenceSplitter({
    "length": {"strategy": "A", "min_chars": 3, "max_chars": 15},
    "enable_era": True,
})
result = splitter.split(script)

# 3. 分镜导出
exporter = StoryboardExporter()
storyboard = exporter.to_storyboard(
    result.scenes,
    synopsis=info["synopsis"],
    characters=[{"name": c} for c in info["characters"]],
    settings=info["settings"],
)

print(f"\n🎬 分镜 ({storyboard['total_scenes']} 场, 共 {storyboard['total_duration']}s):")
for i, scene in enumerate(storyboard["scenes"]):
    print(f"  [{i+1}] {scene['duration_s']}s — {scene['text'][:30]}...")
    print(f"      角色:{scene['characters']} 场景:{scene['setting']} 氛围:{scene['mood']}")
    print(f"      提示: {scene['image_hint'][:60]}...")

print(f"\n✅ 验证通过")
print(f"→ 输出可传给 PROJECT-011 POST /v1/optimize/batch")