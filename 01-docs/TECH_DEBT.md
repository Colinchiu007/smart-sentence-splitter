# 技术债务登记（Tech Debt Register）

| # | 债务项 | 影响范围 | 复杂度 | 优先级 | 创建日期 | 状态 |
|---|--------|---------|--------|-------|---------|------|
| TD-001 | 中文/英文 chain 在 mode=fast 时 LLM 仍被构造（虽然不可用） | pipeline.py | 低 | P2 | 2026-06-14 | 待修复 |
| TD-002 | TextTiling 短文本早退逻辑依赖 min_text_length 而非 token | texttiling/splitter.py | 低 | P2 | 2026-06-14 | 待修复 |
| TD-003 | ChineseSplitter EOS 窗口检测规则可扩展 | languages/zh/splitter.py | 低 | P3 | 2026-06-14 | 待修复 |
| TD-004 | config/splitter.yaml 文档注释不够完整 | config/splitter.yaml | 低 | P3 | 2026-06-14 | 待修复 |
| TD-005 | 无端到端集成测试（CLI+REST+MCP 联合测试） | tests/ | 中 | P2 | 2026-06-14 | 待修复 |
| TD-006 | 新 contributor 导览缺三块：pipeline 9 步序号链图、`02-source/` 路径说明表、安装/启动命令速查（extras/CLI/MCP）——结构信息散在 ARCH-001 与 USAGE_GUIDE，无一张集中导览 | 01-docs/AGENTS.md / 01-docs/ARCH-001-architecture.md | 低 | P3 | 2026-10-24 | 待修复 |
| TD-007 | `docs/AGENTS.md` 与 `01-docs/AGENTS.md` 同 blob 双份并存（各 179 行），疑为 `docs/` → `01-docs/` 迁移残留；外部链接两种路径都可达，删任一份需先改引用 | 01-docs/ 与 docs/ | 低 | P3 | 2026-10-24 | 待修复 |
