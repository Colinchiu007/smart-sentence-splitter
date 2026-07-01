# PROJECT-012 — 语义分句引擎 PRD

> **版本**: v0.10.0 | **最后更新**: 2026-06-30  
> **产品定位**: 输入长文，按语义完整性 + 字数/时长约束自动切割为结构化句子序列，输出可用于字幕生成、逐句生图、视频合成的标准化分句数据  
> **核心价值**: 从「标点符号切分」升级到「语义理解级切句」，打通「文案→分句→字幕→逐句配图→轮播视频」的自动化管线  
> **状态**: ✅ 稳定运营（365 测试全绿）

---

## 一、产品概述

**SmartSentenceSplitter** 是一站式语义分句引擎，面向内容创作者和开发者提供从原始文本到结构化分句/场景/字幕/提示词的完整转换能力。

| 维度 | 说明 |
|------|------|
| **输入** | 任意长度文本（单次 ≤200K 字，超长自动分块递归处理） |
| **输出** | 标准化 JSON：sentences / scenes / subtitles / script_analysis |
| **多语言** | 中文（jieba 增强 + AC 自动机）、英文（缩写保护 + 引号保护）、日文（配对引号）、中英混排路由 |
| **API 形态** | Python SDK + FastAPI REST + CLI + MCP Server + Streamlit 工作台 |
| **依赖** | 纯规则模式零外部依赖；可选 jieba / LLM / langdetect |

---

## 二、目标用户

| 用户类型 | 特征 | 调用方式 |
|---------|------|---------|
| **内容创作者（终端）** | 用此引擎做视频的创作者 | Streamlit 工作台（Web UI） |
| **开发者** | 集成到自己的 Web/App/桌面应用 | REST API / SDK / MCP |
| **AI 工作流用户** | ComfyUI / n8n 等工作流工具 | MCP Server / CLI |

---

## 三、产品架构

```
输入文本（长文/文章）
    │
    ▼
┌─ Layer 1: 句子级 — 分句引擎 ──────────────────────────────────┐
│  LanguageRouter ──→ zh/zh_chain ──→ TierChain                       │
│                        │               ├─ Tier 1: LLM (OpenAI/讯飞/Ollama) │
│                   jieba + AC      ├─ Tier 2: jieba + TextTiling        │
│                   + TextTiling    └─ Tier 3: 纯规则（零依赖 fallback）       │
│                        │                                               │
│                   en/en_chain ──→ 缩写保护 + 标点分句                    │
│                   ja/ja_chain ──→ 配对引号 + 标点分句（v0.9.9）            │
└────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ Layer 1.5: 字数控制 ───────────────────────────────────────────┐
│  LengthSegmenter                                                     │
│    A: 按 max_chars 重切（配对引号保护）                                │
│    B: 标尺标记（too_long / ok / too_short）                           │
│    off: 透传                                                         │
└────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ Layer 2: 场景级 — 场景分割 + 剧本分析 ──────────────────────────┐
│  SceneSegmenter: 按 is_topic_boundary + 地点信号分组                 │
│  ScriptAnalyzer: 角色提取 / 场景提取 / 梗概（v0.7）                    │
│  → SceneSegment.characters / setting / mood 注入                    │
└────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ Layer 3: 字幕级 — 字幕分割 + 输出桥接 ─────────────────────────┐
│  SubtitleSegmenter: 8-15字字幕块 + 时长分配                           │
│  SubtitleExporter: SRT + ASS 导出                                    │
│  StoryboardExporter: 分镜 JSON                                       │
│  PromptEngineExporter: PROJECT-011 桥接（含 context 注入 v0.9.1）     │
└────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ Postprocessor 链 ──────────────────────────────────────────────┐
│  EraPostprocessor (时代标签: ancient / modern / mixed)              │
│  CustomMergingProcessor (用户词典合并)                                │
└────────────────────────────────────────────────────────────────────┘
    │
    ▼
SplitResult {sentences, scenes, tier_used, language, script_analysis}
```

### 三级降级链（核心创新）

```
              ┌──────────────┐
              │  输入文本      │
              └──────┬───────┘
                     │
            ┌────────▼────────┐
            │ Tier 1: LLM     │ ← 精度最高，成本最高
            │ API 可用时      │   3 provider: OpenAI/讯飞/Ollama
            └────────┬────────┘
                     │ 超时/限流/Key 未配置
            ┌────────▼────────┐
            │ Tier 2: 语义    │ ← jieba + TextTiling + 规则
            │ 无外部依赖      │   无监督主题分割
            └────────┬────────┘
                     │ 文本过短/效果不佳
            ┌────────▼────────┐
            │ Tier 3: 规则    │ ← 零依赖，精度最低但稳定
            │ 标点+启发式     │   中英文缩写/引号/书名号保护
            └────────┬────────┘
                     │
            ┌────────▼────────┐
            │ 字数控制        │ ← A/B/off 三模式
            │ 场景+字幕分割   │ ← 下游处理
            └─────────────────┘
```

### 三大模式

| 模式 | min_tier | 适用场景 |
|------|----------|---------|
| **fast** | 3（仅规则）| 超大批量、零延迟要求 |
| **balanced** | 2（语义+规则）| 默认，兼顾速度与质量 |
| **precise** | 1（LLM）| 最高精度，自动启用 TextTiling |

---

## 四、功能状态

### ✅ 核心功能（全部已完成）

| 编号 | 功能 | 版本 | 测试覆盖 |
|------|------|------|---------|
| F-01 | **规则分句器** — 基于标点+启发式的基础分句，中英文缩写/引号/书名号/括号保护 | v0.1.0 | ✅ 39 tests |
| F-02 | **jieba 增强分句器** — jieba 分词+词性标注辅助语义边界判定，AC 自动机用户词典 | v0.2.0 | ✅ 集成测试 |
| F-03 | **TextTiling 主题分割** — 句级滑动窗口余弦相似度 + 局部极大值，语言无关 | v0.2.0 | ✅ 14 tests |
| F-04 | **LLM 深度分句** — 3 provider (OpenAI/讯飞/Ollama)，3 层响应解析容错 | v0.4.0 | ✅ 25 tests |
| F-05 | **三级退化链** — LLM→语义→规则自动降级，可配置 min_tier | v0.3.0 | ✅ 集成测试 |
| F-06 | **场景级分割** — 按 topic_boundary + 地点信号词分组，优先语义边界 | v0.1.0 | ✅ 集成测试 |
| F-07 | **字幕级分割** — 8-15字/块可配，标点优先级矩阵 | v0.1.0 | ✅ 集成测试 |
| F-08 | **时代检测集成** — 三层加权关键词评分，古代/现代/混合判定 | v0.3.0 | ✅ 集成测试 |
| F-09 | **输出标准化** — JSON 含 sentences/scenes/subtitles/era_info/script_analysis | v0.1.0 | ✅ 全量 |
| F-10 | **体验工作台** — Streamlit 4-tab (分句/字幕/分镜/提示词) + 多剧本管理 + 对比 | v0.5.0 | ✅ 7 tests |
| F-11 | **REST API** — FastAPI：GET /health, POST /v1/split, POST /v1/split/batch, POST /v1/split/stream (SSE) | v0.5.0 | ✅ 集成测试 |
| F-12 | **CLI 工具** — sentence-splitter -i input.txt -o output.json | v0.5.0 | ✅ |
| F-13 | **MCP Server** — MCP 协议工具: smart_splitter, text_to_sentences | v0.5.1 | ✅ |
| F-14 | **SRT/ASS 字幕导出** — SubtitleExporter 支持两种格式 + 统计 | v0.8.0 | ✅ 10 tests |
| F-15 | **生图提示词生成** — PromptEngineExporter 桥接 PROJECT-011，含 context 注入 | v0.6.1 | ✅ 15 tests |

### ✅ 超越原始 PRD 的附加功能

| 功能 | 版本 | 说明 |
|------|------|------|
| **剧本分析** (ScriptAnalyzer) | v0.7.0 | 角色提取 + 场景识别 + 梗概生成 + 情绪推断 |
| **分镜输出** (StoryboardExporter) | v0.7.0 | 含角色/场景/氛围/时长 的分镜 JSON |
| **字数控制策略** (A/B/off) | v0.6.0 | A 模式智能重切、B 模式标尺标记、off 透传 |
| **配对引号保护** | v0.9.2 | A 模式重切时锁定配对引号内外 |
| **批量 API** (POST /v1/split/batch) | v0.9.6 | 一次请求处理多段文本 |
| **日语分句** (JapaneseSplitter) | v0.9.9 | 配对引号保护 + TierChain 集成 |
| **多剧本管理 + 对比模式** | v0.9.8 | Workbench 侧栏保存/切换/对比 |
| **语义段落检测** (句级 TextTiling) | v0.9.10 | 句级滑动窗口 + 主题边界感知场景分割 |
| **SSE 流式分句** (POST /v1/split/stream) | v0.10.0 | 大文本分块进度推送 + 低延迟流式响应 |
| **PROJECT-011 HTTP Client** | v0.8.0 | 优化请求批量发送 + 图片预览 |
| **性能基线 + Fuzz 测试** | v0.9.7 | 4 级性能基线 + 17 极端场景 fuzz |
| **上下文注入** (context) | v0.9.1 | 角色/场景一致性注入优化请求 |

---

## 五、数据模型

```python
@dataclass
class SentenceBlock:
    text: str
    index: int
    tier: str                    # llm / texttiling / tier3_rule
    language: str
    words: List[str]
    pos_tags: List[str]
    confidence: float
    is_topic_boundary: bool
    topic_depth_score: float
    length_status: str           # ok / too_long / too_short
    length_strategy_applied: str # A / B / off

@dataclass
class EraInfo:
    era: str                     # modern / ancient / mixed
    confidence: float
    keywords: List[str]

@dataclass
class SceneSegment:
    segment_id: int
    text: str
    sentences: List[SentenceBlock]
    characters: List[str]        # 剧本分析(v0.7)
    setting: str                 # 剧本分析(v0.7)
    mood: str                    # 情绪推断(v0.7)
    estimated_duration: float
    target_words: int
    subtitles: List[SubtitleBlock]

@dataclass
class SubtitleBlock:
    index: int
    text: str
    start_time: float
    end_time: float
    duration: float
    parent_id: int

@dataclass
class SplitResult:
    sentences: List[SentenceBlock]
    scenes: List[SceneSegment]
    tier_used: str
    language: str
    total_scenes: int
    total_duration: float
    script_analysis: Optional[Dict]
    config_snapshot: Dict
```

---

## 六、测试矩阵

| 测试集 | 覆盖内容 | 数量 |
|--------|---------|------|
| **单元测试** | 中/英/日 splitter、TierChain、LLM provider、字数控制、剧本分析、时代检测、TextTiling、字幕导出、提示词桥接、MCP Server | 282 |
| **集成测试** | 端到端管线、REST API、SSE 流式、PROJECT-011 client、工作台、v3 postprocessor、v7 剧本分析 | 72 |
| **性能基线** | 1KB < 20ms / 10KB < 100ms / 100KB < 10s / 1MB < 60s | 4 test levels |
| **Fuzz 测试** | 随机中文/英文/混排、17 极端场景 | 5 test files |
| **合计** | **348 passed + 9 skipped** ✅ | — |

### 关键验收场景

| 场景 | 验收标准 |
|------|---------|
| 中英文混合分句 | 输入 "Hello world。这是一段测试text。" → 正确分2句 |
| 引号内句号不误判 | "他说：「好的。」然后走了。" → 不误切在引号内句号 |
| 缩写保护 | "Dr. Wang 和 Mr. Li" → 不在缩写点处切 |
| 降级链 | 模拟 LLM 超时 → 自动降级到 TextTiling → 降级到规则 |
| 日语配对引号 | 「こんにちは。今日はいい天気ですね。」→ 不切引号内句点 |
| 长篇大文本 | 200000+ 字 → 自动按标点分块递归处理 |
| 极端输入 fuzz | 空/纯标点/超长词/纯重复 → 不抛异常 |

---

## 七、非功能需求

| 维度 | 要求 | 实测 |
|------|------|------|
| **性能** | 10K 字规则分句 < 1s | ✅ ~50ms |
| **性能** | 100KB < 10s | ✅ ~418ms |
| **性能** | 1MB < 60s | ✅ ~5.8s |
| **最大输入** | 单次 200K 字（超长自动分块递归） | ✅ |
| **零依赖模式** | 纯规则分句器零外部依赖 | ✅ |
| **安装体积** | 核心库 < 5MB（不含 jieba 词典） | ✅ |
| **API 形态** | Python SDK + REST API + CLI + MCP Server + Workbench | ✅ |
| **可配置性** | 全部参数 YAML 可配，支持 mode/fast/balanced/precise | ✅ |

---

## 八、配置体系

```yaml
# 核心配置
language: "auto"                # auto / zh / en
mode: "balanced"                # fast / balanced / precise
min_tier: 2                     # 1=LLM, 2=语义+规则, 3=仅规则
max_input_length: 200000        # 大文本截断阈值（>200K 时分块递归处理）

# 功能开关
enable_era: false
enable_topic_segmentation: false
enable_script_analysis: false
enable_llm: false

# 字数控制
length:
  strategy: "B"                 # A=重切, B=标尺, off=透传
  min_chars: 3
  max_chars: 15

# LLM Tier 配置
llm:
  provider: "openai"            # openai / xfyun / ollama
  model: "gpt-4o-mini"
  max_tokens: 300
  temperature: 0.0
```

---

## 九、迭代历史

| 版本 | 日期 | 核心变更 |
|------|------|---------|
| **v0.1.0** | 2026-06-XX | 初始发布：规则分句器 + 场景/字幕分割 |
| **v0.2.0** | 2026-06-XX | TextTiling 主题分割 + 竞品复用 (5项) |
| **v0.3.0** | 2026-06-XX | 三级退化链 (F1-F7) + jieba 增强 + 时代检测集成 |
| **v0.4.0** | 2026-06-XX | LLM Tier 完整实现 (OpenAI/讯飞/Ollama) |
| **v0.5.0** | 2026-06-XX | REST API + Streamlit 工作台 + 真 LLM 测试 |
| **v0.5.1** | 2026-06-XX | MCP Server + 缺陷修复 |
| **v0.6.0** | 2026-06-XX | 字数控制策略 (A/B/off) |
| **v0.6.1** | 2026-06-XX | PROJECT-011 exporter 桥接 |
| **v0.7.0** | 2026-06-XX | 剧本分析 (角色/场景/梗概) + 分镜增强 |
| **v0.7.1** | 2026-06-XX | pipeline 集成 ScriptAnalyzer |
| **v0.8.0** | 2026-06-XX | SRT/ASS 字幕导出 + PROJECT-011 HTTP client |
| **v0.8.1** | 2026-06-XX | 端到端实测 + 平台名修正 |
| **v0.8.2** | 2026-06-XX | 性能基准 + 基线测试 |
| **v0.8.3** | 2026-06-XX | CI 修复 + 验证脚本 |
| **v0.9.0** | 2026-06-XX | 工作台四合一 (分句/字幕/分镜/提示词) |
| **v0.9.1** | 2026-06-XX | 上下文 (context) 注入 |
| **v0.9.2** | 2026-06-XX | A 模式配对引号保护 |
| **v0.9.5** | 2026-06-14 | 脚本分析角色提取增强 + 端到端示例 |
| **v0.9.6** | 2026-06-14 | REST API 批量接口 POST /v1/split/batch |
| **v0.9.7** | 2026-06-14 | 性能基线扩展至 1MB + Fuzz 测试 |
| **v0.9.8** | 2026-06-14 | 多剧本管理面板 + 对比功能 |
| **v0.9.9** | 2026-06-14 | 日语分句支持 (JapaneseSplitter) |
| **v0.9.10** | 2026-06-14 | 语义段落检测优化 (句级 TextTiling + 主题边界感知场景分割) |
| **v0.10.0** | 2026-06-30 | 大文本分块改进 (200K) + SSE 流式分句端点 POST /v1/split/stream |

> 注：v0.9.3-v0.9.4 为版本号同步和 CI 修复迭代。

---

## 十、集成接口

### REST API (FastAPI)

```
GET  /health              → {"status": "ok", "version": "..."}
GET  /capabilities        → 动态能力声明（tiers/languages/modes）
GET  /v1/info             → 运行时配置信息
POST /v1/split            → 单文本分句
POST /v1/split/batch      → 多文本批量分句 (v0.9.6)
POST /v1/split/stream      → SSE 流式分句 (v0.10.0)
```

### CLI

```bash
sentence-splitter -i input.txt -o output.json [--language auto] [--enable-llm]
```

### MCP Server

```bash
python -m splitter.api.mcp_server
# 工具: smart_splitter, text_to_sentences
```

### Streamlit 工作台

```bash
streamlit run workbench/app.py --server.port 8501
# 4 标签页: 分句 / 字幕 / 分镜 / 提示词
```

### Python SDK

```python
from splitter import SmartSentenceSplitter
splitter = SmartSentenceSplitter({"mode": "balanced"})
result = splitter.split("长文本...")
result.to_dict() → {"sentences": [...], "scenes": [...]}
```

---

## 十一、技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.11+ | jieba 生态，与现有代码栈一致 |
| 分词 | jieba 0.42+ (zh) / 空白分词 (en) | 成熟中文分词，词性标注+NER |
| 主题分割 | TextTiling（自实现） | 无监督，零外部依赖，句级窗口 |
| Web 框架 | FastAPI + Streamlit | REST + 可视化工作台 |
| LLM 分句 | 接口抽象（3 provider） | 不绑定供应商，OpenAI 协议统一 |
| 配置 | YAML | 继承现有 config.yaml 设计 |

---

## 十二、依赖关系

| 依赖 | 类别 | 用途 |
|------|------|------|
| pydantic>=2.0 | 核心 | 数据模型验证 |
| PyYAML>=6.0 | 核心 | 配置加载 |
| jieba>=0.42.1 | optional[semantic] | 中文分词 |
| fastapi>=0.110 | optional[api] | REST API |
| streamlit>=1.30 | optional[workbench] | 体验工作台 |
| httpx>=0.27 | optional[llm] | LLM Provider HTTP 调用 |
| langdetect>=1.0.9 | optional[langdetect] | 语言自动检测 |
| mcp>=0.9 | optional[mcp] | MCP Server |

---

## 十三、后续规划（Beyond v0.9.10）

| 方向 | 优先级 | 目标版本 |
|------|--------|---------|
| 流式分句（增量处理 >200K 字）| ✅ | v0.10.0（SSE） |
| 分布式并行分句（多文本并发）| P2 | v1.0 |
| ComfyUI 节点 | P3 | v1.x |
| 长文本 >1MB 流式传输 + WebSocket | P3 | v1.x |
| 自动语言模型选择（按文本复杂度和成本）| P3 | v1.x |
| ThemeFactory 集成（样式化字幕输出）| P3 | v1.x |

---

*本文档由自动化审计生成（2026-06-29），同步代码库 v0.9.10 实际状态。原始 PRD (v0.2.0) 见 docs/PM-PRD-v0.2.md。*
