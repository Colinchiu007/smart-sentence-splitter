# PROJECT-012 — 智能语义分句引擎

[![Version](https://img.shields.io/badge/version-0.1.0-blue)]()
[![Python](https://img.shields.io/badge/python-3.11+-green)]()
[![License](https://img.shields.io/badge/license-MIT-yellow)]()

> 按语义完整性和字数约束自动切割文本，输出结构化分句数据 — 字幕生成 / 逐句生图 / 视频合成的统一入口

## ✨ 核心特性

- 🧠 **三级分句降级链** — LLM (Tier 1) → TextTiling+jieba (Tier 2) → 规则 (Tier 3)
- 🤖 **3 个 LLM Provider** — OpenAI / 讯飞 MAAS / Ollama（v0.4）
- 🌍 **多语言原生支持** — 中文 (jieba 增强) + 英文 (缩写+引号保护) + 中英混排路由
- 🪶 **零依赖核心** — 仅 `pydantic` + `PyYAML`，jieba/streamlit/fastapi 全部 optional
- 🪡 **AC 自动机用户词典** — O(n) 多模式匹配 + DAG+DP 加权合并 (FoolNLTK/LAC 复用)
- ⚙️ **全配置化** — 全部参数 YAML 可配，运行时热更新
- 🪡 **Postprocessor 链** — EraPostprocessor / CustomMergingProcessor 可插拔 (THULAC/HanLP 复用)
- 🎬 **下游友好输出** — 标准化 JSON (sentences/scenes/subtitles/era_info) 直接对接字幕/生图/视频
- 🚀 **3 模式** — `fast` / `balanced` / `precise` (LAC 复用)

## 🚀 快速开始

### 安装

```bash
# 核心库（仅 pydantic + PyYAML）
pip install -e .

# 含语义分句（jieba）
pip install -e ".[semantic]"

# 全量安装
pip install -e ".[all]"
```

### 30 秒上手

```python
from splitter import SmartSentenceSplitter

splitter = SmartSentenceSplitter()
result = splitter.split("今天天气真好。我们去公园散步。路上遇到了朋友。")

for s in result.sentences:
    print(f"[{s.index}] {s.text}")

for scene in result.scenes:
    print(f"Scene {scene.segment_id}: {scene.text[:30]}... "
          f"({scene.estimated_duration:.1f}s)")
```

### CLI 用法

```bash
# 文件输入
sentence-splitter -i input.txt -o output.json

# 英文输入
sentence-splitter -i input.txt -o output.json --language en

# 启用时代检测（中文）
sentence-splitter -i input.txt -o output.json --enable-era

# 自定义配置
sentence-splitter -i input.txt -o output.json --config my-config.yaml

# 管道输入
cat input.txt | sentence-splitter --language auto
```

## 📊 输出格式

```json
{
  "sentences": [
    {
      "text": "今天天气真好。",
      "index": 0,
      "char_count": 7,
      "word_count": 3,
      "words": ["今天天气", "真", "好", "。"],
      "pos_tags": ["n", "d", "a", "x"],
      "language": "zh",
      "tier": "tier2_semantic",
      "confidence": 1.0
    }
  ],
  "scenes": [
    {
      "segment_id": 0,
      "text": "今天天气真好。我们去公园散步。",
      "estimated_duration": 4.5,
      "target_words": 15,
      "era_info": {
        "era": "modern",
        "confidence": 0.6,
        "keywords": ["今天"]
      },
      "subtitles": [
        {
          "text": "今天天气真好。",
          "display_order": 0,
          "start_time": 0.0,
          "duration": 1.5
        }
      ]
    }
  ],
  "tier_used": "tier2_semantic",
  "language": "zh",
  "total_duration": 7.0,
  "total_words": 23,
  "total_scenes": 2
}
```

## 🏗️ 架构

```
输入文本 → LanguageRouter → TierChain → SceneSegmenter → SubtitleSegmenter → EraDetector → JSON
            (多语言路由)    (三级降级)   (场景分割)        (字幕分割)         (时代检测)
```

详细架构见 [`docs/ARCH-001-architecture.md`](docs/ARCH-001-architecture.md)

## 🌍 多语言支持

| 语言 | 优先级 | 分词器 | 缩写词表 | 状态 |
|------|--------|--------|---------|------|
| 中文 (zh) | P0 | jieba | 内置 16 个 | ✅ |
| 英文 (en) | P0 | 空白分词 (零依赖) | 内置 35+ 个 | ✅ |
| 中英混排 (mixed) | P0 | 双语切换 | 全部 | ✅ |
| 日文 (ja) | P2 | fugashi (待集成) | — | 🚧 |

**缩写保护示例**：
- `Dr. Smith 和 Mr. Wang 在 U.S. 工作` → 不在缩写点切分
- `He said "Hello." Then left.` → 引号内句号不切
- `He thought... and left.` → 省略号视为 1 个边界

## ⚙️ 配置

完整配置见 [`config/splitter.yaml`](config/splitter.yaml)。核心参数：

```yaml
language: "auto"              # auto | zh | en | ja | mixed
min_tier: 2                   # 1=LLM, 2=Semantic, 3=Rule
enable_era: false             # 时代检测（仅中文）

scene:
  target_seconds: 6.0         # 6秒一段
  base_words_per_second: 3.3  # 中文语速
  speech_rate: 1.0
  min_words_per_segment: 10
  max_words_per_segment: 50

subtitle:
  min_chars_per_block: 8      # 字幕块下限
  max_chars_per_block: 15     # 字幕块上限
  time_calculation_method: "proportional"
```

## 🧪 测试

```bash
# 全部测试
python -m pytest tests/

# 仅单元测试
python -m pytest tests/unit/

# 详细模式
python -m pytest tests/ -v

# 当前测试数：216 ✅
```

## 📚 文档

- [PRD.md](docs/PRD.md) — 产品需求文档
- [ARCH-001-architecture.md](docs/ARCH-001-architecture.md) — 整体架构
- [CHANGELOG.md](docs/CHANGELOG.md) — 更新日志
- [AGENTS.md](docs/AGENTS.md) — AI Agent 开发指南

## 🛠️ 开发

```bash
# 项目结构
src/splitter/
├── core/              # 抽象接口 + 降级链 + 路由
├── languages/         # zh / en / ja 语言包
├── tiers/             # tier1_llm / tier2_semantic / tier3_rule
├── scene_subtitle/    # Layer 2 + 3
├── era/               # 时代检测
├── api/               # CLI / REST / MCP
├── models/            # 数据模型
├── pipeline.py        # 主编排
└── utils/             # 配置/序列化/语言检测

# 添加新功能流程
# 1. 写测试 (RED)
# 2. 写实现 (GREEN)
# 3. 同步更新 CHANGELOG
# 4. 提交
```

## 📋 版本

当前版本：**v0.4.0** (2026-06-13)

完整历史见 [CHANGELOG.md](docs/CHANGELOG.md)

## 📄 许可证

MIT License
