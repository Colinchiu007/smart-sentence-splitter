"""Streamlit 体验工作台 - v0.5 新增.

测试工作台 app 能否正确导入（语法、依赖）。
完整 UI 测试需要 streamlit run 启动 + 浏览器交互，超出自动化测试范围。
"""

import sys
from pathlib import Path

# 修正: tests/integration/ → 项目根 = parent.parent.parent
PROJECT_ROOT = Path(__file__).parent.parent.parent


def test_app_file_exists():
    """workbench/app.py 文件存在。"""
    app = PROJECT_ROOT / "workbench" / "app.py"
    assert app.exists()
    assert app.stat().st_size > 1000  # 至少 1KB


def test_app_importable():
    """workbench/app.py 可被 exec 编译（无语法错误）。"""
    app_path = PROJECT_ROOT / "workbench" / "app.py"
    src = app_path.read_text(encoding="utf-8")
    # 编译检查（不执行）
    compile(src, str(app_path), "exec")


def test_startup_script_exists():
    """scripts/run_workbench.sh 存在。"""
    script = PROJECT_ROOT / "scripts" / "run_workbench.sh"
    assert script.exists()
    content = script.read_text(encoding="utf-8")
    assert "streamlit run" in content
    assert "workbench/app.py" in content


def test_app_uses_smart_splitter():
    """workbench/app.py 引用 SmartSentenceSplitter。"""
    app_path = PROJECT_ROOT / "workbench" / "app.py"
    content = app_path.read_text(encoding="utf-8")
    assert "SmartSentenceSplitter" in content
    assert "from splitter import" in content


def test_app_supports_core_features():
    """工作台覆盖核心配置项。"""
    app_path = PROJECT_ROOT / "workbench" / "app.py"
    content = app_path.read_text(encoding="utf-8")
    # 检查关键 UI 元素
    assert "language" in content
    assert "mode" in content
    assert "enable_era" in content
    assert "enable_topic_segmentation" in content
    assert "enable_llm" in content
    # 输出
    assert "JSON" in content
    assert "download_button" in content


def test_app_script_management():
    """工作台支持多剧本管理 (v0.9.8)。"""
    app_path = PROJECT_ROOT / "workbench" / "app.py"
    content = app_path.read_text(encoding="utf-8")
    # 多剧本管理核心元素
    assert "st.session_state" in content
    assert "剧本" in content and ("listbox" in content or "selectbox" in content or "radio" in content)
    assert "保存" in content
    assert "删除" in content or "清空" in content


def test_app_script_comparison():
    """工作台支持多剧本对比 (v0.9.8)。"""
    app_path = PROJECT_ROOT / "workbench" / "app.py"
    content = app_path.read_text(encoding="utf-8")
    # 对比功能
    has_comparison = "对比" in content or "差异" in content or "compare" in content.lower()
    assert has_comparison, "工作台应有对比功能"
