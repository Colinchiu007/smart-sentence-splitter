# smart-sentence-splitter — 测试规范

## TDD 流程

```
RED   → 在 tests/unit/ 下写失败测试
GREEN → 最小实现让测试通过
REFACTOR → 重构，保持测试通过
```

### 测试组织

```
tests/
+-- unit/                    # 单元测试
|   +-- test_zh_splitter.py
|   +-- test_en_splitter.py
|   +-- test_texttiling.py
|   +-- test_length_segmenter.py
+-- integration/             # 集成测试
    +-- test_v3.py           # 后处理器集成
    +-- test_v5.py           # REST API 集成
```

