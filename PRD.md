# PROJECT-012 — 智能语义分句引擎 · 产品需求文档 (PRD)

> 版本: 0.9.2 | 更新: 2026-06-14 | 状态: 🟢 活跃开发

## 1. 产品定位

### 一句话描述
**按语义完整性和字数约束自动切割文本，输出结构化分句数据** — 字幕生成 / 逐句生图 / 视频合成的统一 NLP 入口。

### 目标用户
- **内容创作者**: 短视频字幕、直播台词、口播稿切句
- **AI 生成管线**: Midjourney / Stable Diffusion 逐句生图管线
- **影视工业**: 剧本分镜、字幕生成、项目管理
- **开发者**: 嵌入式文本预处理 (LLM prompt 拆分、翻译断句)

### 核心价值
| 维度 | 价值 |
|------|------|
| 🧠 智能 | 3 级降级链 (LLM → TextTiling → 规则)，无密钥也能用 |
| 📏 可控 | 字数上限/下限/A 重切/B 标尺，输出长度精确到字 |
| 🎬 结构化 | 句子 → 场景 → 字幕 3 层结构 + 角色/场景/情绪元数据 |
| 🪶 轻量 | 零依赖核心 (仅 pydantic + PyYAML)，按需安装 jieba/streamlit/fastapi |
| 🔌 可接入 | REST API / CLI / MCP Server / Streamlit 四种集成方式 |

---

## 2. 功能清单 (按版本)

### v0.1~v0.3 — 分句引擎筑基

| 功能 | 说明 |
|------|------|
| 中文分句 | 按句号/问号/叹号/分号/换行分割，保护引号/括号 |
| 英文分句 | 按句号/问号/叹号分割，保护缩写 (Mr./Dr./U.S.) |
| 中英自动检测 | Unicode 识码 + jieba 启发式判断 |
| 3 级降级链 | LLM (Tier 1) → TextTiling+jieba (Tier 2) → 规则 (Tier 3) |
| jieba 分词 | AC 自动机用户词典 (FoolNLTK/LAC 复用) |
| 3 种模式 | fast (仅规则) / balanced (语义+规则) / precise (LLM 优先) |
| DAG+DP | 多策略分句结果加权合并 |

### v0.4 — LLM 增强

| 功能 | 说明 |
|------|------|
| OpenAI Provider | 调用 GPT 模型执行智能分句 |
| 讯飞 MAAS Provider | 调用讯飞大模型 |
| Ollama Provider | 本地 LLM |
| prompt 模板 | role/system/user 三段式 + 可配置 tokens 上限 |
| LLM Tier 开关 | enable_llm=False 时跳过 LLM，完全离线运行 |

### v0.5 — 基础设施

| 功能 | 说明 |
|------|------|
| FastAPI REST API | POST /split, GET /health, GET /config, GET /version |
| Streamlit 工作台 | GUI 界面，实时分句 + JSON 下载 |
| CLI 命令行 | sentence-splitter 命令，支持管道输入 |
| config loader | YAML 配置文件热加载 |
| Postprocessor 链 | EraPostprocessor / CustomMergingProcessor 可插拔 |
| 语言路由 | LanguageRouter 自动路由中文/英文/混合 |
| 3 个 SentenceBlock | SentenceBlock (句子) / SceneSegment (场景) / SubtitleBlock (字幕) |
| 时长计算 | 按字数比例分配场景时长 |

### v0.6 — 字数控制

| 功能 | 说明 |
|------|------|
| A 模式 (重切) | 按 max_chars 重新切割，标点优先 + 配对引号保护 (v0.9.2) |
| B 模式 (标尺) | 只标记 too_long / too_short，不改变原文分句 |
| off 模式 (透传) | 完全忽略长度约束 |
| min_chars | 最短块长度限制 (默认 3) |
| 3 级标点优先级 | 强分隔 (。！？；) > 弱分隔 (，、) > 强制切 (无标点时) |

### v0.7 — 剧本分析 + 分镜

| 功能 | 说明 |
|------|------|
| ScriptAnalyzer | 角色提取 + 场景提取 + 梗概生成 |
| 角色提取 | LOCATION_TRANSITION_VERBS 信号词 + bad_starts 过滤 |
| 场景提取 | LOCATION_SUFFIXES 地点后缀词 + Unicode 正则匹配 |
| StoryboardExporter | 分镜 JSON 输出 (角色/场景/情绪/时长) |
| SceneSegment 增强 | characters / setting / mood 字段自动填充 |
| 情绪启发式 | 关键词映射 (开心→happy, 悲伤→sad 等) |

### v0.8 — 字幕 + 提示词桥接

| 功能 | 说明 |
|------|------|
| SRT 导出 | 标准字幕格式，跨场景时间累加 |
| ASS 导出 | 完整头部 (Script Info + V4+ Styles + Events) + 角色名 |
| SubtitleSegmenter | 8-15 字字幕块，复用 LengthSegmenter 配对引号保护 (v0.9.2) |
| PromptEngineClient | PROJECT-011 HTTP 客户端 |
| /v1/optimize | 单条 prompt 优化 |
| /v1/optimize/batch | 批量 prompt 优化 (v0.9.1 新增 context 注入) |
| 平台映射 | 中→midjourney, 英→stable_diffusion, 日→jimeng |

### v0.9 — 体验增强

| 功能 | 说明 |
|------|------|
| 工作台四合一 | 分句 / 字幕 (SRT+ASS) / 分镜 / 提示词 4 标签页 |
| Context 注入 | synopsis / character_list / character / setting 传入 PROJECT-011 |
| 配对引号保护 | 《》「」（）[] 【】 {} "" '' 不被 A 模式截断 |
| 场景检测修复 | 删除单字后缀 (后/外/上/家)，加 Unicode 边界后顾 |

### 未来规划 (v1.0+)

| 功能 | 优先级 | 状态 |
|------|--------|------|
| REST API 批量接口 (POST /split/batch) | P1 | ✅ v0.9.6 |
| 多语言扩展 (日/韩/法) | P1 | 🔵 v0.9.9 开发中 |
| 语义段落检测优化 | P1 | 📋 |
| 性能基线扩展 (1MB) | P2 | ✅ v0.9.7 |
| Fuzz 测试防崩溃 | P2 | ✅ v0.9.7 |
| 项目管理面板 (多剧本) | P2 | 🔵 v0.9.8 开发中 |
| 实时字幕流 | P2 | 📋 |
| 插件系统 (自定义 exporter) | P3 | 📋 |

---

## 3. 非功能需求

### 性能
| 场景 | 指标 | 当前实测 |
|------|------|----------|
| 50 字以内 | < 100ms | 15ms |
| 1KB 中文 | < 500ms | 56ms |
| 10KB 中文 | < 3s | 225ms |
| 25,000 字 | < 2s | 200ms |
| 吞吐量 | > 10 万字/秒 | 12.7 万字/秒 |
| 冷启动 | 含 jieba 加载 < 2s | ~1s |

### 兼容性
- Python 3.11+
- 零依赖核心: 仅 pydantic + PyYAML
- 可选: jieba, streamlit, fastapi, uvicorn, requests

### 部署
- pip install -e . (核心) / .[semantic] (含 jieba) / .[all] (全量)
- REST API: `uvicorn splitter.api.rest_api:app --port 8000`
- Streamlit GUI: `streamlit run workbench/app.py --server.port 8501`
- MCP Server: `python -m splitter.api.mcp_server`

---

## 4. 数据模型

```
SentenceBlock        SceneSegment           SubtitleBlock
┌────────────┐       ┌────────────┐         ┌────────────┐
│ text       │       │ text       │         │ text       │
│ index      │       │ sentences[]│         │ index      │
│ tier       │       │ characters │         │ start_time │
│ language   │───────│ setting    │─────────│ end_time   │
│ length_sta │       │ mood       │         │ duration   │
│ confident  │       │ est_durati │         │ parent_id  │
│ words      │       │ subtitles  │         └────────────┘
│ pos_tags   │       └────────────┘
└────────────┘

SplitResult              SplitConfig
┌────────────────┐       ┌────────────────┐
│ sentences[]    │       │ language       │
│ scenes[]       │       │ mode           │
│ tier_used      │       │ min_tier       │
│ language       │       │ enable_era     │
│ total_scenes   │       │ enable_llm     │
│ script_analysis│       │ enable_script  │
│ config_snap    │       │ length:{A/B/off, min, max} │
└────────────────┘       └────────────────┘
```

---

## 5. 竞品对比

| 维度 | PROJECT-012 | spaCy | Jieba 分句 | LLM-only |
|------|-------------|-------|------------|----------|
| 语义分句 | ✅ 3-tier | ✅ | ❌ | ✅ |
| 字数控制 | ✅ A/B/off | ❌ | ❌ | ❌ |
| 字数保护 | ✅ | ❌ | ❌ | ❌ |
| 剧本分析 | ✅ | ⚠️ NER | ❌ | ✅ |
| 场景/情绪 | ✅ | ❌ | ❌ | ⚠️ 需 prompt |
| 字幕导出 | ✅ SRT/ASS | ❌ | ❌ | ❌ |
| 桥接生图管线 | ✅ PROJECT-011 | ❌ | ❌ | ⚠️ |
| 离线可用 | ✅ | ✅ | ✅ | ❌ |
| 安装体积 | < 1MB | ~500MB | ~10MB | ~10GB+ |

---

## 6. 集成关系

```
PROJECT-012 (智能语义分句引擎)
         │
         ├── PROJECT-011 (prompt-engine)  ← POST /v1/optimize/batch
         │     └── Midjourney / Stable Diffusion / 即梦
         │
         ├── Streamlit → 人工审核 (字幕/分镜/提示词预览)
         │
         └── REST API → CI/CD 管线
               └── MCP Server → AI Agent 工具调用
```

---

## 7. 版本号约定

遵循语义化版本:
- **major**: 不兼容的 API 改动 (目前 0.x 表示 pre-release)
- **minor**: 向下兼容的功能新增 (v0.6→v0.7 字数控制→剧本分析)
- **patch**: 向下兼容的 bug 修复 (v0.9.1→v0.9.2)
- tag 格式: `v0.9.2`

当前: 15 个版本, 324 测试, 100% 通过
