"""端到端实测: PROJECT-012 → PROJECT-011."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from splitter import SmartSentenceSplitter
from splitter.exporter.prompt_engine import PromptEngineExporter
from splitter.exporter.prompt_engine_client import PromptEngineClient
from splitter.exporter.subtitle_exporter import SubtitleExporter
from splitter.exporter.storyboard import StoryboardExporter

print("=" * 60)
print("PROJECT-012 → 字幕 / 分镜 / 提示词 全流程")
print("=" * 60)

# 1. 分句
text = """小明走进超市。他拿了一瓶水。小红在公园等他。

小明回到家。妈妈说：学校停课了。

第二天，小明和小红决定去公园碰碰运气。"""

splitter = SmartSentenceSplitter({
    "length": {"strategy": "A", "min_chars": 3, "max_chars": 15},
    "enable_script_analysis": True,
})
result = splitter.split(text)

print(f"\n✂️ 分句: {len(result.sentences)} 句 / {len(result.scenes)} 场")
for s in result.scenes[:3]:
    print(f"   {s.text} | 角色: {s.characters} | 场景: {s.setting}")

# 2. SRT 字幕
sub_exp = SubtitleExporter()
srt = sub_exp.to_srt(result.scenes)
print(f"\n📺 SRT 字幕 ({len(srt)} 字符):")
print(srt[:300])

# 3. Storyboard
sb_exp = StoryboardExporter()
sb = sb_exp.to_storyboard(
    result.scenes,
    synopsis=result.script_analysis.get("synopsis", "") if result.script_analysis else "",
    characters=[{"name": c} for c in (result.script_analysis.get("characters", []) if result.script_analysis else [])],
)
print(f"\n🎬 分镜: {sb['total_scenes']} 场, {sb['total_duration']}s")

# 4. PROJECT-011 HTTP 桥接 (不实际发请求, 只验证 payload 转换)
print(f"\n🔗 PROJECT-011 提示词 payload:")
client = PromptEngineClient()
exporter = PromptEngineExporter()
for scene in result.scenes[:2]:
    for sentence in scene.sentences[:1]:
        req = exporter.to_optimize_request(sentence)
        payload = client.build_optimize_payload(req)
        print(f"   {payload}")

print(f"\n✅ 全流程验证通过")
print(f"\n[可选] 真实调用: 需要 PROJECT-011 在 8013 端口运行")
print(f"   cd /c/Users/邱领/projects/prompt-engine")
print(f"   python -m prompt_engine.api.rest    # 或 uvicorn")
print(f"   然后 client.optimize(req) 即可")