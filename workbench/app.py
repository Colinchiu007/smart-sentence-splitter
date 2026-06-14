"""Streamlit 体验工作台 - v0.5 新增.

启动:
    streamlit run workbench/app.py

功能:
- 输入文本 → 实时分句
- 选择 mode (fast/balanced/precise)
- 选择语言 (auto/zh/en)
- 启用/禁用 era + topic_segmentation
- 查看 JSON 输出
- 下载结果
"""

import sys
import json
import os
from pathlib import Path

# 加 splitter 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamlit as st

from splitter import SmartSentenceSplitter, __version__


# === 页面配置 ===
st.set_page_config(
    page_title="Smart Sentence Splitter",
    page_icon="✂️",
    layout="wide",
)

# === 侧边栏配置 ===
with st.sidebar:
    st.title("⚙️ 配置")
    st.markdown(f"**版本**: v{__version__}")
    st.markdown("---")

    language = st.selectbox(
        "语言",
        ["auto", "zh", "en"],
        index=0,
        help="auto: 自动检测; zh: 中文; en: 英文",
    )

    mode = st.selectbox(
        "模式",
        ["balanced", "fast", "precise"],
        index=0,
        help="fast: 仅规则 (零依赖); balanced: 语义+规则 (默认); precise: 含 LLM+主题",
    )

    st.markdown("---")
    st.subheader("高级选项")

    enable_era = st.checkbox("启用时代检测 (中文)", value=False)
    enable_topic_seg = st.checkbox("启用 TextTiling 主题分割", value=False)
    enable_llm = st.checkbox("启用 LLM Tier", value=False,
                            help="需要 OPENAI_API_KEY 或 XFYUN_API_KEY")

# === 主区域 ===
st.title("✂️ Smart Sentence Splitter")
st.caption("PROJECT-012 智能语义分句引擎 - 体验工作台")

# 输入文本
default_text = (
    "今天天气真好。我们去公园散步。路上遇到了多年未见的老朋友。\n\n"
    "他告诉我，最近人工智能技术发展很快。深度学习让很多不可能的事变成了可能。"
    "特别是大语言模型的崛起，彻底改变了人机交互的方式。"
)
text = st.text_area(
    "📝 输入文本",
    value=default_text,
    height=200,
    help="支持中英文混合。可以粘贴文章、对话、演讲稿等任意文本。",
)

# 操作按钮
col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])
with col_btn1:
    run_btn = st.button("🚀 分句", type="primary", use_container_width=True)
with col_btn2:
    clear_btn = st.button("🗑️ 清空", use_container_width=True)

if clear_btn:
    st.rerun()

# === 主体逻辑 ===
if run_btn and text.strip():
    # 构造配置
    config = {
        "language": language,
        "mode": mode,
        "enable_era": enable_era,
        "enable_topic_segmentation": enable_topic_seg,
        "enable_llm": enable_llm,
    }

    # 进度条
    progress = st.progress(0, "初始化分句器...")
    try:
        splitter = SmartSentenceSplitter(config)
        progress.progress(30, "分句中...")

        result = splitter.split(text)
        progress.progress(100, "完成!")
        progress.empty()

        # 显示元信息
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("语言", result.language)
        with col2:
            st.metric("tier", result.tier_used)
        with col3:
            st.metric("句子数", len(result.sentences))
        with col4:
            st.metric("场景数", result.total_scenes)

        # 分句结果
        st.markdown("### 📋 分句结果")
        for i, s in enumerate(result.sentences):
            badge = "🟦" if s.is_topic_boundary else "⬜"
            st.markdown(f"{badge} **{i}**. {s.text}")

        # 场景信息
        if result.scenes:
            st.markdown("### 🎬 场景结构")
            scene_data = []
            for sc in result.scenes:
                era = sc.era_info.era if sc.era_info else "—"
                scene_data.append({
                    "ID": sc.segment_id,
                    "文本预览": sc.text[:40] + ("..." if len(sc.text) > 40 else ""),
                    "字数": sc.target_words,
                    "时长(s)": f"{sc.estimated_duration:.1f}",
                    "时代": era,
                    "字幕块": len(sc.subtitles),
                })
            st.table(scene_data)

        # JSON 输出
        with st.expander("🔍 查看完整 JSON 输出"):
            st.json(result.to_dict())

        # 下载
        st.download_button(
            "💾 下载 JSON",
            data=json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            file_name="split_result.json",
            mime="application/json",
        )

    except Exception as e:
        progress.empty()
        st.error(f"❌ 分句失败: {e}")
        with st.expander("错误详情"):
            st.exception(e)
else:
    st.info("👆 上方输入文本，然后点击 🚀 分句 开始")

# === 底部说明 ===
st.markdown("---")
with st.expander("ℹ️ 关于这个工作台"):
    st.markdown("""
    **Smart Sentence Splitter** 是 PROJECT-012 的官方体验工作台。

    ### 工作流
    1. **输入文本**（支持中英文）
    2. **选择配置**（语言、模式、高级选项）
    3. **点击分句** → 实时处理
    4. **查看结果**（句子/场景/时代/JSON）

    ### 模式说明
    - **fast**: 仅规则分句（零依赖，最快）
    - **balanced**: 语义 + 规则（默认，推荐）
    - **precise**: 含 LLM Tier + TextTiling（最精确，需要 API key）

    ### Tier 说明
    - **Tier 1 (LLM)**: 用 LLM 语义切分（OpenAI/讯飞/Ollama）
    - **Tier 2 (Semantic)**: jieba 分词 + 词性 + 主题边界
    - **Tier 3 (Rule)**: 纯规则分句（标点 + 缩写表）

    自动降级：Tier 1 不可用 → Tier 2 → Tier 3
    """)
