#!/bin/bash
# 启动 Streamlit 体验工作台
# Usage: bash scripts/run_workbench.sh

set -e
cd "$(dirname "$0")/.."

echo "=== PROJECT-012 Streamlit 体验工作台 ==="
echo ""

# 检查依赖
python -c "import streamlit" 2>/dev/null || {
    echo "❌ streamlit 未安装"
    echo "安装: pip install -e '.[workbench]'"
    exit 1
}

# 启动
streamlit run workbench/app.py --server.port 8501 --server.address 0.0.0.0
