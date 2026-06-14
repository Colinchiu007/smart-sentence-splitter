# 故障应急流程 (Incident Response)

Phase 1: 止血（5 分钟）
- 回滚到上一稳定版本
- 确认影响范围

Phase 2: 诊断（30 分钟）
- 查测试输出: `python -m pytest tests/ -v --tb=long`
- 查最近 commit: `git log --oneline -10`
- 复现 + 确定根因

Phase 3: 修复
- 写测试复现 → 找根因 → 修复 → 全量测试

Phase 4: 复盘（24 小时内）
- 更新 CHANGELOG
- 更新 TECH_DEBT.md
- 更新本文件
