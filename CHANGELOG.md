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

