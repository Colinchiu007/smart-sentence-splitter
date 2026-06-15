> 本文件是快速入口。完整版本请参考 `docs/AGENTS.md`。

## 快速命令
```bash
# 全部测试
python -m pytest tests/

# 启动 REST API
uvicorn splitter.api.rest_api:app --reload

# 启动 Streamlit
streamlit run workbench/app.py

# 启动 MCP Server
python -m splitter.api.mcp_server
```

## 关键路径
- `pipeline.py` — SmartSentenceSplitter 主入口
- `tiers/tier1_llm.py` — LLM Tier
- `api/rest_api.py` — FastAPI
- `api/mcp_server.py` — MCP Server

## 版本
v0.9.9 (2026-06-14) — 353 测试 100% 通过
