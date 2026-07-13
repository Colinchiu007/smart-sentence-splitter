# PROJECT-012 — 语义分句引擎 PRD

## 1. 产品概述

**产品名**：SmartSentenceSplitter（智能语义分句引擎）

**一句话描述**：输入长文，按**语义完整性 + 字数/时长约束**自动切割为结构化句子序列，输出可用于字幕生成、逐句生图、视频合成的标准化分句数据。

| **核心价值**：从「标点符号切分」升级到「语义理解级切句」，打通「文案→分句→字幕→逐句配图→轮播视频」的自动化管线。

**多语言支持**（v0.2 新增）：中文（jieba 增强）+ 英文（缩写+引号保护）+ 中英混排路由，P2 扩展日文。 |

## 2. 目标用户

| 用户类型 | 特征 | 痛点 | 调用方式 |
|---------|------|------|---------|
| **内容创作者（终端）** | 用此引擎做视频的创作者 | 手动逐句分句耗时，字幕配图对不上 | 体验工作台（Web UI） |
| **开发者** | 集成到自己的 Web/App/桌面应用 | 没有好用的开源分句 API | REST API / SDK |
| **AI 工作流用户** | ComfyUI / n8n 等工作流工具 | 分句作为前置节点 | MCP Server / CLI |

## 3. 产品架构（三级分割模型）

```
输入文本（长文/文章）
    │
    ▼
┌─────────────────────────────┐
│  Layer 1: 语义分句引擎       │  ← 核心创新
│  技术栈：                    │
│    ├─ jieba (分词+词性标注)  │
│    ├─ TextTiling (主题边界)  │
│    └─ LLM (可选深度语义)     │
│  输出：语义完整的句子列表      │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│  Layer 2: 场景级分割         │  ← 已有代码升级
│  规则：                      │
│    ├─ 不切断句子              │
│    ├─ 目标字数 = 语速×时长    │
│    └─ 语义边界优先于字数边界   │
│  输出：语音段落列表            │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│  Layer 3: 字幕级分割         │  ← 已有代码升级
│  规则：                      │
│    ├─ 8-15字/块（可配置）     │
│    ├─ 标点优先级矩阵          │
│    └─ 阅读节奏保留            │
│  输出：字幕块列表（含时间戳）  │
└─────────────────────────────┘
    │
    ▼
输出标准化 JSON
  ├─ sentences: 语义句子列表
  ├─ scenes: 场景段落（含时长估算）
  ├─ subtitles: 字幕块（含时间信息）
  └─ era_info: 每段落时代检测结果
```


### 3.1 两维度理解：精度栈 × 产出栈

分句引擎在两个正交维度上运作，分别解决**"断得准不准"**和**"输出给谁用"**的问题。

#### 纵向维度 — Tier 降级链（分句精度栈）

决定**用什么方法**来找句子边界，精度从高到低自动降级：

| Tier | 分句器 | 原理 | 可用性 |
|------|--------|------|--------|
| **Tier 1** | LLMSplitter | 大模型语义理解分句 | 需 API key |
| **Tier 2A** | TextTilingSemanticSplitter | 主题边界识别（词汇重复度） | 需配置启用 |
| **Tier 2B** | ChineseSplitter / EnglishSplitter | jieba 分词 + 词性 + EOS 窗口 | 始终可用 |
| **Tier 3** | ChineseRuleSplitter / EnglishRuleSplitter | 纯标点规则（零依赖兜底） | 始终可用 |

> **关键行为**：TierChain.split() 从 Tier 1 开始逐级尝试，不满足 is_available() 或抛异常时自动降级——**保证永远有结果返回**。

#### 横向维度 — 三层输出粒度栈

决定**输出什么粒度**给下游消费，从细到粗：

| 层级 | 数据结构 | 产生方式 | 用途 |
|------|---------|---------|------|
| **句子级（Layer 1）** | SentenceBlock[] | Tier 链分句（物理上的第一次分句操作） | 下游分析：剧本分析、时代检测、情感分析 |
| **场景级（Layer 2）** | SceneSegment[] | SceneSegmenter **合并**句子成 ~6 秒语音段落（不切分） | TTS / 配音 / 场景配图 |
| **字幕级（Layer 3）** | SubtitleBlock[] | SubtitleSegmenter 按字数限制**重新切分**（物理上的第二次分句操作） | 视频字幕（每行 8-15 字，带时间戳） |

> **注意**：中间 Layer 2（SceneSegmenter）是**合并操作而非切分**。真正执行分句操作的是两个点：Tier 链做语义边界分句 → SentenceBlock；SubtitleSegmenter 做字数限制切分 → SubtitleBlock。

#### 两维度的关系
```
                      ┌── 纵向：精度栈（怎么断句）──┐
                      │  Tier 1 → Tier 2 → Tier 3   │
                      └──────────────┬───────────────┘
                                     │
               输入文本 ──────────────┼─────────────→ ① 语义分句 → SentenceBlock[]
                                     │
                                     ├─────────────→ ② SceneSegmenter 合并 → SceneSegment[]
                                     │
                                     └─────────────→ ③ 字幕切分 → SubtitleBlock[]
                      ┌── 横向：产出栈（输出什么）──┐
                      │  句子级 → 场景级 → 字幕级   │
                      └─────────────────────────────┘
```

**总结**：两个维度正交——无论用 Tier 1（LLM）还是 Tier 3（纯规则）分句，最终都会经过场景合并 → 字幕切分的产出流水线，输出始终是标准化的 `SplitResult` 结构。


## 4. 功能列表

### P0 — 核心功能（MVP 必做）

| 编号 | 功能 | 描述 | 验收标准 |
|------|------|------|---------|
| F-01 | **规则分句器** | 基于标点+启发式规则的基础分句（继承现有 SentenceTokenizer） | 中英文混合、缩写、引号内句号不误判 |
| F-02 | **jieba 增强分句器** | 利用 jieba 分词+词性标注辅助语义边界判定 | 不在实体中间切分；在复句连接词处识别语义边界 |
| F-03 | **TextTiling 主题分割** | 基于词汇重复度的无监督主题边界检测 | 多段落文章能识别主题转换点 |
| F-04 | **LLM 深度分句**（可选调用） | 调用 LLM 做最细粒度的语义分句（降级链的最高层） | 长难句识别子句边界准确率 > 90% |
| F-05 | **三级退化链** | LLM → TextTiling → 规则分句自动降级（可配置） | LLM 超时/限流时自动降级不中断 |
| F-06 | **场景级分割** | 继承现有 SceneSegmenter，增强语义边界优先逻辑 | 不切断句子，字数达标时优先在语义边界切 |
| F-07 | **字幕级分割** | 继承现有 SubtitleSegmenter，增加阅读节奏模型 | 8-15字/块可配，标点优先级矩阵 |
| F-08 | **时代检测集成** | 继承现有 EraDetector，每段落标注 era_info | 古代/现代/混合判定准确率 > 90% |
| F-09 | **输出标准化** | JSON 输出含 sentences/scenes/subtitles/era_info | 下游可直接消费 |

### P1 — 体验层

| 编号 | 功能 | 描述 |
|------|------|------|
| F-10 | **体验工作台** | Streamlit Web UI，输入文本→实时预览分句结果 |
| F-11 | **REST API** | FastAPI 封装，`POST /v1/split` |
| F-12 | **CLI 工具** | `sentence-splitter -i input.txt -o output.json` |

### P2 — 扩展能力

| 编号 | 功能 | 描述 |
|------|------|------|
| F-13 | 流式分句 | 增量处理超长文本（> 100K 字） |
| F-14 | SRT/ASS 字幕导出 | 输出字幕格式文件 |
| F-15 | 生图提示词生成 | 每句/段结合时代信息生成 AI 绘图 prompt |

## 5. 降级链设计（核心创新）

```
              ┌──────────────┐
              │  输入文本      │
              └──────┬───────┘
                     │
            ┌────────▼────────┐
            │ LLM 语义分句     │ ← Tier 1: 精度最高，成本最高
            │ (API 可用时)     │
            └────────┬────────┘
                     │ 超时/限流/失败
            ┌────────▼────────┐
            │ TextTiling      │ ← Tier 2: 无监督主题+语义边界
            │ + jieba 增强     │     无外部依赖，精度中等
            └────────┬────────┘
                     │ 文章太短/效果不佳
            ┌────────▼────────┐
            │ 规则分句器       │ ← Tier 3: 零依赖，精度最低但稳定
            │ (标点+启发式)     │
            └────────┬────────┘
                     │
            ┌────────▼────────┐
            │ 场景级 + 字幕级  │ ← 三层通用，下游处理
            │ 分割             │
            └─────────────────┘
```

## 6. 数据模型

```python
@dataclass
class SentenceBlock:
    text: str                    # 句子文本
    index: int                   # 全局序号
    char_count: int              # 字符数
    word_count: int              # 词数（jieba 分词结果）
    words: List[str]             # 分词结果
    pos_tags: List[str]          # 词性标注
    tier: str                    # 分句器来源: llm / texttiling / rule
    confidence: float            # 置信度 0-1

@dataclass
class EraInfo:
    era: str                     # modern / ancient / mixed
    confidence: float            # 置信度
    keywords: List[str]          # 匹配关键词

@dataclass
class SceneSegment:
    text: str
    segment_id: int
    estimated_duration: float
    target_words: int
    sentences: List[SentenceBlock]  # 包含的句子
    era_info: Optional[EraInfo]     # 时代信息
    subtitles: List[SubtitleBlock]

@dataclass
class SubtitleBlock:
    text: str
    display_order: int
    start_time: float
    duration: float
    parent_segment_id: int
```

## 7. 非功能需求

| 维度 | 要求 |
|------|------|
| **性能** | 10K 字文本 ÷ 规则分句 < 1s；÷ LLM 分句 < 30s |
| **最大输入** | 单次 50K 字（LLM模式下）；无限制（规则模式下） |
| **零依赖模式** | 规则分句器零外部依赖，纯 Python stdlib |
| **安装体积** | 核心库 < 5MB（不含 jieba 词典） |
| **API 形态** | Python SDK + REST API + CLI + MCP Server |
| **可配置性** | 全部参数 YAML 可配，支持运行中热更新 |

## 8. 验收测试矩阵

| 测试场景 | P0/P1 | 测试方法 |
|---------|-------|---------|
| 中英文混合分句 | P0 | 输入 "Hello world。这是一段测试text。" → 正确分2句 |
| 引号内句号不误判 | P0 | "他说："好的。"然后走了。" → 不误切在引号内句号 |
| 缩写处理 | P0 | "Dr. Wang 和 Mr. Li" → 不在缩写点处切 |
| 长难句子句识别 | P0 | 含"虽然…但是…"、"因为…所以…"的复句 |
| 实体完整性 | P0 | "习近平主席" 不分到 "习近平" "主席" 两句 |
| 场景级字数约束 | P0 | 目标20字 → 每段字数在10-30之间，且在句子边界 |
| 字幕级8-15字约束 | P0 | 每个字幕块8-15字 |
| 时代检测 | P0 | 古代/现代检测准确率 > 85% |
| 降级链 | P0 | 模拟LLM超时 → 自动降级到 TextTiling |
| 体验工作台 | P1 | 输入→预览→导出正常工作 |

## 9. 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.11+ | 你的现有代码就是 Python，jieba 生态 |
| 分词 | jieba 0.42+ | 成熟中文分词，词性标注+NER |
| 主题分割 | TextTiling（自实现） | 无监督，零外部依赖，效果好 |
| Web 框架 | FastAPI + Streamlit | FastAPI 提供 REST，Streamlit 做工作台 |
| LLM 分句 | 接口抽象（可接入任何 LLM） | 抽象接口，不绑定供应商 |
| 配置 | YAML | 继承你现有 config.yaml 设计 |
| 输出 | JSON | 通用结构化格式 |

## 10. 迭代计划

| 迭代 | 内容 | 预估工期 |
|------|------|---------|
| **v0.1** | 规则分句器 + 场景分割 + 字幕分割（迁移现有代码） | 1天 |
| **v0.2** | jieba 增强分句器 + TextTiling + 实体保护 | 2天 |
| **v0.3** | 三级退化链 + LLM 分句接口 | 1天 |
| **v0.4** | 时代检测集成 + REST API | 1天 |
| **v0.5** | 体验工作台（Streamlit）+ CLI | 1天 |
| **v0.6** | SRT导出 + 生图提示词生成 | 1天 |

## 11. 多语言策略

### 11.1 语言优先级

| 语言 | 优先级 | 分词器 | 分句标点 | 缩写词表 | 引号规则 |
|------|--------|--------|---------|---------|---------|
| **zh（中文）** | P0 | jieba | `。！？；……\n` | ["等","即","如"] | 「」"" `''` |
| **en（英文）** | P0 | 空白分词（无外部依赖） | `. ! ? ; — \n` | 18 个默认缩写（Mr. Dr. U.S. e.g. 等）| `" " ' '` |
| **ja（日文）** | P2 | fugashi/MeCab | `。！？` | — | 「」 |
| **mixed（中英混）** | P0 | 双语切换策略 | 全部 | 全部 | 全部 |

### 11.2 多语言分句特殊挑战与解决方案

| # | 挑战 | 解决方案 |
|---|------|---------|
| 1 | 中英混合段落自动识别 | 按段落/句子自动检测语言 → 走对应分句器 |
| 2 | 英文缩写点不当作句号 | 缩写词表 + 大写首字母规则（`Mr.` `U.S.` 整词保护） |
| 3 | 英文引号内 `He said "Hello."` 不切 | 引号对匹配 + 成对保护 |
| 4 | 英文破折号 `—...—` 子句边界 | 识别 `—...—` 包裹的子句边界，标注为次级分句 |
| 5 | 英文省略号 `...` 视为 1 个标点 | 三点合并规则 |
| 6 | 跨语言空行分隔 | 中英文段落间用空行/换行清晰分隔 |
| 7 | 语言自动检测 | langdetect + 字符集启发式（CJK>30%→zh, ASCII>90%→en） |
| 8 | 跨语言专有名词保护 | 中文人名/英文人名识别后整段保护 |

### 11.3 多语言配置入口

```yaml
# config/splitter.yaml
language: "auto"  # auto | zh | en | ja | mixed

sentence_tokenizer:
  language: "auto"
  handle_abbreviations: true

  # 跨语言默认缩写词表
  custom_abbreviations:
    # 中文
    - "等"
    - "即"
    - "如"
    # 英文（v0.2 内置 18 个）
    # Mr. Dr. Mrs. Ms. U.S. U.K. e.g. i.e. etc. vs. Inc. Ltd. Jr. Sr. a.m. p.m. No. Vol.

  # 按语言特定配置
  language_specific:
    zh:
      tokenizer: "jieba"
      use_pos: true              # 使用词性标注
      entity_protection: true     # 实体完整性保护
    en:
      tokenizer: "whitespace"     # 零依赖
      use_pos: false
      abbreviation_table: "default_en"
      quote_pairs: [["\"", "\""], ["'", "'"]]
      handle_ellipsis: true
      handle_em_dash: true
    ja:
      tokenizer: "fugashi"
      enabled: false              # v0.6 再做
```

### 11.4 英文默认缩写词表（v0.2 内置）

```python
EN_ABBREVIATIONS = [
    # 头衔
    "Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Sr.", "Jr.", "St.",
    # 机构/地标
    "U.S.", "U.K.", "U.S.A.", "E.U.", "U.N.",
    # 商业
    "Inc.", "Ltd.", "Corp.", "Co.", "LLC.",
    # 学术引用
    "etc.", "i.e.", "e.g.", "vs.", "cf.", "al.",
    # 时间
    "a.m.", "p.m.", "A.M.", "P.M.",
    # 数字/编号
    "No.", "Vol.", "pp.", "p.",
    # 拉丁缩写
    "et al.", "n.b.", "q.v.",
]
```

### 11.5 数据模型补充

```python
@dataclass
class SentenceBlock:
    text: str
    index: int
    char_count: int
    word_count: int
    words: List[str]
    pos_tags: List[str]            # 中文用 jieba posseg，英文可空
    language: str                  # ← 新增：每句独立语言标签 zh/en/ja
    tier: str
    confidence: float
```

### 11.6 验收测试矩阵（多语言补充）

| # | 测试场景 | 期望 |
|---|---------|------|
| ML-01 | 纯中文分句 | zh 路径生效，结果含 jieba 分词/词性 |
| ML-02 | 纯英文分句 | en 路径生效，标点 `. ! ?` 正确识别 |
| ML-03 | 中英混排 `他说"Hello"然后走了` | 引号对保护，英文部分整段识别为 en |
| ML-04 | 英文缩写 `Dr. Smith 和 Mr. Wang 在 U.S. 工作` | 4 个点都不切 |
| ML-05 | 英文省略号 `He thought... and then left.` | `...` 视为 1 个边界 |
| ML-06 | 英文破折号子句 `The result — surprisingly — was positive.` | 识别 `—...—` 包裹子句 |
| ML-07 | 语言 auto 检测 | 输入纯英文→`language=en`；纯中文→`language=zh` |
| ML-08 | 多段落混排 | 段1中文+段2英文→按段落分别调用对应分句器 |
| ML-09 | 跨语言时长估算 | en 段使用 `words/3.0`（英文语速），zh 段使用 `chars/3.3` |

### 11.7 多语言工期影响

| 组件 | 中文 | 英文 | 日文 |
|------|------|------|------|
| 规则分句器 | 已实现 | +0.5天 | P2 |
| 语义分句器 | jieba 已实现 | 空白分词+缩写表 0.5天 | fugashi 0.5天 |
| TextTiling | 语言无关 | 复用 | 复用 |
| 场景/字幕 | 语言无关 | 复用 | 复用 |
| **总增工期** | 0 | **+1天** | P2 |

---

## 12. 与现有素材的关系

| 现有素材 | 在 PROJECT-012 中的角色 |
|---------|---------------------|
| `text_segmentation_module.py` | Layer 2 + Layer 3 的基础实现 → 整合到 `src/splitter/scene_subtitle.py` |
| `era_detector_demo.py` | F-08 时代检测（仅中文生效）→ 整合到 `src/splitter/era.py` |
| `config.yaml` | 全局配置 → 扩展字段（multilingual 段）放 `config/splitter.yaml` |
| `text_segmentation_requirements.md` | 本 PRD 的功能需求来源 |

---

**版本**: v0.2.0
**日期**: 2026-06-13
**作者**: PM (COO role)
**状态**: 待 CEO 签字
**变更**: v0.1 → v0.2 新增多语言支持章节（§11）
