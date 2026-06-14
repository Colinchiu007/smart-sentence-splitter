# PROJECT-012 CHANGELOG

## [0.8.0] - 2026-06-14

### ✨ v0.8.0 — SRT/ASS 字幕导出 + PROJECT-011 端到端桥接

#### SubtitleExporter (SRT + ASS)

`src/splitter/exporter/subtitle_exporter.py` — 导出标准字幕格式。

**SRT**:
```
1
00:00:00,000 --> 00:00:03,000
今天天气真好
```

**ASS**: 完整头部 (Script Info + V4+ Styles + Events) + 角色名作为 Name 字段。

**特性**: 跨场景时间累加, 零依赖, 纯字符串拼接。

#### PromptEngineClient (PROJECT-011 HTTP 客户端)

`src/splitter/exporter/prompt_engine_client.py` — 封装 PROJECT-011 REST API:

- `health_check()` / `optimize()` / `optimize_batch()`
- `build_optimize_payload()` / `parse_optimize_response()`

**依赖**: `requests` (optional, 按需导入)

#### 实测验证

```
输入剧本 → SmartSentenceSplitter (enable_script_analysis=True)
        → 7 句 / 4 场, 自动填角色 (小明/小红) + 场景 (超市/公园/学校)
        → SRT 字幕 (192 字符, 17.27s)
        → Storyboard JSON (4 场)
        → PROJECT-011 payload (platform=mj, creative=5, max_length=500)
```

#### 📊 测试

- **新增 17 个测试** (12 SRT/ASS + 5 client)
- **总计: 312 个测试 100% 通过 + 7 skipped** ✅

#### 📁 新增文件

```
src/splitter/exporter/
├── subtitle_exporter.py          # 新 (4.2KB)
└── prompt_engine_client.py       # 新 (3.7KB)

tests/unit/test_subtitle_exporter.py
tests/integration/test_prompt_engine_client.py
examples/verify_end_to_end.py
```

## [0.8.1] - 2026-06-14

### 🔧 v0.8.1 — PROJECT-011 端到端真实验证 + 平台名修正

#### 实测成功

启动 PROJECT-011 (port 8013) + 真实调 /v1/optimize/batch:
```
输入: 7 句中文剧本 → 7 条 PROJECT-011 优化请求
输出: 7 条 Midjourney 英文 prompt, 平均 850 tokens/条
```

**PROJECT-011 优化前后对比示例**:
- 输入: `小明走进超市。`
- 输出: `Xiao Ming, a young man with a friendly expression, walks confidently through the...`

#### 修复

- **平台名修正** (zh→midjourney, en→stable_diffusion, ja→jimeng)
  - 原代码用 `mj`/`sd`/`niji` 简写, 与 PROJECT-011 真实枚举不匹配
  - 修复: 7 条请求全部 200 OK (修复前 422 Unprocessable Entity)
- **batch 端点格式**: `{requests: [...]}` 包装, 不是裸 list

#### 测试

- 新增 2 e2e 测试 (test_real_optimize_batch, test_real_platform_mapping)
- **总计: 312 passed + 9 skipped (无 PROJECT-011)** ✅

#### 新增文件

```
examples/verify_prompt_engine_e2e.py    # 端到端实测脚本
tests/integration/test_prompt_engine_client.py  # +2 e2e 测试
```

## [0.7.0] - 2026-06-14


### ✨ v0.7.0 — 剧本分析 + 分镜增强 (Storyboard)

#### 新增模块: ScriptAnalyzer

`src/splitter/script/script_analyzer.py` — 从完整剧本文本提取：
- **角色列表** (jieba nr 词性→人名) 
- **故事梗概** (第一段摘要)
- **场景/地点列表** (jieba ns 词性 + 后缀启发式)
- **关键词表** (高频名词)
- **场景变化检测** (地点信号词 → new scene)

设计原则：零 LLM 依赖，纯规则 + jieba。无 jieba 时降级为字符启发式。

#### SceneSegment 扩展

| 新增字段 | 类型 | 说明 |
|----------|------|------|
| `characters` | List[str] | 本场出现的角色 |
| `setting` | str | 本场地点 |
| `mood` | str | 情绪标签 |
| `story_phase` | str | 叙事阶段 (开头/发展/高潮/结局) |
| `to_image_hint()` | 方法 | 生成画面提示词片段供 PROJECT-011 消费 |

所有新字段有默认值，不破坏 v0.6.x 旧代码。

#### 新增模块: StoryboardExporter

`src/splitter/exporter/storyboard.py` — 分镜 JSON 输出格式：

```json
{
  "story_synopsis": "小明是一个普通的高中生...",
  "characters": [{"name": "小明"}],
  "settings": ["超市", "学校", "公园"],
  "total_scenes": 8,
  "total_duration": 36.4,
  "scenes": [
    {
      "scene_id": 0,
      "text": "小明是一个普通的高中生。",
      "duration_s": 3.6,
      "characters": [],
      "setting": "",
      "mood": "",
      "phase": "",
      "image_hint": "小明是一个普通的高中生。, 风格:mixed",
      "era": "mixed",
      "scene_context": { "next_setting": "", ... }
    }
  ]
}
```

#### 架构设计原则

基于多 Agent 分镜理论 (参考 AI 短剧工作流)：

```
编剧 Agent (PROJECT-012)     → 剧本结构分析
导演 Agent (PROJECT-012)     → 场景分割 + 时长计算
提示词优化 Agent (PROJECT-011) → 分镜提示词 + 角色一致性
```

PROJECT-012 做结构分析（角色/场景/情绪/时长），PROJECT-011 做创意生成（提示词/风格/一致性）。

#### 输出格式对齐

分镜 JSON 可直接传给 PROJECT-011：
```
POST /v1/optimize/batch  ← storyboard.scenes[].image_hint
角色一致性 ← storyboard.characters
场景一致性 ← storyboard.settings
```

#### 📊 测试

- **新增 21 个测试用例**（角色提取/场景提取/梗概/场景变化/Storyboard 序列化/集成）
- **总计: 290 个测试用例 100% 通过 + 5 skipped** ✅

#### 📁 新增文件

```
src/splitter/
├── script/
│   ├── __init__.py
│   └── script_analyzer.py       # 新 (7KB)
├── models/
│   └── scene.py                  # 升级 (4 新字段 + to_image_hint)
└── exporter/
    └── storyboard.py             # 新 (2.4KB)

tests/unit/
├── test_script_analyzer.py       # 新 (12 个测试)
└── test_storyboard.py            # 新 (9 个测试)

examples/
└── verify_storyboard.py          # 新 (实测)

docs/
└── PM-PRD-ARCH-v0.7.md           # 新 (PRD+ARCH 合并)
```

## [0.6.1] - 2026-06-14

### ✨ v0.6.1 — PROJECT-011 桥接 (exporter)

新增 `exporter/prompt_engine.py` — 将 PROJECT-012 的分句输出转换为 PROJECT-011 (prompt-engine) 的 OptimizeRequest 格式。

#### 功能

| 方法 | 输入 | 输出 | 用途 |
|------|------|------|------|
| `to_optimize_request(sentence, era?)` | SentenceBlock | dict (OptimizeRequest) | 单句 → 提示词 |
| `to_batch_request(sentences, eras?)` | SentenceBlock[] | list[OptimizeRequest] | 批量 → 提示词 |
| `from_split_result(result)` | SplitResult | list[OptimizeRequest] | 完整结果 → 批量提示词 |

#### 转换规则

- **语言→平台**: zh→mj, en→sd, ja→niji, auto→generic
- **字数→参数**: too_short→创意+3, too_long→max_length=200
- **时代→风格**: ancient→classical, modern→contemporary, mixed→eclectic

#### 集成

分离设计，无跨包依赖。PROJECT-012 产生数据，PROJECT-011（独立仓库）消费数据。集成点在数据格式层。

```
# PROJECT-012 分句 → 导出 → PROJECT-011 一键优化
python -c "
from splitter import SmartSentenceSplitter
from splitter.exporter.prompt_engine import PromptEngineExporter

result = SmartSentenceSplitter({'enable_era': True}).split('清军在甲午战争中死磕到底。')
exporter = PromptEngineExporter()
batch = exporter.from_split_result(result)
# batch now ready for POST /v1/optimize/batch
"
```

#### 📊 测试

- **新增 9 个测试用例**（基础转换/时代/字数/批量/英文/空）
- **总计: 269 个测试用例 100% 通过 + 5 skipped** ✅

#### 📁 新增文件

```
src/splitter/exporter/
├── __init__.py
└── prompt_engine.py              # 新 (5.2KB)

tests/unit/
└── test_exporter.py               # 新 (9 个测试)

examples/
└── verify_exporter.py             # 新 (实测脚本)
```

---

## [0.6.0] - 2026-06-14

### ✨ v0.6 — 字数控制分句 (length_strategy)

#### 新增功能

**LengthSegmenter** — 按字数控制分句，3 种策略可切换：

| 策略 | 行为 | 适用场景 |
|------|------|---------|
| **off** | 透传，标记 status=ok | 不需要字数约束 |
| **A** | 按字数 + 优先级标点**重切**（每块 3-15 字）| 短信/TTS/字幕/AI 生图 prompt |
| **B** | 不切，标 length_status (ok/too_short/too_long) | 稿件分析/超长警告 |

**默认 B 模式** — 兼容 v0.5.1 现有行为，**239 个旧测试 0 修改**。

#### 关键设计

- **3 种模式可切换** — `length.strategy` 字段
- **数据模型扩展** — `SentenceBlock.length_status` + `length_strategy_applied`
- **Pipeline 集成** — 步骤 6.5（分句后，场景前）
- **优先级标点** — 中文句末 `。！？；` 优先，弱分隔 `，` 其次
- **贪心切** — 在 max_chars 范围内找最右的标点
- **强制切兜底** — 无标点时按 max_chars 硬切

#### 配置

```yaml
length:
  strategy: "B"  # off | A | B
  min_chars: 3
  max_chars: 15
  prefer_punctuation: true
  warning_on_violation: true
```

#### 📊 测试

- **新增 21 个测试用例**（默认 B / A 模式 / 边界 / 英文 / 异常）
- **总计: 260 个测试用例 100% 通过 + 5 skipped** ✅

#### 实测对比

输入：`"今天天气真好，阳光明媚，我们决定去郊外的公园散步，享受难得的周末时光。"`

- **B 模式**：1 句, status=too_long (32字)
- **A 模式**：3 块（"今天天气真好，阳光明媚，" + "我们决定去郊外的公园散步，" + "享受难得的周末时光。"）
- **off 模式**：原样通过

#### 📁 新增/修改文件

```
src/splitter/
├── scene_subtitle/
│   └── length_segmenter.py          # 新 (7.5KB)
├── models/
│   └── sentence.py                   # 加 2 字段 (length_status, length_strategy_applied)
├── pipeline.py                       # 步骤 6.5 集成
└── utils/config_loader.py            # DEFAULT_CONFIG 加 length 段

config/splitter.yaml                  # 加 length 段

tests/unit/
└── test_length_segmenter.py          # 新 (21 个测试)

examples/
└── verify_length_strategy.py         # 新 (实测脚本)
```

---

## [0.5.1] - 2026-06-14

### ✨ v0.5.1 — 真实 LLM 验证 + MCP Server + 4 个缺陷修复

#### Step 1: 真实 LLM 端到端验证
- `examples/verify_real_llm.py` — 写入了可复现的真实 LLM 验证脚本
- **结果**: OpenRouter deepseek-chat 中/英文分句通过, Pipeline `mode=precise` 走 `tier1_llm`

#### Step 2: MCP Server
- 新增 `src/splitter/api/mcp_server.py` (6.5KB) — 基于 MCP SDK 1.x
- **tool**: `split_text` — 分句（支持所有配置参数 + Pydantic schema）
- **resources**: `status://health` + `status://capabilities`
- 启动: `python -m splitter.api.mcp_server`（stdio 模式）
- 自动检测 API key → 自动启用 LLM Tier
- `mode=precise` 自动 `enable_topic_segmentation=True`
- `mode=fast` 自动 `min_tier=3`

#### Step 3: 4 个缺陷修复
1. **CHANGELOG 缺失 v0.5.1** ✅ — 本条目
2. **AGENTS 版本还停在 v0.5.0** ✅ — 更新到 v0.5.1
3. **`verify_real_llm.py` 硬编码绝对路径** ✅ — 改为 `~/.pkuseg/config.yaml` + 环境变量
4. **`pipeline._apply_mode` 永久改 `self.config`** ✅ — 改为临时变量，不破坏配置状态

#### 📊 测试
- 新增: **5 个测试用例**（MCP Server 编译 + 导入）
- **总计: 239 个测试用例 100% 通过 + 5 skipped（无 key） ✅**

---

## [0.5.0] - 2026-06-13

### ✨ v0.5 — 3 步完成：真实 LLM 测试 + REST API + Streamlit 工作台

#### Step 1: 真实 LLM 端到端测试
- 新增 `tests/integration/test_real_llm.py` — 5 个真实 LLM 集成测试
- 跑法: `export OPENAI_API_KEY=*** && python -m pytest tests/integration/test_real_llm.py -v`
- **自动 skip 机制**：无 key 时所有测试 skip 不报错
- 覆盖：openai 中文/英文分句、pipeline 集成、xfyun 中文/pipeline

#### Step 2: REST API (FastAPI)
- 新增 `src/splitter/api/rest_api.py` — 4 个端点
  - `GET  /health` — 健康检查
  - `GET  /capabilities` — 能力声明（tiers / languages / modes / features）
  - `GET  /v1/info` — 运行时配置（LLM 可用性等）
  - `POST /v1/split` — 核心分句端点（Pydantic 验证）
- 自动生成 OpenAPI schema → `GET /docs` Swagger UI
- 启动: `uvicorn splitter.api.rest_api:app --reload` 或 `python -m splitter.api.rest_api`
- 错误处理：400 (config) / 422 (Pydantic) / 503 (LLM key 缺失) / 500 (内部错误)

**关键修复**：TierChain 重构 — `min_tier_provider` callable，mode=fast/balanced/precise 现在能真正生效（之前是 `_apply_mode` 改了 config 但 chain 已构造）

#### Step 3: Streamlit 体验工作台
- 新增 `workbench/app.py` (5.9KB) — 完整 Web UI
- **侧栏配置**：语言 / 模式 / 高级选项（era / topic / LLM）
- **主区域**：输入文本框 + 分句按钮 + 句子列表（标 ⬜/🟦 topic boundary）+ 场景表格
- **JSON 输出**：可展开查看 + 一键下载 `.json` 文件
- **底部说明**：模式/Tier/自动降级规则
- 启动: `streamlit run workbench/app.py` 或 `bash scripts/run_workbench.sh`

#### 📊 测试

- 新增: **18 个测试用例**
  - 5 个真 LLM 测试（skip when no key）
  - 13 个 REST API 测试（health/capabilities/info/split + OpenAPI schema）
- **总计: 234 个测试用例 100% 通过 + 5 个 skipped（无 key） ✅**

#### 📁 新增文件

```
src/splitter/api/
└── rest_api.py                     # 新 (FastAPI app, 8 routes)

workbench/
└── app.py                          # 新 (Streamlit UI, 5.9KB)

scripts/
└── run_workbench.sh                # 新 (启动脚本)

tests/integration/
├── test_real_llm.py                # 新 (5 个真 LLM 测试)
├── test_rest_api.py                # 新 (13 个 REST 测试)
└── test_workbench.py               # 新 (5 个工作台测试)
```

---

## [0.4.0] - 2026-06-13

### ✨ v0.4 — LLM Tier 完整实做（兑现 v0.3 stub 承诺）

#### 核心能力

- **3 个 LLM Provider** 全部实现：
  - `OpenAIProvider` — GPT-4o-mini/GPT-4o（base_url 透传）
  - `XfyunProvider` — 讯飞 MAAS API（与 OpenAI 协议兼容，默认 base_url 已配置）
  - `OllamaProvider` — 本地 LLM（端口探测 `/api/tags`）
- **LLMSplitter 从 stub → 实做**：
  - 真实可调用 `is_available()` / `split()`
  - Prompt 模板化（中文/英文双版本）
  - 3 层容错：纯 JSON → 正则提取 → 行切分 → 原文兜底
  - 重试机制（默认 max_retries=2）
- **Pipeline 集成**：enable_llm=True 时，LLM Tier 加入 Tier 1 链头；不可用时自动跳过（降级到 Tier 2）
- **Lazy 加载**：LLM splitter 实例不预加载，首次访问时创建

#### 配置文件（config/splitter.yaml）

```yaml
llm:
  provider: "openai"  # openai | xfyun | ollama
  model: "gpt-4o-mini"
  api_key_env: "OPENAI_API_KEY"  # 默认从环境变量读
  base_url: null
  timeout: 30
  max_retries: 2
  temperature: 0.0  # 分句要确定性
  max_tokens: 4096
```

#### 关键代码

**Provider 基类**（`src/splitter/llm/base.py`）：
```python
class LLMProvider(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...
    @abstractmethod
    def chat(self, messages, **kwargs) -> str: ...
```

**LLMSplitter 3 层解析**（`src/splitter/tiers/tier1_llm.py:_parse_response`）：
1. 直接 `json.loads(response)`
2. 正则提取 `\[.*?\]`
3. 按行切分 + 过滤 markdown
4. 兜底：按原文标点切

#### 📊 测试

- 新增: **41 个测试用例**
  - 3 个 Provider 单元测试（mock SDK 调用）: 20 个
  - LLMSplitter 重构测试（parse_response 4 层、retry、is_available）: 21 个
- **总计: 216 个测试用例 100% 通过 ✅**

#### 📁 新增文件

```
src/splitter/
├── llm/                          # 新 LLM 包
│   ├── __init__.py
│   ├── base.py                   # LLMProvider 抽象基类
│   ├── openai_provider.py        # OpenAI 适配
│   ├── xfyun_provider.py         # 讯飞 MAAS 适配
│   ├── ollama_provider.py        # 本地 LLM 适配
│   └── prompts.py                # 分句 prompt 模板
└── tiers/
    └── tier1_llm.py              # stub → 实做

tests/unit/
├── test_llm_providers.py          # 新 (20 个)
└── test_tier1_llm.py             # 新 (21 个)
```

#### ⚠️ 风险与缓解

| 风险 | 缓解 |
|------|------|
| LLM 返回非 JSON | 4 层容错：JSON → 正则 → 行切分 → 原文兜底 |
| API key 泄露 | 只读环境变量，不写日志/异常 |
| LLM 超时 | timeout 配置 + 重试 + 自动降级 |
| 体积依赖 | `openai` SDK 仍走 optional dependency |

---

## [0.3.0] - 2026-06-13

### ✨ v0.3 — 4 个竞品复用集成（HanLP/LAC/THULAC/FoolNLTK）

#### 7 项复用功能（F1-F7）

| # | 复用点 | 来源 | 改动 |
|---|--------|------|------|
| **F1** | **AC 自动机升级** — Match dataclass + 标准 emit 合并 | FoolNLTK `trie.py` | `languages/zh/ac.py` 重构 |
| **F2** | **DAG+DP 加权合并** — Customization 借鉴 jieba 思路 | FoolNLTK `_mearge_user_words` | `languages/zh/custom.py` 加 `adjust_dag()` |
| **F3** | **Lazy 模型加载** — EraDetector 按需加载 | FoolNLTK `_load_seg_model` | `pipeline.py` + `era/postprocessor.py` |
| **F4** | **TextTiling 增强** — 短文本早退重调 | 内部调优 | tier chain 已含 |
| **F5** | **Postprocessor 集成到 pipeline 主流** | THULAC `Postprocesser.adjustSeg` | `pipeline.split()` 自动调 chain |
| **F6** | **EraPostprocessor** — EraDetector 包装为 postprocessor | HanLP MTL 思想 | `era/postprocessor.py` 新文件 |
| **F7** | **mode=precise** + **LLM Tier 接口预留** | LAC 3-mode 切换 | `pipeline._apply_mode()` + `tiers/tier1_llm.py` |

#### 核心实现细节

**F1 (Match dataclass)**
```python
@dataclass
class Match:
    start: int
    end: int
    keyword: str
    length: int = 0  # 自动计算
```

**F1 (emit 合并)**
- BFS 构建 fail 指针时合并 `fail_node.emits | current_node.emits`
- `search()` 直接输出当前节点 emits（不重复查 fail 链）
- 4 个测试验证：`test_emit_merging_via_fail` / `test_emit_set_includes_overlapping`

**F2 (DAG+DP 加权合并)**
- 边类型：单字边 (1.0) / 分词边 (1 + length) / 用户词典边 (2 × length²)
- DP 选最大权重路径
- `adjust_dag()` 是 `adjust()` 的增强版，可与已有分词结果融合

**F3 (Lazy)**
- `_era_detector_instance = None` 在 `__init__`
- `_get_era_detector()` 首次访问时实例化
- 公开 `era_detector` property 保持向后兼容

**F5 (Postprocessor chain)**
- 拆分 `_handle_large_text()` 为独立方法
- pipeline.split() 9 步：检测→兜底→mode→链选→分句→场景→字幕→**chain**→返回

**F6 (EraPostprocessor)**
- 继承 BasePostprocessor
- `only_for_language="zh"` 过滤
- `try/except` 保证失败不影响主流程

**F7 (LLM Tier stub)**
```python
class LLMSplitter(BaseSentenceSplitter):
    language = "auto"
    tier = "tier1_llm"
    def is_available(self) -> bool: return False  # v0.3 不实现
    def split(self, text): raise NotImplementedError(...)
```

**F7 (mode 映射)**
- `fast` → min_tier=3, 关闭 TextTiling
- `balanced` → 默认（min_tier=2）
- `precise` → min_tier=1, 开启 TextTiling

#### 📊 测试

- 新增: **20 个测试用例**
  - F1 emit 合并 + Match dataclass: 4 个
  - F2 DAG+DP 合并: 4 个
  - F3 Lazy + F5 chain + F6 Era + F7 mode + LLM: 12 个
- **总计: 175 个测试用例 100% 通过 ✅**

#### 📁 新增文件

```
src/splitter/
├── era/
│   └── postprocessor.py        # 新 (EraPostprocessor)
├── postprocessor.py             # v0.2 → v0.3 增强 (chain 集成)
├── pipeline.py                  # 重构 (chain 集成 + lazy)
└── tiers/
    └── tier1_llm.py             # 新 (LLM Tier stub)

tests/integration/
└── test_v3.py                   # 新 (v0.3 集成测试 12 个)
```

#### ✨ 复用来源

| 来源 | 项目 stars | 复用次数 |
|------|----------|---------|
| FoolNLTK | 1.7K | F1, F2, F3 |
| HanLP | 36.4K | F6 (MTL 思想) |
| LAC | 百度 | F7 (mode 切换) |
| THULAC | 2.1K | F5 (postprocessor chain) |

---

## [0.2.0] - 2026-06-13

### ✨ v0.2 核心升级 — TextTiling 主题分割 + 4 项竞品复用

#### TextTiling 主题分割
- **TextTiling 算法实现** — 滑动窗口 + 余弦相似度 + 深度评分 + 边界识别
- **TextTilingSemanticSplitter** — 作为 Tier 2A 注册到 pipeline
- **ChineseSplitter EOS 窗口检测** — 对标点前后 5 字符做上下文分析（HanLP EOS 思路）
- **配置启用** — `enable_topic_segmentation: false`（默认关闭，向后兼容）
- 新文件: `src/splitter/texttiling/` (3 个文件 + 测试)

#### 复用 #1：AC 自动机 + Customization（来自 LAC）
- **Aho-Corasick 多模式匹配** — 纯 Python，O(n) 匹配
- **Customization 类** — `add_word()` / `load_customization()` / `adjust()` 完整接口
- 新文件: `src/splitter/languages/zh/ac.py` + `custom.py`

#### 复用 #2：EOS 标点窗口检测（来自 HanLP）
- ChineseSplitter 重构：`_find_eos_positions()` 窗口检测 + 复句连接词上下文分析

#### 复用 #3：后处理器统一接口（来自 THULAC）
- `BasePostprocessor` 抽象基类 + `PostprocessorChain` + `CustomMergingProcessor`
- 新文件: `src/splitter/postprocessor.py`

#### 复用 #4：大文本兜底（来自 THULAC __cutRaw）
- pipeline `split()` 增加 `max_input_length` 超限自动分块递归处理

#### 复用 #5：mode 切换（来自 LAC 3 mode）
- 配置 `mode: "fast" | "balanced" | "precise"` — 对应 min_tier=3/2/1

#### 📊 测试
- 新增: **54 个测试用例**
- **总计: 155 个测试用例 100% 通过 ✅**

---

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
