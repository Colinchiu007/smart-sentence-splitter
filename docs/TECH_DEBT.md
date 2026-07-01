# 技术债务登记（Tech Debt Register）

| # | 债务项 | 影响范围 | 复杂度 | 优先级 | 创建日期 | 状态 |
|---|--------|---------|--------|-------|---------|------|
| TD-001 | 中文/英文 chain 在 mode=fast 时 LLM 仍被构造（虽然不可用） | pipeline.py | 低 | P2 | 2026-06-14 | 待修复 |
| TD-002 | TextTiling 短文本早退逻辑依赖 min_text_length 而非 token | texttiling/splitter.py | 低 | P2 | 2026-06-14 | 待修复 |
| TD-003 | ChineseSplitter EOS 窗口检测规则可扩展 | languages/zh/splitter.py | 低 | P3 | 2026-06-14 | 待修复 |
| TD-004 | config/splitter.yaml 文档注释不够完整 | config/splitter.yaml | 低 | P3 | 2026-06-14 | 待修复 |
| TD-005 | 无端到端集成测试（CLI+REST+MCP 联合测试） | tests/ | 中 | P2 | 2026-06-14 | 待修复 |
