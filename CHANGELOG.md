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

