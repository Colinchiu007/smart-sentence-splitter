# PROJECT-012 — 架构文档 (ARCHITECTURE.md)

> 版本: 0.9.2 | 更新: 2026-06-14

## 1. 系统架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SmartSentenceSplitter                        │
│                          (pipeline.py)                              │
└─────────────────────────────────────────────────────────────────────┘
         │
         ├── Layer 1: 句子级 — 分句引擎 (Sentence Splitting)
         │    │
         │    ├── LanguageRouter ──→ zh/ChineseSplitter ──→ Tier Chain
         │    │                           │                     │
         │    │                      jieba + AC         Tier 1 (LLM)
         │    │                      + TextTiling        Tier 2 (Semantic)
         │    │                                           Tier 3 (Rule)
         │    └── EnglishSplitter ──→ 缩写保护 + 标点分句
         │
         ├── Layer 2: 场景级 — 场景分割 / 剧本分析 (Scene Grouping)
         │    │
         │    ├── SceneSegmenter     — 按 TextTiling 边界 + 地点信号分组
         │    ├── ScriptAnalyzer     — 角色 / 场景 / 梗概 (v0.7)
         │    └── LengthSegmenter    — A 重切 / B 标尺 / off 透传 (v0.6)
         │
         └── Layer 3: 字幕级 — 字幕导出 (Subtitle/Export)
              │
              ├── SubtitleSegmenter  — 8-15字字幕块 + 时长分配 (v0.8)
              ├── SubtitleExporter   — SRT + ASS 导出
              ├── StoryboardExporter — 分镜 JSON
              └── PromptEngineExporter — PROJECT-011 桥接 (v0.9.1 context)
```

---

## 2. 核心数据流

```
输入文本
    │
    ▼
[1] 多语言检测 (language_detect.py)
    │   auto → Unicode + jieba 启发式
    │   zh/en → 固定路由
    │
    ▼
[2] 大文本兜底 (max_input_length=50,000)
    │   超过 → 按标点分块递归 split
    │
    ▼
[3] 模式映射 (mode → min_tier)
    │   fast → 3 (仅规则)
    │   balanced → 2 (语义+规则) [默认]
    │   precise → 1 (LLM)
    │
    ▼
[4] Tier Chain 分句
    │   Tier 1 → LLM (openai/xfyun/ollama)
    │   Tier 2 → jieba + TextTiling + 规则
    │   Tier 3 → 纯规则 (标点 + 引号保护)
    │   降级: 高 tier 失败 → 自动降级到低 tier
    │   DAG+DP 合并多策略结果
    │
    ▼
[5] 字数控制 (LengthSegmenter)
    │   A: 按 max_chars 重切 (配对引号保护)
    │   B: 标尺标记 (too_long/too_short/ok)
    │   off: 透传
    │
    ▼
[6] 场景分割 (SceneSegmenter)
    │   按 is_topic_boundary + LOCATION_TRANSITION_VERBS 分组
    │
    ▼
[7] 剧本分析 + 场景注入 (ScriptAnalyzer)
    │   角色提取 + 场景提取 + 梗概
    │   → 注入 SceneSegment.characters/setting/mood
    │
    ▼
[8] 字幕分割 (SubtitleSegmenter)
    │   复用 LengthSegmenter A 模式 → 8-15字块
    │   → 分配 start_time/end_time/duration
    │
    ▼
[9] Postprocessor 链
    │   EraPostprocessor (时代标签)
    │   CustomMergingProcessor (自定义合并)
    │
    ▼
SplitResult {sentences, scenes, tier_used, language, script_analysis}
```

---

## 3. 模块详解

### 3.1 分句引擎 (Layer 1)

#### 语言路由
```
language_router.py
  ├── detect_language(text) → "zh" / "en" / "mixed"
  └── 中文 → zh/ChineseSplitter + jieba 增强
      └── 英文 → en/EnglishSplitter + 缩写保护
```

#### Tier Chain (降级链)
```
tier_chain.py
  ├── Tier 1 (LLM): tier1_llm.py
  │   ├── OpenAI Provider     (openai_provider.py)
  │   ├── 讯飞 MAAS Provider  (xfyun_provider.py)
  │   └── Ollama Provider     (ollama_provider.py)
  │
  ├── Tier 2 (Semantic): tiers/tier3_rule.py + texttiling/
  │   ├── jieba 分词 + AC 自动机用户词典
  │   ├── TextTiling 主题分割
  │   └── 规则合并
  │
  └── Tier 3 (Rule): base_splitter.py
      ├── 中文标点分句 + 书名号/引号/括号保护
      └── 英文缩写保护 + 标点分句
```

#### 中文分句逻辑 (languages/zh/splitter.py)
```
split(text)
  ├── 预处理: 换行保护 / 省略号保护 / 书名号保护
  ├── 正则分句: [。！？；\n…] 分割点
  ├── 引号保护: 《》「」（）内外标点不参与分割
  └── 后处理: 短句合并 / 残余空格清理
```

### 3.2 字数控制 (Layer 1.5)

```
length_segmenter.py
  ├── PRIORITY_PUNCTUATION       — 标点优先级表
  ├── PAIRED_QUOTES              — 配对引号保护 (v0.9.2)
  │
  ├── segment(sentences)         — 入口: 对每个 too_long 句子处理
  │   ├── A: _resplit(text)      — 重切
  │   └── B: 标记 length_status  — 不切
  │
  ├── _resplit(text)             — 循环切分
  │   ├── _find_split_position   — 找切分点 (锁定配对引号)
  │   └── _try_paired_quote_split — 引号截断保护 (v0.9.2)
  │
  └── _classify_length           — length_status 分类
```

### 3.3 场景级 (Layer 2)

```
scene_segmenter.py
  ├── segment(sentences)         — 按 topic_boundary 分组
  ├── _should_split_at           — 检查是否需新场景
  │   └── location 信号词检测
  └── SceneSegment ← 合并相邻句子到同一场景

script_analyzer.py
  ├── analyze(text) → {characters, settings, synopsis}
  ├── extract_characters(text)   — 角色提取
  │   LOCATION_TRANSITION_VERBS 行为动词 → 前后主语作为角色
  ├── extract_settings(text)     — 场景提取
  │   LOCATION_SUFFIXES 地点后缀 + Unicode 正则 + 边界保护
  └── _is_valid_location(loc)    — 过滤非地点
      bad_starts: 动词/副词/连词黑名单
```

### 3.4 字幕级 (Layer 3)

```
subtitle_segmenter.py
  ├── segment(scene) → [SubtitleBlock]
  ├── _length_seg._resplit(text) — 复用 LengthSegmenter A 模式
  └── _merge_short(blocks)      — 合并过短首/尾块

subtitle_exporter.py
  ├── to_srt(scenes) → str       — SRT 格式
  ├── to_ass(scenes) → str       — ASS 格式 (含角色名)
  ├── count_subtitles(scenes)    — 统计字幕块数/时长
  └── _time_to_srt / _time_to_ass — 时间戳格式化
```

### 3.5 Exporter (输出桥接)

```
storyboard.py
  ├── StoryboardExporter
  ├── to_storyboard(scenes)      — 分镜 JSON
  └── to_dict()                  — 含角色/场景/情绪/时长

prompt_engine.py
  ├── PromptEngineExporter       — PROJECT-011 桥接
  ├── to_optimize_request(sentence, era, context) — 单条
  ├── to_batch_request(...)      — 批量
  └── from_split_result(result)  — 从 SplitResult 构建

prompt_engine_client.py
  ├── health_check()             — GET /health
  ├── optimize(request)          — POST /v1/optimize
  └── optimize_batch(batch)      — POST /v1/optimize/batch
```

---

## 4. 关键数据结构

```python
class SentenceBlock:
    text: str
    index: int
    tier: str
    language: str
    words: List[str]
    pos_tags: List[str]
    confidence: float
    is_topic_boundary: bool
    topic_depth_score: float
    length_status: str          # "ok" / "too_long" / "too_short"
    length_strategy_applied: str  # "A" / "B" / "off"

class SceneSegment:
    segment_id: int
    text: str
    sentences: List[SentenceBlock]
    characters: List[str]       # v0.7 剧本分析填充
    setting: str                # v0.7 剧本分析填充
    mood: str                   # v0.7 情绪推断
    estimated_duration: float
    subtitles: List[SubtitleBlock]

class SubtitleBlock:
    index: int
    text: str
    start_time: float
    end_time: float
    duration: float
    parent_id: int

class SplitResult:
    sentences: List[SentenceBlock]
    scenes: List[SceneSegment]
    tier_used: str
    language: str
    total_scenes: int
    script_analysis: Optional[Dict]
    config_snapshot: Dict

class OptimizeRequest:           # PROJECT-011 格式
    prompt: str
    platform: str               # midjourney / stable_diffusion / jimeng
    style: str
    creative_level: int
    max_length: int
    negative_prompt: str
    num_candidates: int
    auto_detect_style: bool
    context: Optional[Dict]     # v0.9.1: synopsis / character / setting / character_list
```

---

## 5. 配置体系

```yaml
# splitter/config.yaml (默认值)
language: "auto"                # auto / zh / en
mode: "balanced"                # fast / balanced / precise
min_tier: 2                     # 1=LLM, 2=语义+规则, 3=仅规则

enable_era: false               # 时代检测
enable_topic_segmentation: false  # TextTiling 主题分割
enable_script_analysis: false   # 剧本分析 (角色/场景)
enable_llm: false               # LLM Tier

length:
  strategy: "B"                 # A=重切, B=标尺, off=透传
  min_chars: 3                  # 最短块
  max_chars: 15                 # 最长块
  prefer_punctuation: true      # 优先标点切
  warning_on_violation: true    # 超长/超短时标记

llm:
  provider: "openai"            # openai / xfyun / ollama
  model: "gpt-4o-mini"
  max_tokens: 300
  temperature: 0.1

max_input_length: 50000         # 大文本分块阈值
```

---

## 6. 集成接口

### REST API (FastAPI)
```
GET  /health              → {"status": "ok", "version": "0.9.6"}
GET  /version             → {"version": "0.9.6", "build": "..."}
GET  /config              → 当前配置
POST /split               → SplitResult JSON (单文本)
POST /split/batch         → {"results": [SplitResult, ...]} (多文本批量, v0.9.6)
```

### CLI
```bash
sentence-splitter -i input.txt -o output.json [--language auto]
```

### MCP Server
```bash
python -m splitter.api.mcp_server
# → MCP 工具: smart_splitter / text_to_sentences
```

### Streamlit 工作台
```bash
streamlit run workbench/app.py --server.port 8501
# → 4 标签页: 分句/字幕/分镜/提示词
```

### PROJECT-011 桥接
```python
from splitter.exporter.prompt_engine import PromptEngineExporter
exporter = PromptEngineExporter()
batch = exporter.from_split_result(result)
client.optimize_batch(batch)  # POST /v1/optimize/batch
```

---

## 7. 性能特征

| 组件 | 时间复杂度 | 瓶颈 |
|------|-----------|------|
| ChineseSplitter | O(n) | — |
| jieba 分词 | O(n × k) | 词典加载 (冷启动 ~1s) |
| TextTiling | O(n log n) | 块长 |
| ScriptAnalyzer | O(n × m) | m = 场景词数量 |
| SubtitleSegmenter | O(n) | — |
| 大文本分块 | O(n / 50000) | Docker 内存 |
| LLM Tier | O(n × tokens) | API 延迟 |

---

## 8. 测试架构

```
tests/
├── unit/                          # 单元测试 (25 文件)
│   ├── test_zh_splitter.py        # 中文分句 (含书名号保护)
│   ├── test_en_splitter.py        # 英文分句
│   ├── test_length_segmenter.py   # 字数控制 (含配对引号)
│   ├── test_script_analyzer.py    # 剧本分析
│   ├── test_storyboard.py         # 分镜
│   ├── test_subtitle_exporter.py  # 字幕导出
│   ├── test_exporter.py           # PromptEngineExporter (含 context)
│   ├── test_performance_baseline.py # 性能基线 (4 测试)
│   └── ...
│
├── integration/                   # 集成测试 (7 文件)
│   ├── test_pipeline.py           # 完整管线
│   ├── test_rest_api.py           # REST API
│   ├── test_prompt_engine_client.py # PROJECT-011 桥接 (含 context)
│   └── test_workbench.py          # 工作台
│
└── 当前: 324 passed, 9 skipped, 100% 通过
```

---

## 9. 部署拓扑

```
开发环境 (本地)
  ├── Python 3.11+ + pip install -e .[all]
  ├── REST API: http://localhost:8000
  ├── Streamlit: http://localhost:8501
  └── MCP Server: stdio

与 PROJECT-011 联合
  ├── PROJECT-012: http://localhost:8000 (分句)
  ├── PROJECT-011: http://localhost:8013 (优化)
  └── 数据流向: 文本 → PROJECT-012 → batch → PROJECT-011 → prompt 带 context
```
