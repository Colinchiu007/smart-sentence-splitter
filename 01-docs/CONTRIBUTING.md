# 贡献指南（Contributing）

## 分支策略
- `main`: 生产代码, 只接受 PR merge
- `feat/xxx`: 新功能
- `fix/xxx`: Bug 修复
- `docs/xxx`: 文档

## 提交规范
```
<type>(<scope>): <description>
```
类型: feat / fix / docs / refactor / test / chore

## 本地开发
```bash
pip install -e ".[all]"
sentence-splitter -i examples/sample_zh.txt --enable-era
python examples/sdk_usage.py
python -m pytest tests/
```
