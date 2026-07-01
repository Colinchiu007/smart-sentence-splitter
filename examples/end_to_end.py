#!/usr/bin/env python3
"""端到端示例: 输入剧本 → 分句 → 场景 → 字幕 → 分镜 → PROJECT-011 桥接

用法:
    # 仅分句 (不需要 PROJECT-011)
    python examples/end_to_end.py

    # 带 PROJECT-011 优化 (需要先启动 011)
    python examples/end_to_end.py --optimize

    # 自定义输入
    python examples/end_to_end.py --text "你的剧本..."
"""

import sys, json, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from splitter import SmartSentenceSplitter, __version__
from splitter.exporter.subtitle_exporter import SubtitleExporter
from splitter.exporter.storyboard import StoryboardExporter
from splitter.exporter.prompt_engine import PromptEngineExporter


def run_pipeline(text: str, optimize: bool = False):
    """完整管线演示。"""
    print(f"{'='*60}")
    print(f"📝 Smart Sentence Splitter v{__version__}")
    print(f"{'='*60}")

    # ===== 分句配置 =====
    config = {
        "enable_script_analysis": True,  # 启用剧本分析 (角色/场景)
        "mode": "balanced",
        "length": {"strategy": "B", "max_chars": 15},
    }

    # ===== 1. 分句 =====
    splitter = SmartSentenceSplitter(config)
    result = splitter.split(text)

    print(f"\n📌 语言: {result.language}")
    print(f"📌 Tier:  {result.tier_used}")
    print(f"📌 句子:  {len(result.sentences)}")
    print(f"📌 场景:  {result.total_scenes}")

    # ===== 2. 剧本分析 =====
    if result.script_analysis:
        sa = result.script_analysis
        print(f"\n📜 角色: {', '.join(sa.get('characters', [])) or '—'}")
        print(f"📜 场景: {', '.join(sa.get('settings', [])) or '—'}")
        print(f"📜 梗概: {sa.get('synopsis', '')[:100]}...")

    # ===== 3. 句子列表 =====
    print(f"\n📋 句子 ({len(result.sentences)}):")
    for s in result.sentences:
        badge = "🟦" if s.is_topic_boundary else "⬜"
        print(f"  {badge} [{s.index}] {s.text}  `{s.length_status}`")

    # ===== 4. 场景结构 =====
    if result.scenes:
        print(f"\n🎬 场景 ({len(result.scenes)}):")
        for sc in result.scenes:
            chars = ", ".join(sc.characters) if sc.characters else "—"
            print(f"  [{sc.segment_id}] {sc.text[:50]}...")
            print(f"      角色={chars} 场景={sc.setting or '—'} 情绪={sc.mood or '—'} 时长={sc.estimated_duration:.1f}s")

    # ===== 5. 字幕导出 =====
    if result.scenes:
        sub_exp = SubtitleExporter()
        srt = sub_exp.to_srt(result.scenes)
        ass = sub_exp.to_ass(result.scenes)
        count = sub_exp.count_subtitles(result.scenes)
        print(f"\n📺 字幕: {count[0]} 块, {count[1]:.1f}s")
        print(f"  SRT ({len(srt)} 字符)")
        print(f"  ASS ({len(ass)} 字符)")

    # ===== 6. 分镜输出 =====
    if result.scenes:
        story = StoryboardExporter()
        sb_json = story.to_storyboard(result.scenes)
        print(f"\n🎬 分镜: {len(sb_json['scenes'])} 场")

    # ===== 7. PROJECT-011 桥接 =====
    if optimize:
        exp = PromptEngineExporter()
        batch = exp.from_split_result(result)
        print(f"\n🔗 PROJECT-011 请求 ({len(batch)} 条):")
        for i, req in enumerate(batch):
            ctx = req.get("context", {})
            print(f"  [{i}] prompt: {req['prompt'][:40]}...")
            print(f"      character={ctx.get('character')} setting={ctx.get('setting')}")

        # 发送优化请求
        from splitter.exporter.prompt_engine_client import PromptEngineClient
        client = PromptEngineClient("http://localhost:8013")
        try:
            results = client.optimize_batch(batch)
            print(f"\n  ✅ {len(results)} 条优化成功")
            for i, p in enumerate(results):
                print(f"\n  [{i}] ORIG: {batch[i]['prompt']}")
                print(f"       OPT:  {p[:100]}...")
        except Exception as e:
            print(f"\n  ❌ 优化失败 (PROJECT-011 未启动?): {e}")
    else:
        print(f"\n🔗 跳过 PROJECT-011 (加 --optimize 启用)")

    print(f"\n✅ 管线完成")


if __name__ == "__main__":
    optimize = "--optimize" in sys.argv

    # 默认文本
    default_text = (
        "小明走进超市。他拿了一瓶水。小红在公园等他。\n\n"
        "小明回到家。妈妈说：学校停课了。\n\n"
        "第二天，小明和小红决定去公园碰碰运气。"
    )

    # 自定义文本
    for i, arg in enumerate(sys.argv):
        if arg == "--text" and i + 1 < len(sys.argv):
            default_text = sys.argv[i + 1]
            break

    run_pipeline(default_text, optimize=optimize)
