# AGENTS.md — PROJECT-012 AI Agent 开发指南

> 给后续 AI 协作（Claude Code / Codex / OpenCode 等）使用的工作流指南

## 🎯 项目概览

- **项目名**: Smart Sentence Splitter (智能语义分句引擎)
- **项目代号**: PROJECT-012
- **目标用户**: 内容创作者 + 开发者 + AI 工作流用户
- **核心价值**: 打通「文案→分句→字幕→逐句配图→轮播视频」自动化管线
- **当前版本**: v0.9.5
- **测试覆盖**: 330 个用例 100% 通过 + 9 skipped (无 PROJECT-011)

## 🏗️ 关键架构路径

```
src/splitter/
├── pipeline.py              ← 主编排入口 (SmartSentenceSplitter) — 集成 Postprocessor chain
├── core/
│   ├── base_splitter.py     ← 分句器抽象接口
│   ├── base_tokenizer.py    ← 分词器抽象接口
│   ├── tier_chain.py        ← 降级链编排
│   └── language_router.py   ← 多语言路由
├── languages/
│   ├── zh/                  ← 中文 (jieba + ac.py + custom.py)
│   │   ├── splitter.py      ← ChineseSplitter (EOS 窗口检测)
│   │   ├── tokenizer.py
│   │   ├── abbreviations.py
│   │   ├── ac.py            ← ACAutomaton (Match dataclass)
│   │   └── custom.py        ← Customization (adjust_dag)
│   └── en/                  ← 英文 (空白分词)
├── tiers/
│   ├── tier1_llm.py         ← v0.4 完整实做 (3 Provider)
│   └── tier3_rule.py
├── texttiling/              ← 主题分割算法
├── scene_subtitle/          ← Layer 2 + 3
├── era/
│   ├── detector.py
│   └── postprocessor.py     ← v0.3 EraPostprocessor (lazy)
├── postprocessor.py         ← v0.2 → v0.3 增强 (chain 集成到 pipeline)
├── llm/                      ← v0.4 LLM Tier Provider 抽象
│   ├── base.py
│   ├── openai_provider.py
│   ├── xfyun_provider.py
│   ├── ollama_provider.py
│   └── prompts.py
├── script/                     ← v0.7 新增 (剧本分析)
│   └── script_analyzer.py      ← 角色/场景/梗概/场景变化检测
├── models/                  ← 5 个 dataclass (SceneSegment 扩展)
├── api/
│   ├── cli.py
│   └── rest_api.py        ← v0.5 新增 (FastAPI)
├── workbench/                  ← v0.5 新增 (Streamlit)
│   └── app.py
└── utils/
```

## 📐 重要约定

### 1. 修改代码前
- ✅ 必读对应模块的现有测试文件 (`tests/unit/test_*.py`)
- ✅ 必读 PRD/ARCH 中对应章节
- ❌ 不要绕过 Tier 链直接调用具体 splitter

### 2. 命名规范
- **类名**: `PascalCase` (e.g. `SmartSentenceSplitter`, `ChineseSplitter`)
- **函数/变量**: `snake_case` (e.g. `split_text`, `is_available`)
- **常量**: `UPPER_SNAKE_CASE` (e.g. `ZH_CLAUSE_BOUNDARIES`, `EN_ABBREVIATIONS`)
- **私有方法**: 前缀 `_` (e.g. `_split_by_punctuation`)
- **测试文件**: `test_<module>.py`
- **测试函数**: `test_<行为>_当_<条件>_则_<结果>`

### 3. 抽象接口不可改
- `BaseSentenceSplitter.split()` 签名不能改
- `BaseTokenizer.tokenize()` 签名不能改
- 如需扩展，添加新方法 or 引入新接口

### 4. 数据模型变更流程
1. 在 `src/splitter/models/*.py` 修改 dataclass
2. 同步更新 `to_dict()` / `from_dict()` 方法
3. 更新所有使用该模型的下游代码 (scene/subtitle/era/pipeline)
4. 更新测试断言
5. 更新 PRD 数据模型章节

### 5. 新增分句器流程
1. 继承 `BaseSentenceSplitter`
2. 实现 `split()` + `is_available()`
3. 设置 `language` 和 `tier` 类属性
4. 注册到 `TierChain.splitters` 列表
5. 写测试 (`tests/unit/test_<your_splitter>.py`)
6. 更新 CHANGELOG

### 6. 新增语言包流程
1. 在 `src/splitter/languages/<lang>/` 创建目录
2. 实现 `tokenizer.py` + `splitter.py` + `abbreviations.py`
3. 在 `LanguageRouter` 添加路由分支
4. 在 `pipeline.py` 添加该语言的 splitter 实例
5. 写测试
6. 更新 `config/splitter.yaml` 的 `language_specific` 段
7. 更新 README 多语言支持表格

### 7. 新增 Postprocessor 流程（v0.3+）
1. 继承 `BasePostprocessor`
2. 实现 `adjust(result) -> result`（返回新 SplitResult 或原地修改）
3. 实现 `is_available() -> bool`（依赖检查）
4. 在 `SmartSentenceSplitter._init_postprocessors()` 中注册
5. 写测试 (`tests/integration/test_v3.py` 或新文件)
6. 失败不应影响主流程（在 chain.run() 内部 try/except）
7. 更新 CHANGELOG

### 8. 新增长度策略流程（v0.6+）
1. 修改 `LengthSegmenter` 时不影响默认 B 模式行为
2. 3 种策略: off / A (重切) / B (标尺, 默认)
3. A 模式算法: 贪心在 `max_chars` 范围内找最右标点切；无标点按 max_chars 硬切
4. B 模式算法: 不切，只打 `length_status` 标签 (ok/too_short/too_long)
5. 配置段: `length.strategy/min_chars/max_chars/prefer_punctuation/warning_on_violation`
6. 数据模型字段: `SentenceBlock.length_status` + `length_strategy_applied` (有默认值, 兼容旧代码)
7. Pipeline 集成点: 步骤 6.5 (分句后, 场景前)
8. 写测试 (`tests/unit/test_length_segmenter.py`)

## 🧪 测试命令

```bash
# 全部测试
python -m pytest tests/

# 单元测试
python -m pytest tests/unit/

# 集成测试
python -m pytest tests/integration/

# 特定模块
python -m pytest tests/unit/test_zh_splitter.py -v

# 详细输出
python -m pytest tests/ -v --tb=short

# 跑通即止（快速验证）
python -m pytest tests/ -q
```

## 🚀 常用开发命令

```bash
# 装包
pip install -e .                  # 仅核心
pip install -e ".[semantic]"      # 含 jieba
pip install -e ".[all]"           # 全量

# CLI 测试
sentence-splitter -i examples/sample_zh.txt --enable-era
sentence-splitter -i examples/sample_en.txt --language en

# 跑示例
python examples/sdk_usage.py

# 安装验证
python -c "from splitter import SmartSentenceSplitter; print('OK')"
```

## 📋 验证清单（提交前）

- [ ] 所有测试通过 (`pytest tests/`)
- [ ] 没有新增 lint 错误
- [ ] CHANGELOG 已更新
- [ ] README 特性列表已同步
- [ ] PRD 数据模型章节已同步（如有模型变更）
- [ ] 新增功能有对应测试
- [ ] 现有测试未被破坏

### 🎯 当前迭代重点

### v0.7 (✅ 完成)
- ScriptAnalyzer 剧本分析 (角色/场景/梗概/场景变化)
- SceneSegment 扩展 (characters/setting/mood/story_phase)
- StoryboardExporter 分镜 JSON 输出
- Pipeline 集成 (enable_script_analysis)
- 295 个测试 (v0.7.0 290 + v0.7.1 5)

### v0.8 (✅ 完成)
- SubtitleExporter (SRT + ASS 双格式)
- PromptEngineClient (PROJECT-011 HTTP 桥接)
- Storyboard 全流程端到端实测
- 312 个测试 (v0.7.1 295 + v0.8 新增 17)

### v0.9 (✅ 完成)
- 工作台四合一 (分句/字幕/分镜/提示词)
- Context 注入 (synopsis/character/setting → PROJECT-011)
- A 模式配对引号保护 (《》「」() 等)
- 场景检测修复 (单字后缀误报)
- 324 个测试 (v0.8.2 316 + v0.9.x 新增 8)

## 🐛 常见问题 (FAQ)

### Q: 修改 SentenceBlock 后输出 JSON 不一致？
A: 同步更新 `to_dict()` 方法和 `SplitResult.to_dict()` 引用。

### Q: 中文分词慢？
A: jieba 首次加载需 ~1s（构建前缀词典）。生产环境用 `python -m splitter.api.cli` 启动后保持进程长驻。

### Q: 英文缩写被误切？
A: 缩写表是否覆盖？可在 `EN_ABBREVIATIONS` 添加自定义词，或在 config 中通过 `custom_abbreviations` 扩展。

### Q: Tier 链不降级？
A: 检查 `is_available()` 是否正确实现 + 抛出的异常是否被 `TierChain.split()` 捕获。

### Q: 添加新语言后 pipeline 路由不到？
A: 检查 `LanguageRouter.route()` 的分支是否覆盖新语言 + `pipeline.py` 是否实例化对应 splitter。

## 📚 关联文档

- [PRD.md](../PRD.md) — 产品需求
- [ARCHITECTURE.md](ARCHITECTURE.md) — 架构设计
- [CHANGELOG.md](CHANGELOG.md) — 更新日志
- [README.md](../README.md) — 项目主文档

---

**最后更新**: 2026-06-13
**AI 协作规范**: professional-ai-coding-workflow v1.5.0
