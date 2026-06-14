# PROJECT-012 CHANGELOG

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
