#!/usr/bin/env bash
# PROJECT-012 构建脚本
# 用法: bash scripts/build.sh

set -e
cd "$(dirname "$0")/.."

echo "=== 安装构建工具 ==="
pip install build --quiet

echo ""
echo "=== 清除旧构建 ==="
rm -rf dist/ build/ *.egg-info

echo ""
echo "=== 构建 wheel + source tarball ==="
python -m build

echo ""
echo "=== 产物 ==="
ls -lh dist/

echo ""
echo "=== 安装验证 ==="
pip install dist/*.whl --force-reinstall --quiet
python -c "from splitter import SmartSentenceSplitter; s=SmartSentenceSplitter(); r=s.split('测试'); print(f'✅ 版本 {r.config_snapshot.get(\"mode\", \"?\")} 可用')"

echo ""
echo "✅ 构建完成: dist/smart_sentence_splitter-*.whl"
