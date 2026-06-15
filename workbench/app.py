"""Streamlit 体验工作台 — v0.9 升级版集成了 v0.6-v0.8 全部功能

启动:
    streamlit run workbench/app.py --server.port 8501

功能:
- 📝 分句: 字数控制 + 剧本分析 (角色/场景) + 场景/情绪
- 📺 字幕: SRT + ASS 格式下载
- 🎬 分镜: Storyboard JSON 输出 + 分镜视图
- 🔗 提示词: PROJECT-011 导出
"""

import sys, json, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamlit as st
from splitter import SmartSentenceSplitter, __version__
from splitter.exporter.subtitle_exporter import SubtitleExporter
from splitter.exporter.storyboard import StoryboardExporter
from splitter.exporter.prompt_engine import PromptEngineExporter

st.set_page_config(
    page_title="Smart Sentence Splitter",
    page_icon="✂️",
    layout="wide",
)

# ===== 侧栏 =====
with st.sidebar:
    st.title("⚙️ 配置")
    st.markdown(f"**v{__version__}**")
    st.markdown("---")

    language = st.selectbox("语言", ["auto", "zh", "en"], index=0)
    mode = st.selectbox("模式", ["balanced", "fast", "precise"], index=0)

    st.markdown("---")
    st.subheader("字数控制")
    length_strategy = st.selectbox("策略", ["B (标尺)", "A (重切)", "off (透传)"], index=0)
    strategy_map = {"B (标尺)": "B", "A (重切)": "A", "off (透传)": "off"}
    min_chars = st.number_input("最小字数", 3, 10, 3)
    max_chars = st.number_input("最大字数", 10, 50, 15)

    st.markdown("---")
    st.subheader("高级选项")
    enable_era = st.checkbox("时代检测", value=False)
    enable_topic_seg = st.checkbox("TextTiling 主题分割", value=False)
    enable_script = st.checkbox("剧本分析 (角色/场景)", value=False)
    enable_llm = st.checkbox("LLM Tier", value=False,
        help="需要 OPENAI_API_KEY 或 XFYUN_API_KEY")

# ===== 主区域 =====
tab1, tab2, tab3, tab4 = st.tabs(["📝 分句", "📺 字幕", "🎬 分镜", "🔗 提示词"])

# ===== 默认文本 =====
default_text = (
    "小明走进超市。他拿了一瓶水。小红在公园等他。\n\n"
    "小明回到家。妈妈说：学校停课了。\n\n"
    "第二天，小明和小红决定去公园碰碰运气。"
)

text = st.text_area("📝 输入文本", value=default_text, height=150)

col_btn1, col_btn2 = st.columns([1, 5])
with col_btn1:
    run_btn = st.button("🚀 分句", type="primary", use_container_width=True)
with col_btn2:
    pass

if not (run_btn and text.strip()):
    st.info("上方输入文本，点击 🚀 分句")
    st.stop()

# ===== 执行分句 =====
config = {
    "language": language,
    "mode": mode,
    "enable_era": enable_era,
    "enable_topic_segmentation": enable_topic_seg,
    "enable_script_analysis": enable_script,
    "enable_llm": enable_llm,
    "length": {
        "strategy": strategy_map[length_strategy],
        "min_chars": min_chars,
        "max_chars": max_chars,
    },
}

with st.spinner("分句中..."):
    try:
        splitter = SmartSentenceSplitter(config)
        result = splitter.split(text)
    except Exception as e:
        st.error(f"❌ 分句失败: {e}")
        st.stop()

# ================================================================
# TAB 1: 📝 分句
# ================================================================
with tab1:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("语言", result.language)
    with col2:
        st.metric("Tier", result.tier_used)
    with col3:
        st.metric("句子", len(result.sentences))
    with col4:
        st.metric("场景", result.total_scenes)

    # 剧本分析结果
    if result.script_analysis:
        sa = result.script_analysis
        st.markdown("### 📜 剧本分析")
        c1, c2 = st.columns(2)
        with c1:
            chars = sa.get("characters", [])
            st.markdown(f"**角色**: {', '.join(chars) if chars else '—'}")
            st.markdown(f"**梗概**: {sa.get('synopsis', '')[:100]}...")
        with c2:
            settings = sa.get("settings", [])
            st.markdown(f"**场景**: {', '.join(settings) if settings else '—'}")

    # 分句结果
    st.markdown("### 📋 分句结果")
    for s in result.sentences:
        badge = "🟦" if s.is_topic_boundary else "⬜"
        status = {"ok": "", "too_long": "⚠️", "too_short": "📄"}
        st.markdown(f"{badge} **{s.index}**. {s.text}  `{s.length_status}`")

    # 场景信息
    if result.scenes:
        st.markdown("### 🎬 场景结构")
        scene_rows = []
        for sc in result.scenes:
            chars = ", ".join(sc.characters) if sc.characters else "—"
            scene_rows.append({
                "ID": sc.segment_id,
                "文本": sc.text[:40] + ("..." if len(sc.text) > 40 else ""),
                "角色": chars,
                "场景": sc.setting or "—",
                "情绪": sc.mood or "—",
                "时长(s)": f"{sc.estimated_duration:.1f}",
            })
        st.table(scene_rows)

    # JSON
    with st.expander("🔍 完整 JSON"):
        st.json(result.to_dict())
    st.download_button("💾 下载 JSON",
        data=json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        file_name="split_result.json", mime="application/json")

# ================================================================
# TAB 2: 📺 字幕
# ================================================================
with tab2:
    if not result.scenes:
        st.info("没有场景数据，无法生成字幕")
        st.stop()

    sub_exp = SubtitleExporter()

    st.markdown("### SRT 格式")
    srt = sub_exp.to_srt(result.scenes)
    st.text_area("SRT 输出", srt, height=250)
    st.download_button("📥 下载 .srt", data=srt, file_name="subtitles.srt",
                      mime="text/plain")

    st.markdown("---")
    st.markdown("### ASS 格式")
    ass = sub_exp.to_ass(result.scenes)
    with st.expander("查看 ASS"):
        st.text(ass)
    st.download_button("📥 下载 .ass", data=ass, file_name="subtitles.ass",
                      mime="text/plain")

    st.markdown(f"**统计**: {sub_exp.count_subtitles(result.scenes)} 个字幕块, "
                f"总时长 {sub_exp.total_duration(result.scenes):.1f}s")

# ================================================================
# TAB 3: 🎬 分镜
# ================================================================
with tab3:
    if not result.scenes:
        st.info("没有场景数据")
        st.stop()

    # 构造 script_analysis 给 storyboard
    sa = result.script_analysis or {}
    sb_exp = StoryboardExporter()
    storyboard = sb_exp.to_storyboard(
        result.scenes,
        synopsis=sa.get("synopsis", ""),
        characters=[{"name": c} for c in sa.get("characters", [])],
        settings=sa.get("settings", []),
    )

    st.markdown(f"**总场景**: {storyboard['total_scenes']} | "
                f"**总时长**: {storyboard['total_duration']}s")

    # 分镜卡片
    for i, scene in enumerate(storyboard["scenes"]):
        with st.container():
            bg = "#1a1a2e" if i % 2 == 0 else "#16213e"
            st.markdown(
                f"""<div style="background:{bg};padding:12px;border-radius:8px;margin:6px 0">
                <b>🎬 第 {i+1} 镜</b> | {scene['duration_s']}s<br>
                <b>画面</b>: {scene['image_hint'][:120]}...<br>
                <b>角色</b>: {', '.join(scene['characters']) if scene['characters'] else '—'}
                | <b>场景</b>: {scene.get('setting', '') or '—'}
                | <b>氛围</b>: {scene.get('mood', '') or '—'}
                </div>""",
                unsafe_allow_html=True,
            )

    # JSON
    with st.expander("🔍 完整 Storyboard JSON"):
        st.json(storyboard)
    st.download_button("💾 下载 storyboard.json",
        data=json.dumps(storyboard, ensure_ascii=False, indent=2),
        file_name="storyboard.json", mime="application/json")

# ================================================================
# TAB 4: 🔗 提示词
# ================================================================
with tab4:
    st.markdown("导出到 **[PROJECT-011](https://github.com/Colinchiu007/prompt-engine)**")
    st.caption("将 PROJRCT-012 的分句结果转换为 PROJECT-011 的优化请求格式")

    exporter = PromptEngineExporter()
    payloads = []

    for scene in result.scenes:
        for sentence in scene.sentences:
            era = scene.era_info.era if scene.era_info else None
            payloads.append(exporter.to_optimize_request(sentence, era=era))

    st.markdown(f"**{len(payloads)}** 条优化请求已生成")

    for i, p in enumerate(payloads[:8]):
        with st.expander(f"请求 {i+1}: {p['prompt'][:40]}..."):
            st.json(p)

    if len(payloads) > 8:
        st.info(f"还有 {len(payloads)-8} 条折叠")

    # 批量 JSON
    with st.expander("🔍 完整批量请求 JSON"):
        st.json(payloads)
    st.download_button("💾 下载 prompt_batch.json",
        data=json.dumps(payloads, ensure_ascii=False, indent=2),
        file_name="prompt_batch.json", mime="application/json")

    st.markdown("---")
    st.markdown("**调用示例**:")
    st.code(
        f'curl -X POST http://localhost:8013/v1/optimize '
        f'-H "Content-Type: application/json" '
        f'-d \'{json.dumps(payloads[0], ensure_ascii=False)}\'',
        language="bash",
    )