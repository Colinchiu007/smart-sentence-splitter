# PROJECT-012 CHANGELOG

## [0.1.0] - 2026-06-13

### 🎉 首发版本 (Initial Release)

首个可用版本。实现了 PRD v0.2 定义的 P0 核心功能。

### ✨ 新增功能 (Features)

#### 核心引擎
- **F-01 规则分句器** — 基于标点+启发式规则的基础分句，支持中英文
- **F-02 jieba 增强分句器** — 中文分词+词性标注辅助分句
- **F-05 三级降级链** — Tier 1 (LLM) → Tier 2 (TextTiling+jieba) → Tier 3 (规则) 自动降级
- **F-06 场景级分割** — 6秒一段，字数约束，不切句子
- **F-07 字幕级分割** — 8-15字/块，标点优先级矩阵
- **F-08 时代检测** — 古代/现代/混合三层关键词评分（仅中文）
- **F-09 输出标准化** — JSON 含 sentences/scenes/subtitles/era_info

#### 多语言
- **中文 (zh)** — jieba 分词+词性标注，16 个内置缩写
- **英文 (en)** — 零依赖空白分词，35+ 个内置缩写（Mr. Dr. U.S. e.g. etc.）
- **引号对保护** — 「」"" `''` 不在引号内切分
- **省略号处理** — `...` 视为 1 个边界点
- **破折号子句** — `—...—` 包裹的子句
- **语言自动检测** — 启发式 (CJK比例 + ASCII比例 + 假名)

#### API 形态
- **Python SDK** — `from splitter import SmartSentenceSplitter`
- **CLI 工具** — `sentence-splitter -i input.txt -o output.json`
- **配置文件** — YAML + JSON 双向支持，深度合并

### 🏗️ 架构

- 抽象接口：`BaseSentenceSplitter` + `BaseTokenizer`
- 降级链：`TierChain` 编排多个 splitter，按 `is_available()` 自动降级
- 多语言路由：`LanguageRouter` 段落级检测 + 路由
- 主编排：`SmartSentenceSplitter` 一站式入口

### 📊 测试

- 单元测试: **74 个** (5 个测试模块)
- 集成测试: **27 个** (1 个端到端测试模块)
- 端到端: **3 个语言场景** (zh / en / mixed)
- **总计: 101 个测试用例 100% 通过 ✅**

### 📁 文件清单

#### 源码 (src/splitter/)
- `__init__.py` — 主入口 (4KB)
- `pipeline.py` — 主编排 (5KB)
- `core/` — 抽象层
  - `base_splitter.py`, `base_tokenizer.py`, `tier_chain.py`, `language_router.py`
- `languages/zh/` — 中文包
  - `splitter.py`, `tokenizer.py`, `abbreviations.py`
- `languages/en/` — 英文包
  - `splitter.py`, `tokenizer.py`, `abbreviations.py`
- `tiers/tier3_rule.py` — Tier 3 规则
- `scene_subtitle/` — Layer 2 + 3
  - `scene_segmenter.py`, `subtitle_segmenter.py`
- `era/` — 时代检测
  - `detector.py`, `vocab.py`
- `models/` — 数据模型 (5 个 dataclass)
- `utils/` — 配置/序列化/语言检测
- `api/cli.py` — CLI 入口

#### 配置
- `config/splitter.yaml` — 默认配置
- `pyproject.toml` — 项目元数据 + 依赖分组 (核心/semantic/api/cli/workbench/llm/mcp/langdetect/all)

#### 测试
- `tests/unit/` — 74 个单元测试
- `tests/integration/` — 27 个集成测试
- `tests/fixtures/` — 测试数据

#### 示例
- `examples/sdk_usage.py` — SDK 4 个使用场景
- `examples/sample_zh.txt` — 中文示例文本
- `examples/sample_en.txt` — 英文示例文本

#### 文档
- `docs/PRD.md` (16KB) — 产品需求 v0.2
- `docs/ARCH-001-architecture.md` (27KB) — 整体架构
- `docs/CHANGELOG.md` (本文档) — 更新日志
- `docs/AGENTS.md` — AI Agent 开发指南
- `README.md` — 项目主文档

### 🔧 依赖

- 必需: `pydantic>=2.0`, `PyYAML>=6.0`
- 可选:
  - `semantic` 组: `jieba>=0.42.1` (中文增强)
  - `api` 组: `fastapi>=0.110`, `uvicorn>=0.27` (REST API)
  - `workbench` 组: `streamlit>=1.30` (工作台)
  - `llm` 组: `httpx>=0.27`, `openai>=1.0` (LLM Tier)
  - `mcp` 组: `mcp>=0.9` (MCP Server)
  - `langdetect` 组: `langdetect>=1.0.9` (语言检测)
  - `all` 组: 上述全部

### ⚠️ 已知限制 (Known Limitations)

- LLM Tier (Tier 1) 暂未实现，需要时调 `enable_llm: true` 并配置 API key
- 日文 (ja) 暂不支持，P2 迭代
- 时代检测仅对中文生效
- 性能未做压力测试，10K+ 字文本未验证

### 🚀 下一步 (Roadmap)

- v0.2 — TextTiling 主题分割算法（Tier 2 升级）
- v0.3 — LLM Tier 接口 + OpenAI/xfyun 适配
- v0.4 — REST API (FastAPI)
- v0.5 — Streamlit 体验工作台
- v0.6 — SRT/ASS 字幕导出 + 生图提示词生成

---

**版本**: v0.1.0
**发布日期**: 2026-06-13
**作者**: PROJECT-012 Team
**开发模式**: AI 协作 (PM/架构师/开发/QA 角色扮演)
**工作流**: professional-ai-coding-workflow
