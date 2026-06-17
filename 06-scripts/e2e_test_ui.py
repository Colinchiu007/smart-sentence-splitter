"""Project-012 × Project-011 联合测试前端

启动:
    streamlit run scripts/e2e_test_ui.py --server.port 8510

功能:
    输入文字 → 012 分句 → 带 context → 011 优化 → 图片预览
"""

import sys, json, hashlib, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamlit as st
from splitter import SmartSentenceSplitter
from splitter.exporter.prompt_engine import PromptEngineExporter
from splitter.exporter.prompt_engine_client import PromptEngineClient

st.set_page_config(page_title="文案生图", page_icon="🎨", layout="wide")

st.markdown("# 🎨 文案生图")
st.markdown("PROJECT-012 × PROJECT-011 联合测试 — 输入文案 → 自动分句 → AI 优化 → 图片生成预览")

# ===== 侧边栏配置 =====
with st.sidebar:
    st.markdown("### ⚙️ 配置")

    # 011 服务地址
    server_url = st.text_input("PROJECT-011 地址",
        value="http://localhost:8014", key="e2e_server")

    # 分句配置
    st.markdown("### 📝 分句参数")
    enable_script = st.checkbox("剧本分析 (角色/场景)", value=True,
        help="提取角色、场景、梗概")
    enable_llm = st.checkbox("LLM Tier (需 API Key)", value=False)
    creative_level = st.slider("creative_level", 1, 10, 7,
        help="越高 LLM 越自由发挥")
    max_length = st.slider("最大输出字数", 100, 1000, 300)

    st.markdown("---")
    health_btn = st.button("🩺 检查 011 状态")
    if health_btn:
        try:
            c = PromptEngineClient(server_url, timeout=5)
            ok = c.health_check()
            if ok:
                st.success(f"✅ {server_url} 在线")
            else:
                st.error(f"❌ {server_url} 不可用")
        except Exception as e:
            st.error(f"❌ {e}")

# ===== 主区域 =====

# 示例故事
_EXAMPLE = """小明走进超市。他拿了一瓶水。小红在公园等他。
小明回到家。妈妈说：学校停课了。
第二天，小明和小红决定去公园碰碰运气。"""

col1, col2 = st.columns([1, 1])

with col1:
    text = st.text_area("📖 输入一段故事文字",
        value=_EXAMPLE, height=180)

    run_btn = st.button("🚀 分句 → 优化 → 预览", type="primary",
        use_container_width=True)

if run_btn and text.strip():
    with st.spinner("正在分句..."):
        # 1. 012 分句
        config = {"enable_script_analysis": enable_script}
        if enable_llm:
            config["enable_llm"] = True
        s = SmartSentenceSplitter(config)
        result = s.split(text)

        # 2. 导出带 context 的 batch
        exporter = PromptEngineExporter(
            default_creative_level=creative_level,
            default_max_length=max_length,
        )
        batch = exporter.from_split_result(result)

    with st.spinner(f"正在调用 {server_url} ..."):
        # 3. 调 011
        try:
            client = PromptEngineClient(server_url, timeout=120)
            results = client.optimize_batch(batch)
            st.success(f"✅ 优化成功 — {len(results)} 条")
        except Exception as e:
            st.error(f"❌ 011 调用失败: {e}")
            st.info("💡 可能原因：PROJECT-011 服务未启动、LLM API Key 失效、或网络不通")
            st.stop()

    # 检查是否有错误
    has_llm_error = any(r.get("error") for r in results)
    all_template = all(
        r.get("optimized_prompt","") == batch[i]["prompt"]
        for i, r in enumerate(results)
    )

    # ===== 显示结果 =====
    st.markdown("---")
    st.markdown(f"## 📊 结果 ({len(results)} 条)")

    # 概览指标
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("句子", len(result.sentences))
    col_m2.metric("场景", result.total_scenes)
    col_m3.metric("角色",
        len(result.script_analysis.get("characters", [])) if result.script_analysis else 0)
    col_m4.metric("总 token",
        sum(r.get("tokens_used", 0) for r in results))

    # LLM 状态提示
    if has_llm_error:
        st.warning("⚠️ LLM 优化失败（API Key 可能失效），当前显示的是模板直出结果或原文")
        for i, r in enumerate(results):
            err = r.get("error")
            if err:
                st.caption(f"  [{i}] 错误: {err[:120]}")
    elif all_template:
        st.info("ℹ️ creative_level 较低时使用模板直出（不调 LLM），输出带有 Midjourney 参数后缀")
    else:
        st.success("✅ LLM 优化生效，每句都已改写为图片 prompt")

    # 逐条展示
    for i, (req, res) in enumerate(zip(batch, results)):
        prompt = res.get("optimized_prompt", "")
        tokens = res.get("tokens_used", 0)
        ms = res.get("duration_ms", 0)

        with st.container():
            bg = "#1a1a2e" if i % 2 == 0 else "#16213e"
            ctx = req.get("context", {})

            st.markdown(f"""
            <div style="background:{bg};padding:16px;border-radius:10px;margin:8px 0">
                <b>🎬 第 {i+1} 镜</b>
                <span style="float:right;color:#909399">{ms:.0f}ms · {tokens} tokens</span><br>
                <b style="color:#e6a23c">原文</b>: {req['prompt']}<br>
                <b style="color:#67c23a">场景</b>: {ctx.get('setting', '—')}
                | <b style="color:#409eff">角色</b>: {ctx.get('character', {}).get('name', '—')}
                | <b style="color:#f56c6c">全部角色</b>: {', '.join(c['name'] for c in ctx.get('character_list', [])) or '—'}<br>
                <b style="color:#b37feb">优化后</b>: {prompt[:200]}{'...' if len(prompt)>200 else ''}
            </div>
            """, unsafe_allow_html=True)

            # 图片预览（占位图，非 AI 生成）
            cols = st.columns(2)
            for ci, size_name, w, h in [(0, "宽屏", 400, 225), (1, "方形", 300, 300)]:
                img_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
                seed = f"{img_hash}-{ci}"
                img_url = f"https://picsum.photos/seed/{seed}/{w}/{h}"
                cols[ci].image(img_url, caption=f"📷 占位预览 #{i+1}（{size_name} — 非 AI 生成，仅示意位置）")

    # 下载
    st.markdown("---")
    export_data = []
    for req, res in zip(batch, results):
        export_data.append({
            "original": req["prompt"],
            "context": req.get("context", {}),
            "optimized": res.get("optimized_prompt", ""),
            "tokens": res.get("tokens_used", 0),
        })
    st.download_button("📥 下载 JSON 结果",
        data=json.dumps(export_data, ensure_ascii=False, indent=2),
        file_name="012_011_e2e_results.json", mime="application/json")

elif run_btn:
    st.warning("请输入文字")
