## [0.10.0] - 2026-06-30

### 🚀 v0.10.0 — 大文本分块改进 + SSE 流式分句

#### 大文本分块策略改进

- **max_input_length 默认值**: 50K → 200K（config_loader.py + pipeline.py）
- **更全面的句子边界字符**: 新增英文句点 `.` / 换行 `\n` / 省略号 `…`
- **无标点硬回退**: 无句子边界时按 max_length 字符硬切，避免递归溢出
- **超大块子分块**: 单个句子块超过 max_length 时内部硬切，彻底消除 RecursionError
- **安全阀**: 递归时跳过与父文本相同或更大的块，防止死循环

#### SSE 流式分句端点

- **新增 `POST /v1/split/stream`**: SSE (text/event-stream) 协议
- **事件类型**:
  - `event: progress` — 大文本分块进度（chunk_index, chunks_total, sentences_so_far）
  - `event: result` — 最终完整 SplitResponse JSON
  - `event: error` — 错误信息
- 小文本（≤max_input_length）直接返回单个 result 事件
- 大文本按块处理，每完成一块推送一次进度，最后合并推送完整结果

#### 📊 测试

- 新增 6 个 SSE 流式测试 + 11 个大文本分块测试 = **365 passed + 9 skipped** ✅

## [0.9.10] - 2026-06-14

### 🚀 v0.9.10 — 语义段落检测优化

#### TextTiling 句级算法

从字符级窗口改为**句级窗口**:

- `tokenize()`: 中文按字符分词, 过滤停用字 (的/了/在/是 等 40+)
- `tile_by_sentences()`: 句级滑动窗口 (默认 3 句), 步长 1
- 深度评分基于相邻 tile 余弦相似度变化, 默认阈值 0.15
- `_identify_boundaries()`: 局部极大值 + 相对阈值 (max_depth * 0.3)
- `find_boundaries()` 旧接口保留向后兼容

#### SceneSegmenter 主题边界感知

- 优先按 `is_topic_boundary` 切场景, 字数切降级为次要约束
- 有 topic 边界时有效字数阈值自动 3x (减少碎片化)
- 12 句测试: 旧→11 场景, 新→5 场景 (4 个语义段落)

#### 🎯 效果对比

| 指标 | 旧 (v0.9.9) | 新 (v0.9.10) |
|------|------------|-------------|
| 4 话题测试场景数 | 11 | 5 |
| 中文分词 | 空白切分 (1 token) | 字符级 (133 tokens) |
| 窗口粒度 | 字符级 | 句级 |
| 平滑 | 2 passes (信号衰减) | 0 passes |

#### 📊 测试

- **总计: 353 passed + 9 skipped** ✅ (无新增测试, 核心算法重构)

---

## [0.9.9] - 2026-06-14

### ✨ v0.9.9 — 日语分句支持 (JapaneseSplitter)

#### 新增

- **日语 Splitter**: `src/splitter/languages/ja/splitter.py`
  - 按句点/感叹号/问号/换行分割
  - 配对引号内标点保护 (「」『』（）〔〕)
  - TierChain 集成 + 自动语言检测路由

- **日语语言包架构**: `languages/ja/__init__.py` + `__init__.py`
  - `LanguageRouter` 自动路由 `"ja" → JapaneseSplitter`
  - `pipeline.py` 新增 `_ja_chain` TierChain
  - `detect_language` 已有假名检测 (kana_ratio > 0.1)

#### 新增文件

```
src/splitter/languages/ja/
├── __init__.py
└── splitter.py          # JapaneseSplitter (2.8KB)

tests/unit/test_ja_splitter.py  # 7 个测试
```

#### 📊 测试

- 新增 7 个日语分句测试
- **总计: 353 passed + 9 skipped** ✅

---

## [0.9.8] - 2026-06-14

### ✨ v0.9.8 — 多剧本管理面板 + 对比功能

#### 新增

- **工作台 📂 剧本管理侧栏** — 保存/切换/删除多个剧本
  - session_state 持久化存储
  - 快速切换剧本，保留上次分句结果
  - 保存新剧本时自动捕捉当前输入文本

- **🔄 对比模式** — 两个剧本分句结果并排对比
  - 分句对比 tab: 句子数/文本差异
  - 场景对比 tab: 场景数/时长差异
  - 自动检测句子数不一致

- **代码重构**: 分句结果渲染抽取为 `_render_*` 函数族
  - `_render_script_analysis()` / `_render_sentences()` / `_render_subtitles()` 等
  - 对比模式复用同一渲染函数

#### 📊 测试

- 新增 2 个工作台测试 (多剧本管理 + 对比功能)
- **总计: 346 passed + 9 skipped** ✅

---

## [0.9.7] - 2026-06-14

### 🚀 v0.9.7 — 性能基线扩展 + Fuzz 测试

#### 性能基线
- 新增 2 级: 100KB < 10s, 1MB < 60s (无内存爆炸)
- 实测: 100KB → 418ms, 1MB → 5.8s (远超阈值)

#### Fuzz 测试 (test_fuzz.py)
- 随机中文/英文/混排文本生成器 (30轮)
- 17 个极端场景: 空/纯标点/超长词/纯重复/纯换行等
- 三种模式 (fast/balanced/precise) 覆盖
- 三种字数策略 (A/B/off) 覆盖
- 启用脚本分析时极端场景覆盖

#### 📊 测试
- 新增 9 个测试 (4 性能 + 5 fuzz)
- **总计: 344 passed + 9 skipped** ✅

---
## [0.9.6] - 2026-06-14

### ✨ v0.9.6 — REST API 批量接口 (POST /v1/split/batch)

#### 新端点

`POST /v1/split/batch` — 一次请求处理多段文本:

```json
{
  "texts": ["今天天气真好。", "Hello world."],
  "config": {"mode": "fast"}
}
→ {"results": [SplitResult, SplitResult]}
```

#### 变更

- `rest_api.py`: 新增 `SplitBatchRequest` / `SplitBatchResponse` 模型 + endpoint
- 复用 `SmartSentenceSplitter` 实例 (统一配置, 避免重复构建)
- 空文本返回空 `SplitResponse` (保持索引对应)
- `openapi.json` 自动注册 `/v1/split/batch`

#### 📊 测试

- 新增 5 个测试 (test_rest_api.py: TestSplitBatch)
- **总计: 335 passed + 9 skipped** ✅

---

## [0.9.5] - 2026-06-14

### 🚀 v0.9.5 — 脚本分析角色提取增强

#### 改进

- **角色提取 v2**: 引入频率阈值 + 通用名词过滤 + 过渡动词补充
  - 新 `CHARACTER_TRANSITION_VERBS` (走进/离开/打开等) 作为额外角色信号
  - `STOP_MULTI_WORDS` 过滤 "我们/你们/他们" 等代词
  - `COMMON_NOUN_FALSE_NR` 过滤 "老师/学生/医生" 等通用名词误判
  - 信号词正则缩减为 2-3 字捕获, 避免 "红走进来"→"红走进" 假阳性
- `_is_valid_location`: 2 字地点 (公园/超市) 不再被过滤
- **新文件**: `examples/end_to_end.py` 端到端示例脚本

#### 📊 测试

- 新增 5 个测试用例覆盖增强逻辑
- **总计: 330 passed + 9 skipped** ✅

---

## [0.9.3] - 2026-06-14

