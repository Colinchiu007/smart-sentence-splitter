# 质量门禁指标 (Quality Gates)

| 指标 | 标准 | 检测方式 |
|------|------|---------|
| 测试通过率 | 100% | `python -m pytest tests/` |
| 测试数 | ≥ 100 | `pytest --collect-only` |
| Lint | 零告警 | `ruff check src/` |
| 覆盖率（核心模块） | ≥ 80% | `coverage run -m pytest` |
| 文档审计 | PRD/CHANGELOG/README/AGENTS 同步 | 人工 + `docs/AGENTS.md` 检查清单 |
