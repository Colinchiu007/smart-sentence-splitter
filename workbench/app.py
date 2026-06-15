"""Streamlit 体验工作台 — v0.9.8 多剧本管理 + 对比

启动:
    streamlit run workbench/app.py --server.port 8501

功能:
- 📝 分句: 字数控制 + 剧本分析 (角色/场景) + 场景/情绪
- 📺 字幕: SRT + ASS 格式下载
- 🎬 分镜: Storyboard JSON 输出
- 🔗 提示词: PROJECT-011 导出
- 📂 多剧本管理: 保存/切换/对比
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

# ===== Session 状态 (多剧本管理) =====
if "scripts" not in st.session_state:
    st.session_state.scripts = {}
if "current_script" not in st.session_state:
    st.session_state.current_script = "默认"
if "默认" not in st.session_state.scripts:
    st.session_state.scripts["默认"] = {"text": "", "result": None}

_DEFAULT_TEXT = (
    "小明走进超市。他拿了一瓶水。小红在公园等他。\n\n"
    "小明回到家。妈妈说：学校停课了。\n\n"
    "第二天，小明和小红决定去公园碰碰运气。"
)


def _render_script_analysis(result):
    """渲染剧本分析结果。"""
    if not result.script_analysis:
        return
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


def _render_sentences(result):
    """渲染分句结果。"""
    st.markdown("### 📋 分句结果")
    for s in result.sentences:
        badge = "🟦" if s.is_topic_boundary else "⬜"
        st.markdown(f"{badge} **{s.index}**. {s.text}  `{s.length_status}`")


def _render_scenes(result):
    """渲染场景信息。"""
    if not result.scenes:
        return
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


def _render_json(result):
    """渲染 JSON 下载。"""
    with st.expander("🔍 完整 JSON"):
        st.json(result.to_dict())
    st.download_button("💾 下载 JSON",
        data=json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        file_name="split_result.json", mime="application/json")


def _render_subtitles(result):
    """字幕导出。"""
    if not result.scenes:
        st.info("没有场景数据，无法生成字幕")
        return
    sub_exp = SubtitleExporter()
    st.markdown("### SRT 格式")
    srt = sub_exp.to_srt(result.scenes)
    st.text_area("SRT 输出", srt, height=250)
    st.download_button("📥 下载 .srt", data=srt, file_name="subtitles.srt", mime="text/plain")
    st.markdown("---")
    st.markdown("### ASS 格式")
    ass = sub_exp.to_ass(result.scenes)
    with st.expander("查看 ASS"):
        st.text(ass)
    st.download_button("📥 下载 .ass", data=ass, file_name="subtitles.ass", mime="text/plain")
    st.markdown(f"**统计**: 总时长 {sub_exp.total_duration(result.scenes):.1f}s")


def _render_storyboard(result):
    """分镜输出。"""
    if not result.scenes:
        st.info("没有场景数据")
        return
    sa = result.script_analysis or {}
    sb_exp = StoryboardExporter()
    storyboard = sb_exp.to_storyboard(
        result.scenes,
        synopsis=sa.get("synopsis", ""),
        characters=[{"name": c} for c in sa.get("characters", [])],
        settings=sa.get("settings", []),
    )
    st.markdown(f"**总场景**: {storyboard['total_scenes']} | **总时长**: {storyboard['total_duration']}s")
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
    with st.expander("🔍 完整 Storyboard JSON"):
        st.json(storyboard)
    st.download_button("💾 下载 storyboard.json",
        data=json.dumps(storyboard, ensure_ascii=False, indent=2),
        file_name="storyboard.json", mime="application/json")


def _render_prompts(result):
    """提示词导出。"""
    st.markdown("导出到 **[PROJECT-011](https://github.com/Colinchiu007/prompt-engine)**")
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
            if "context" in p and p["context"]:
                st.markdown("**📌 上下文 (v0.9.1)**")
                st.json(p["context"])
    if len(payloads) > 8:
        st.info(f"还有 {len(payloads)-8} 条折叠")
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
        f'-d \'{json.dumps(payloads[0], ensure_ascii=False) if payloads else {}}\'',
        language="bash",
    )


def _render_result_in_tabs(result, tab1, tab2, tab3, tab4):
    """在 4 个标签页中渲染分句结果。"""
    with tab1:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("语言", result.language)
        col2.metric("Tier", result.tier_used)
        col3.metric("句子", len(result.sentences))
        col4.metric("场景", result.total_scenes)
        _render_script_analysis(result)
        _render_sentences(result)
        _render_scenes(result)
        _render_json(result)
    with tab2:
        _render_subtitles(result)
    with tab3:
        _render_storyboard(result)
    with tab4:
        _render_prompts(result)


def _render_compare(result_a, result_b, tab1, tab2):
    """并排对比两个分句结果。"""
    with tab1:
        st.markdown("### 🆚 分句对比")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**📄 剧本 A** — {len(result_a.sentences)} 句, {result_a.total_scenes} 场")
            for s in result_a.sentences:
                st.markdown(f"  [{s.index}] {s.text}")
        with col_b:
            st.markdown(f"**📄 剧本 B** — {len(result_b.sentences)} 句, {result_b.total_scenes} 场")
            for s in result_b.sentences:
                st.markdown(f"  [{s.index}] {s.text}")

        # 差异标记
        if len(result_a.sentences) != len(result_b.sentences):
            st.info(f"⚠️ 句子数不同: A={len(result_a.sentences)} vs B={len(result_b.sentences)}")

    with tab2:
        st.markdown("### 🆚 场景对比")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**📄 剧本 A** — {result_a.total_scenes} 场")
            for sc in (result_a.scenes or []):
                st.markdown(f"  🎬 [{sc.segment_id}] {sc.text[:60]}...")
                st.markdown(f"     场景={sc.setting or '—'} 时长={sc.estimated_duration:.1f}s")
        with col_b:
            st.markdown(f"**📄 剧本 B** — {result_b.total_scenes} 场")
            for sc in (result_b.scenes or []):
                st.markdown(f"  🎬 [{sc.segment_id}] {sc.text[:60]}...")
                st.markdown(f"     场景={sc.setting or '—'} 时长={sc.estimated_duration:.1f}s")


# ===== 侧栏 =====
with st.sidebar:
    st.title("⚙️ 配置")
    st.markdown(f"**v{__version__}**")
    st.markdown("---")

    # 剧本管理
    st.subheader("📂 剧本管理")
    script_names = list(st.session_state.scripts.keys()) or ["默认"]
    cur = st.session_state.current_script
    selected = st.radio(
        "当前剧本", script_names,
        index=script_names.index(cur) if cur in script_names else 0,
        key="script_selector",
    )
    st.session_state.current_script = selected
    current_data = st.session_state.scripts.get(selected, {"text": "", "result": None})

    # 保存
    new_name = st.text_input("新剧本名称", placeholder="输入名称保存")
    col_save, col_del = st.columns(2)
    with col_save:
        if st.button("💾 保存", use_container_width=True) and new_name.strip():
            txt = st.session_state.get("_input_text", "")
            st.session_state.scripts[new_name.strip()] = {"text": txt, "result": None}
            st.session_state.current_script = new_name.strip()
            st.rerun()
    with col_del:
        if st.button("🗑️ 删除", use_container_width=True):
            if selected in st.session_state.scripts and len(st.session_state.scripts) > 1:
                del st.session_state.scripts[selected]
                remaining = list(st.session_state.scripts.keys())
                st.session_state.current_script = remaining[0]
                st.rerun()

    # 对比模式
    enable_compare = st.checkbox("🔄 对比模式", value=False,
                                 help="选择两个剧本并排对比")
    compare_target = None
    if enable_compare:
        others = [n for n in script_names if n != selected]
        if others:
            compare_target = st.selectbox("对比目标", others, index=0)

    st.markdown("---")

    # 分句配置
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
    enable_script = st.checkbox("剧本分析 (角色/场景)", value=True)
    enable_llm = st.checkbox("LLM Tier", value=False,
        help="需要 OPENAI_API_KEY 或 XFYUN_API_KEY")


# ===== 主区域 =====
if enable_compare and compare_target:
    # 对比模式: 只显示两个标签 (分句对比 + 场景对比)
    tab1, tab2 = st.tabs(["🆚 分句对比", "🆚 场景对比"])
else:
    tab1, tab2, tab3, tab4 = st.tabs(["📝 分句", "📺 字幕", "🎬 分镜", "🔗 提示词"])

# 文本输入
initial_text = current_data.get("text") or _DEFAULT_TEXT
text = st.text_area("📝 输入文本", value=initial_text, height=150, key="input_area")
st.session_state["_input_text"] = text

col_btn1, col_btn2 = st.columns([1, 5])
with col_btn1:
    run_btn = st.button("🚀 分句", type="primary", use_container_width=True)
with col_btn2:
    pass

if not (run_btn and text.strip()):
    # 无新输入: 显示上次缓存结果
    if current_data.get("result"):
        if enable_compare and compare_target:
            other_data = st.session_state.scripts.get(compare_target, {})
            if other_data.get("result"):
                _render_compare(current_data["result"], other_data["result"], tab1, tab2)
            else:
                st.info(f"'{compare_target}' 还没有分句结果，请先对此剧本点击分句")
        else:
            _render_result_in_tabs(current_data["result"], tab1, tab2, tab3, tab4)
    else:
        st.info("上方输入文本，点击 🚀 分句")
    st.stop()

# ===== 执行分句 =====
config = {
    "language": language, "mode": mode,
    "enable_era": enable_era,
    "enable_topic_segmentation": enable_topic_seg,
    "enable_script_analysis": enable_script,
    "enable_llm": enable_llm,
    "length": {
        "strategy": strategy_map[length_strategy],
        "min_chars": min_chars, "max_chars": max_chars,
    },
}

with st.spinner("分句中..."):
    try:
        splitter = SmartSentenceSplitter(config)
        result = splitter.split(text)
        st.session_state.scripts[st.session_state.current_script] = {"text": text, "result": result}
    except Exception as e:
        st.error(f"❌ 分句失败: {e}")
        st.stop()

if enable_compare and compare_target:
    other_data = st.session_state.scripts.get(compare_target, {})
    if other_data.get("result"):
        _render_compare(result, other_data["result"], tab1, tab2)
    else:
        st.info(f"'{compare_target}' 还没有分句结果，对比仅显示当前结果")
        _render_result_in_tabs(result, tab1, tab2, tab3, tab4)
else:
    _render_result_in_tabs(result, tab1, tab2, tab3, tab4)
