# Smart Sentence Splitter — 快速入口

> 智能语义分句引擎 — 打通「文案→分句→字幕→逐句配图→轮播视频」自动化管线
> 完整开发指南见 `docs/AGENTS.md`

## 项目信息

- **版本**: v0.9.10 (2026-06-14)
- **测试**: 353 测试 100% 通过
- **Python**: >=3.11

## 核心架构：三级降级链

```
SmartSentenceSplitter.split(text)
  │
  ├─ 1. 语言检测 (auto/zh/en/ja/mixed)
  ├─ 2. 大文本处理 (>50K chars → 分块递归)
  ├─ 3. 模式映射 (fast/balanced/precise → 配置覆盖)
  │
  └─ 4. TierChain (降级链，从高到低尝试)
       ├── Tier 1: LLM (需 API Key，OpenAI/Ollama/讯飞)
       ├── Tier 2: 语义分割 (TextTiling + jieba/分词规则)
       └── Tier 3: 规则分割 (纯正则，始终可用)
       └── _fallback: 最后兜底
       │
  └─ 5. LengthSegmenter (长度控制: off/A-重切/B-标注)
  └─ 6. SceneSegmenter (场景合并, ~6s/段, 10-50词)
  └─ 7. SubtitleSegmenter (字幕分块, 8-15字/块)
  └─ 8. PostprocessorChain (文言检测等后处理)
  └─ 9. → SplitResult (SentenceBlock[] + SceneSegment[] + SubtitleBlock[])
```

**模式 → min_tier 映射**: fast=T3, balanced=T2, precise=T1(+TextTiling)

## 关键路径

| 文件 | 说明 |
|------|------|
| `02-source/core/pipeline.py` | SmartSentenceSplitter 主编排 |
| `02-source/core/core/tier_chain.py` | 降级链编排 |
| `02-source/core/tiers/tier1_llm.py` | LLM Tier (3 Provider) |
| `02-source/core/tiers/tier3_rule.py` | 规则分割 |
| `02-source/core/languages/zh/splitter.py` | 中文分句器 |
| `02-source/core/languages/en/splitter.py` | 英文分句器 |
| `02-source/core/languages/ja/splitter.py` | 日文分句器 |
| `02-source/api/rest_api.py` | FastAPI |
| `02-source/api/mcp_server.py` | MCP Server |
| `02-source/workbench/app.py` | Streamlit 工作台 |

## 快速命令

```bash
# 安装（先核心，再加 extras）
pip install -e .
pip install -e ".[semantic]"   # 含 jieba（中文分词必需）
pip install -e ".[all]"        # 全量（建议开发环境用）

# 全部测试
pytest tests/ -v

# 启动 REST API
uvicorn splitter.api.rest_api:app --reload --port 8002

# 启动 Streamlit 工作台
streamlit run 02-source/workbench/app.py

# CLI 测试
sentence-splitter -i some_file.txt --language zh

# MCP Server
python -m splitter.api.mcp_server
```

## 重要约定

1. **不绕过 TierChain** — 不要直接调用具体 splitter
2. **基础接口不改** — `BaseSentenceSplitter.split()` 签名不可变
3. **抽象接口不改** — `BaseTokenizer.tokenize()` 签名不可变
4. **Postprocessor 失败不影响主流程** — chain 内部有 try/except 保护
5. **新增语言** → 在 `languages/<lang>/` 创建 splitter/tokenizer → 注册到 `LanguageRouter` → `pipeline.py` 实例化

## 文档索引

- [docs/AGENTS.md](docs/AGENTS.md) — 完整开发指南（新增模块/Postprocessor/长度策略等 SOP）
- [01-docs/ARCHITECTURE.md](01-docs/ARCHITECTURE.md) — 架构设计
- [01-docs/PRD.md](01-docs/PRD.md) — 产品需求
- [01-docs/CHANGELOG.md](01-docs/CHANGELOG.md) — 更新日志
