# ARCH-001 — PROJECT-012 语义分句引擎 整体架构

**版本**: v0.1.0
**日期**: 2026-06-13
**作者**: 架构师 (COO role)
**状态**: 待 CEO 签字
**关联**: PRD v0.2.0

---

## 1. 架构目标

| 目标 | 描述 |
|------|------|
| **G1 通用性** | Python SDK + REST API + CLI + MCP Server 四种调用形态 |
| **G2 弹性** | 三级降级链 (LLM → TextTiling+jieba → 规则)，无外部依赖时仍可用 |
| **G3 多语言** | zh (P0) + en (P0) + 中英混排 (P0) + ja (P2) |
| **G4 语义质量** | 优于纯标点分句，准确率 > 85% |
| **G5 体验层独立** | 配套 Web 工作台，可独立运行 |
| **G6 配置化** | 全参数 YAML 可配，热更新 |

---

## 2. 整体架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                       PROJECT-012 整体架构                         │
└──────────────────────────────────────────────────────────────────┘

        ┌─────────────────────────────────────────────────┐
        │              输入层 (Input Layer)                │
        │  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
        │  │ Python   │  │ REST     │  │   CLI    │  ...   │
        │  │ SDK      │  │ API      │  │          │       │
        │  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
        └───────┼─────────────┼─────────────┼─────────────┘
                │             │             │
                └─────────────┼─────────────┘
                              ▼
        ┌─────────────────────────────────────────────────┐
        │            API 适配层 (Adapter)                  │
        │  ┌────────────┐  ┌────────────┐  ┌──────────┐  │
        │  │ FastAPI    │  │ argparse   │  │ MCP      │  │
        │  │ router.py  │  │ cli.py     │  │ server   │  │
        │  └────────────┘  └────────────┘  └──────────┘  │
        └─────────────────────┬───────────────────────────┘
                              ▼
        ┌─────────────────────────────────────────────────┐
        │           核心引擎 (SmartSentenceSplitter)        │
        │  ┌─────────────────────────────────────────────┐ │
        │  │  TierChain  (降级链编排)                     │ │
        │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐      │ │
        │  │  │ Tier 1  │→ │ Tier 2  │→ │ Tier 3  │      │ │
        │  │  │ LLM     │  │ Semantic│  │ Rule    │      │ │
        │  │  │ Splitter│  │Splitter │  │Splitter │      │ │
        │  │  └─────────┘  └─────────┘  └─────────┘      │ │
        │  └─────────────────────────────────────────────┘ │
        │  ┌─────────────────────────────────────────────┐ │
        │  │  多语言路由 (LanguageRouter)                 │ │
        │  │  auto / zh / en / ja / mixed                │ │
        │  └─────────────────────────────────────────────┘ │
        │  ┌─────────────────────────────────────────────┐ │
        │  │  Layer 2 场景级分割 (SceneSegmenter)        │ │
        │  └─────────────────────────────────────────────┘ │
        │  ┌─────────────────────────────────────────────┐ │
        │  │  Layer 3 字幕级分割 (SubtitleSegmenter)     │ │
        │  └─────────────────────────────────────────────┘ │
        │  ┌─────────────────────────────────────────────┐ │
        │  │  EraDetector 时代检测 (可选)                │ │
        │  └─────────────────────────────────────────────┘ │
        └─────────────────────┬───────────────────────────┘
                              ▼
        ┌─────────────────────────────────────────────────┐
        │         数据模型层 (Models / Dataclasses)        │
        │  SentenceBlock / SceneSegment / SubtitleBlock   │
        │  EraInfo / SplitResult                          │
        └─────────────────────┬───────────────────────────┘
                              ▼
        ┌─────────────────────────────────────────────────┐
        │              输出层 (Output)                      │
        │  JSON 序列化 / SRT 导出 / 生图 prompt 生成       │
        └─────────────────────────────────────────────────┘

        ┌─────────────────────────────────────────────────┐
        │        体验工作台 (Streamlit Workbench)          │
        │  独立运行，不影响核心库                           │
        └─────────────────────────────────────────────────┘
```

---

## 3. 目录结构

```
PROJECT-012/
├── README.md
├── CHANGELOG.md
├── LICENSE
├── pyproject.toml                 # 项目配置 + 依赖
├── requirements.txt
├── .gitignore
├── .pre-commit-config.yaml
├── pytest.ini
│
├── config/
│   └── splitter.yaml              # 默认配置（含多语言）
│
├── src/
│   └── splitter/                  # 主包
│       ├── __init__.py
│       │
│       ├── core/                  # 核心抽象
│       │   ├── __init__.py
│       │   ├── base_tokenizer.py  # Tokenizer 抽象接口
│       │   ├── base_splitter.py   # SentenceSplitter 抽象接口
│       │   ├── tier_chain.py      # 降级链编排
│       │   └── language_router.py # 多语言路由
│       │
│       ├── languages/             # 语言包
│       │   ├── __init__.py
│       │   ├── zh/
│       │   │   ├── __init__.py
│       │   │   ├── tokenizer.py   # jieba 包装
│       │   │   ├── splitter.py    # 中文分句
│       │   │   ├── abbreviations.py  # 中文缩写
│       │   │   └── quotes.py      # 中文引号
│       │   ├── en/
│       │   │   ├── __init__.py
│       │   │   ├── tokenizer.py   # 空白分词
│       │   │   ├── splitter.py    # 英文分句
│       │   │   ├── abbreviations.py  # 18 个英文缩写
│       │   │   └── quotes.py      # 英文引号
│       │   └── ja/                # P2 暂留
│       │       └── __init__.py
│       │
│       ├── tiers/                 # 三级降级链
│       │   ├── __init__.py
│       │   ├── tier1_llm.py       # LLM 语义分句
│       │   ├── tier2_semantic.py  # TextTiling + jieba
│       │   └── tier3_rule.py      # 规则分句
│       │
│       ├── texttiling/            # 主题分割算法（自实现）
│       │   ├── __init__.py
│       │   ├── texttiling.py
│       │   └── sentence_similarity.py
│       │
│       ├── scene_subtitle/        # Layer 2 + 3
│       │   ├── __init__.py
│       │   ├── scene_segmenter.py
│       │   ├── subtitle_segmenter.py
│       │   └── config.py
│       │
│       ├── era/                   # 时代检测
│       │   ├── __init__.py
│       │   ├── detector.py
│       │   └── vocab.py
│       │
│       ├── api/                   # API 适配层
│       │   ├── __init__.py
│       │   ├── rest_api.py        # FastAPI
│       │   ├── cli.py             # argparse CLI
│       │   └── mcp_server.py      # MCP Server
│       │
│       ├── models/                # 数据模型
│       │   ├── __init__.py
│       │   ├── sentence.py
│       │   ├── scene.py
│       │   ├── subtitle.py
│       │   ├── era.py
│       │   └── result.py
│       │
│       ├── pipeline.py            # 主编排（SmartSentenceSplitter）
│       │
│       └── utils/
│           ├── __init__.py
│           ├── language_detect.py
│           ├── config_loader.py
│           └── serializer.py
│
├── tests/                         # 测试
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_zh_splitter.py
│   │   ├── test_en_splitter.py
│   │   ├── test_tier_chain.py
│   │   ├── test_texttiling.py
│   │   ├── test_scene_subtitle.py
│   │   ├── test_era.py
│   │   └── test_language_router.py
│   ├── integration/
│   │   ├── test_pipeline_zh.py
│   │   ├── test_pipeline_en.py
│   │   └── test_pipeline_mixed.py
│   └── fixtures/
│       ├── sample_zh.txt
│       └── sample_en.txt
│
├── workbench/                     # Streamlit 体验工作台
│   ├── app.py
│   └── requirements.txt
│
├── examples/                      # 使用示例
│   ├── sdk_usage.py
│   ├── rest_api_client.py
│   └── cli_usage.sh
│
├── docs/
│   ├── PRD.md
│   ├── ARCH-001.md                # 本文档
│   ├── ARCH-002-tiers.md          # 三级降级链详细设计（v0.3 写）
│   ├── ARCH-003-multilingual.md   # 多语言详细设计（v0.3 写）
│   ├── CHANGELOG.md
│   ├── AGENTS.md
│   └── api-reference.md
│
└── scripts/
    ├── dev_setup.sh
    └── run_workbench.sh
```

---

## 4. 核心组件设计

### 4.1 抽象接口层

```python
# core/base_tokenizer.py
from abc import ABC, abstractmethod
from typing import List, Tuple

class BaseTokenizer(ABC):
    """分词器抽象接口"""

    @abstractmethod
    def tokenize(self, text: str) -> List[str]:
        """分词"""
        pass

    @abstractmethod
    def pos_tag(self, text: str) -> List[Tuple[str, str]]:
        """词性标注 (可选实现)"""
        pass


# core/base_splitter.py
from abc import ABC, abstractmethod
from typing import List
from ..models import SentenceBlock

class BaseSentenceSplitter(ABC):
    """分句器抽象接口"""

    language: str = "zh"  # 子类覆盖

    @abstractmethod
    def split(self, text: str) -> List[SentenceBlock]:
        """将文本分割为句子"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """分句器是否可用（依赖是否安装、API 是否可达）"""
        pass
```

### 4.2 三级降级链

```python
# core/tier_chain.py
from typing import List, Optional
from .base_splitter import BaseSentenceSplitter
from ..models import SentenceBlock

class TierChain:
    """
    三级降级链编排：
    Tier 1 (LLM) → Tier 2 (TextTiling+jieba) → Tier 3 (规则)
    """

    def __init__(
        self,
        tier1: BaseSentenceSplitter,  # LLM
        tier2: BaseSentenceSplitter,  # Semantic
        tier3: BaseSentenceSplitter,  # Rule
        config: dict = None
    ):
        self.tiers = [tier1, tier2, tier3]
        self.tier_names = ["tier1_llm", "tier2_semantic", "tier3_rule"]
        self.config = config or {}
        self.min_tier = self.config.get("min_tier", 2)  # 最低允许的 tier
        self.enable_llm = self.config.get("enable_llm", False)

    def split(self, text: str) -> tuple[List[SentenceBlock], str]:
        """
        返回: (分句结果, 实际使用的 tier 名称)
        """
        start_tier = 0 if self.enable_llm else 1

        for i, (tier, name) in enumerate(zip(self.tiers[start_tier:], self.tier_names[start_tier:])):
            if i < self.min_tier - 1:
                continue
            if not tier.is_available():
                continue
            try:
                result = tier.split(text)
                if result and self._validate(result):
                    return result, name
            except Exception as e:
                # 记录到日志
                continue

        # 兜底：永远 Tier 3
        return self.tiers[2].split(text), "tier3_rule_fallback"

    def _validate(self, result: List[SentenceBlock]) -> bool:
        """验证分句结果是否合理（至少1句、平均长度合理）"""
        if not result:
            return False
        avg_len = sum(len(s.text) for s in result) / len(result)
        return 1 < avg_len < 500
```

### 4.3 多语言路由

```python
# core/language_router.py
from typing import List
from ..languages.zh.splitter import ChineseSplitter
from ..languages.en.splitter import EnglishSplitter
from ..utils.language_detect import detect_language

class LanguageRouter:
    """按语言路由到对应分句器"""

    def __init__(self, config: dict):
        self.config = config
        self.zh_splitter = ChineseSplitter(config.get("zh", {}))
        self.en_splitter = EnglishSplitter(config.get("en", {}))

    def route(self, text: str) -> tuple[str, object]:
        """
        返回: (检测到的语言, 对应的分句器实例)
        """
        mode = self.config.get("language", "auto")

        if mode == "auto":
            lang = detect_language(text)
        else:
            lang = mode

        if lang == "zh":
            return "zh", self.zh_splitter
        elif lang == "en":
            return "en", self.en_splitter
        elif lang == "mixed":
            # 中英混排：先用 zh splitter 主路 + en 段落单独处理
            return "mixed", self.zh_splitter
        else:
            return "zh", self.zh_splitter  # 兜底
```

### 4.4 主编排器

```python
# pipeline.py
from typing import Dict, Any
from .core.tier_chain import TierChain
from .core.language_router import LanguageRouter
from .scene_subtitle import SceneSegmenter, SubtitleSegmenter
from .era import EraDetector
from .models import SplitResult

class SmartSentenceSplitter:
    """
    主入口：对外的"门面"
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.router = LanguageRouter(self.config)
        self.chain = TierChain(
            tier1=...,
            tier2=...,
            tier3=...,
        )
        self.scene_segmenter = SceneSegmenter(self.config.get("scene", {}))
        self.subtitle_segmenter = SubtitleSegmenter(self.config.get("subtitle", {}))
        self.era_detector = EraDetector() if self.config.get("enable_era", False) else None

    def split(self, text: str) -> SplitResult:
        # 1. 多语言路由
        lang, splitter = self.router.route(text)

        # 2. Tier 链分句
        sentences, tier_used = self.chain.split(text)

        # 3. 场景级分割
        scenes = self.scene_segmenter.segment(sentences)

        # 4. 字幕级分割
        for scene in scenes:
            scene.subtitles = self.subtitle_segmenter.segment(
                scene.text, scene.estimated_duration, scene.segment_id
            )

        # 5. 时代检测 (可选)
        if self.era_detector:
            for scene in scenes:
                scene.era_info = self.era_detector.detect(scene.text)

        # 6. 返回结构化结果
        return SplitResult(
            sentences=sentences,
            scenes=scenes,
            tier_used=tier_used,
            language=lang,
            ...
        )
```

---

## 5. 数据流图

```
输入: text: str
  │
  ▼
[LanguageRouter] → 段落级语言检测
  │
  ├─→ zh 路径: ChineseSplitter
  ├─→ en 路径: EnglishSplitter
  └─→ mixed 路径: 段落级路由
  │
  ▼
[TierChain] → 三级降级
  │
  ├─→ Tier 1 (LLM): 精度最高, 成本最高
  ├─→ Tier 2 (TextTiling + jieba): 中等精度, 无外部依赖
  └─→ Tier 3 (Rule): 兜底, 零依赖
  │
  ▼
[List[SentenceBlock]]  ← 语义分句结果
  │
  ▼
[SceneSegmenter] → 场景级分割
  │  规则: 不切句, 字数达标, 语义边界优先
  │
  ▼
[List[SceneSegment]]  ← 语音段落
  │
  ▼
[SubtitleSegmenter] → 字幕级分割
  │  规则: 8-15字/块, 标点优先级
  │
  ▼
[List[SubtitleBlock]] (嵌套在 SceneSegment)
  │
  ▼
[EraDetector] (可选) → 时代检测
  │
  ▼
[SplitResult] → JSON 序列化输出
  │
  ▼
输出: JSON {
  "sentences": [...],
  "scenes": [...],
  "tier_used": "tier2_semantic",
  "language": "zh",
  "era_info": [...],
  "config": {...}
}
```

---

## 6. 接口设计（对外 SDK）

```python
# src/splitter/__init__.py
from .pipeline import SmartSentenceSplitter
from .models import SplitResult, SentenceBlock, SceneSegment, SubtitleBlock

__all__ = [
    "SmartSentenceSplitter",
    "SplitResult",
    "SentenceBlock",
    "SceneSegment",
    "SubtitleBlock",
]

__version__ = "0.1.0"


# === 用法示例 ===
# 1. 最简调用（使用默认配置）
from splitter import SmartSentenceSplitter

splitter = SmartSentenceSplitter()
result = splitter.split("长文本内容...")

print(result.sentences)  # 语义句子列表
print(result.scenes)     # 场景段落列表
print(result.tier_used)  # 实际使用的 tier: tier2_semantic

# 2. 自定义配置
from splitter import SmartSentenceSplitter
from splitter.utils.config_loader import load_config

config = load_config("config/splitter.yaml")
splitter = SmartSentenceSplitter(config=config)
result = splitter.split(text)

# 3. 指定语言
config = {"language": "en", "enable_llm": False}
splitter = SmartSentenceSplitter(config=config)
result = splitter.split(english_text)
```

---

## 7. REST API 设计

```
POST /v1/split
Content-Type: application/json

Request:
{
  "text": "长文本内容...",
  "language": "auto",  // auto | zh | en | ja | mixed
  "config": {          // 可选，覆盖默认配置
    "scene": {
      "target_seconds": 6.0,
      "speech_rate": 1.0
    },
    "subtitle": {
      "min_chars_per_block": 8,
      "max_chars_per_block": 15
    }
  },
  "enable_era": true
}

Response:
{
  "sentences": [
    {
      "index": 0,
      "text": "句子1",
      "char_count": 12,
      "word_count": 8,
      "language": "zh",
      "tier": "tier2_semantic",
      "confidence": 0.85
    }
  ],
  "scenes": [
    {
      "segment_id": 0,
      "text": "...",
      "estimated_duration": 6.0,
      "target_words": 20,
      "era_info": {
        "era": "modern",
        "confidence": 0.82,
        "keywords": ["现代", "当代"]
      },
      "subtitles": [
        {
          "text": "字幕1",
          "display_order": 0,
          "start_time": 0.0,
          "duration": 1.5
        }
      ]
    }
  ],
  "tier_used": "tier2_semantic",
  "language": "zh",
  "total_duration": 60.0,
  "total_words": 200
}

GET /v1/health
Response: {"status": "ok", "version": "0.1.0"}

GET /v1/capabilities
Response: {
  "languages": ["zh", "en", "mixed"],
  "tiers_available": ["tier1_llm", "tier2_semantic", "tier3_rule"],
  "features": ["scene_segment", "subtitle_segment", "era_detect"]
}
```

---

## 8. CLI 设计

```bash
# 基本用法
sentence-splitter -i input.txt -o output.json

# 指定语言
sentence-splitter -i input.txt -o output.json --language en

# 启用 LLM tier
sentence-splitter -i input.txt -o output.json --enable-llm

# 自定义配置
sentence-splitter -i input.txt -o output.json --config my-config.yaml

# 输出 SRT 字幕
sentence-splitter -i input.txt -o output.srt --format srt

# 详细模式
sentence-splitter -i input.txt -o output.json --verbose

# 帮助
sentence-splitter --help
```

---

## 9. 配置系统

```yaml
# config/splitter.yaml

# ============ 全局 ============
language: "auto"  # auto | zh | en | ja | mixed
enable_era: false  # 是否启用时代检测
enable_llm: false  # 是否启用 LLM tier
min_tier: 2        # 最低允许的 tier: 1=LLM, 2=Semantic, 3=Rule

# ============ 多语言 ============
sentence_tokenizer:
  language: "auto"
  handle_abbreviations: true

  custom_abbreviations: []  # 用户扩展缩写词表

  language_specific:
    zh:
      tokenizer: "jieba"
      use_pos: true
      entity_protection: true
    en:
      tokenizer: "whitespace"
      use_pos: false
      abbreviation_table: "default_en"  # 内置 18 个
      quote_pairs: [["\"", "\""], ["'", "'"]]
      handle_ellipsis: true
      handle_em_dash: true
    ja:
      enabled: false

# ============ 场景级 ============
scene:
  target_seconds: 6.0
  base_words_per_second: 3.3
  speech_rate: 1.0
  min_words_per_segment: 10
  max_words_per_segment: 50
  enforce_sentence_boundary: true
  allow_single_sentence_overflow: true

# ============ 字幕级 ============
subtitle:
  min_chars_per_block: 8
  max_chars_per_block: 15
  punctuation_priority:
    - "。"
    - "！"
    - "？"
    - "；"
    - "，"
    - "."
    - "!"
    - "?"
    - ","
    - " "
    - "\n"
  time_calculation_method: "proportional"  # proportional | equal

# ============ LLM Tier ============
llm:
  provider: "openai"  # openai | xfyun | claude | custom
  model: "gpt-4o-mini"
  api_key_env: "OPENAI_API_KEY"
  base_url: null
  timeout: 30
  max_retries: 2
```

---

## 10. 技术选型理由

| 组件 | 选型 | 理由 |
|------|------|------|
| **Python 3.11+** | 你的现有代码就是 Python 3.11 | 生态一致 |
| **jieba** | 中文分词首选 | 35K stars，成熟，词性标注+用户词典 |
| **FastAPI** | REST API | 异步友好、自动 OpenAPI 文档 |
| **Streamlit** | 工作台 | 30 行做出能用的 UI |
| **Pydantic** | 数据模型 | FastAPI 原生支持，类型安全 |
| **PyYAML** | 配置 | 你的现有配置就是 YAML |
| **pytest** | 测试 | 行业标准 |
| **mcp** | MCP Server | Anaconda 官方 SDK |
| **ruff** | Lint + Format | 替代 flake8+black，速度快 10x |

**不选的方案**：
- ❌ HanLP：太重（200MB+），jieba 足够
- ❌ spaCy：英文强但中文弱
- ❌ HuggingFace Transformers：本地推理慢，LLM 走 API 更经济
- ❌ LangChain：过度抽象，对分句这种单点任务不必要

---

## 11. 性能指标

| 场景 | 性能目标 |
|------|---------|
| 10K 字 ÷ Tier 3 规则 | < 1s |
| 10K 字 ÷ Tier 2 TextTiling+jieba | < 5s（首次加载 jieba 词典） |
| 10K 字 ÷ Tier 1 LLM | < 30s（含 API 调用） |
| REST API 单次请求 | < 10s (Tier 2 路径) |
| 内存占用 | < 200MB (含 jieba 词典) |
| 启动时间 | < 2s (冷启动) |

---

## 12. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **jieba 首次加载慢** | 工作台启动延迟 | 懒加载，只在用 Tier 2 时加载 |
| **LLM API 不稳定** | Tier 1 失败 | 强制降级链 + 重试机制 |
| **多语言混排误判** | 分句错乱 | 段落级而非字符级检测 |
| **英文缩写表不全** | 部分缩写被误切 | 用户可扩展 + 默认 18 个覆盖 95% 场景 |
| **Streamlit 与核心库版本冲突** | 工作台跑不起来 | 独立 requirements.txt |
| **多线程安全** | 并发请求数据竞争 | Tier 链无状态，jieba 全局锁 |

---

## 13. 部署形态

| 形态 | 入口命令 | 端口 |
|------|---------|------|
| **Python SDK** | `from splitter import SmartSentenceSplitter` | - |
| **REST API** | `uvicorn splitter.api.rest_api:app` | 8000 |
| **CLI** | `sentence-splitter -i input.txt` | - |
| **MCP Server** | `python -m splitter.api.mcp_server` | stdio |
| **Streamlit 工作台** | `streamlit run workbench/app.py` | 8501 |

---

## 14. 与现有素材的集成

| 现有文件 | 集成位置 | 处理方式 |
|---------|---------|---------|
| `text_segmentation_module.py` | `src/splitter/scene_subtitle/` | 重构为 SceneSegmenter + SubtitleSegmenter |
| `era_detector_demo.py` | `src/splitter/era/detector.py` | 翻译为 Python 包，添加类型注解 |
| `config.yaml` | `config/splitter.yaml` | 扩展 multilingual 段 |

**代码迁移策略**：
1. v0.1: 把现有代码**直接搬过来**到新位置，加配置加载器
2. v0.2: 重构为接口符合新设计
3. v0.3: 加降级链
4. v0.4: 加多语言 + 时代检测

---

## 15. 验收标准（架构层）

- [ ] 核心库安装即用（`pip install -e .`）
- [ ] FastAPI 服务能起来（`uvicorn` 启动正常）
- [ ] Streamlit 工作台能访问（`http://localhost:8501`）
- [ ] CLI 能处理示例文件
- [ ] 单元测试覆盖率 > 80%
- [ ] `python -m splitter` 显示版本和可用能力
- [ ] 配置加载器支持 YAML + JSON

---

**版本**: v0.1.0
**变更**: 初始版本
**下一步**: 进入 v0.3 写 ARCH-002（三级降级链详细设计）和 ARCH-003（多语言详细设计）
