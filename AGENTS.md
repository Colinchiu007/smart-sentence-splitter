# smart-sentence-splitter — 开发流程规范

> 智能语义分句引擎的开发流程与编码约定。AI 工具启动时自动读取。
> 详细技术参考见 `docs/AGENTS.md`。

---

## 核心原则

1. **TDD**：测试先于代码，提交前所有测试通过
2. **先文档再代码**：没有 PRD 不动手，没有架构设计不动手
3. **抽象接口不可改**：`BaseSentenceSplitter.split()`、`BaseTokenizer.tokenize()` 签名不可变
4. **降级链不绕过**：不要绕过 Tier 链直接调用具体 splitter
5. **向后兼容**：数据模型变更必须有迁移路径

## AI 角色分工

| 角色 | 阶段 | 产出物 |
|------|------|--------|
| **PM** | 需求分析 | PRD、分句策略、多语言支持需求 |
| **架构师** | 技术设计 | Tier 链设计、语言包架构、降级策略 |
| **开发工程师** | 编码实现 | 分句器/分词器/后处理器 + 测试（TDD） |
| **QA** | 质量验证 | 分句准确率测试、多语言测试 |
| **CTO** | 代码评审 | 分句逻辑正确性、降级链完整性 |

## 7 阶段开发流程

### 阶段 1：想法澄清
确认：分句策略类型、新增语言/后处理器/分析器、Tier 链位置

### 阶段 2：PRD（PM）
产出：PRD，包含 P0/P1/P2 功能、分句规则、验收标准
**批准后才能进入下一阶段。**

### 阶段 3：技术设计（架构师）
产出：方案对比 + 推荐方案
- 新增分句器：继承 `BaseSentenceSplitter`，注册到 `TierChain`
- 新增语言包：在 `languages/<lang>/` 实现 splitter + tokenizer + abbreviations
- 新增后处理器：继承 `BasePostprocessor`，注册到 pipeline
- 详细流程见 `docs/AGENTS.md`

### 阶段 4：开发计划（PM）
MVP 拆成 ≤4h 的任务。

### 阶段 5：编码实现（开发 + TDD）
- 先写测试，再写代码
- 测试覆盖：正常分句 / 边界值 / 多语言 / 降级 / 异常输入
- 手动验证：CLI 示例 + API 请求

### 阶段 6：代码评审（CTO）
必检项：
- 🔴 抽象接口签名是否被修改
- 🔴 Tier 链是否被绕过
- 🟠 数据模型是否向后兼容
- 🟠 失败不影响主流程（后处理器 try/except）
- 🟢 新功能是否注册到 pipeline
- 🟢 CHANGELOG 是否更新

### 阶段 7：发布
- 所有测试通过（`pytest tests/`）
- 更新 CHANGELOG.md
- 更新 README 特性列表
- git 提交并 tag

## 质量门禁

**PRD 阶段**：分句策略明确 / 多语言范围清晰 / 验收标准可验证
**设计阶段**：Tier 链设计完整 / 最简单方案
**开发阶段**：测试全通过 / 手动验证核心功能 / 降级链验证
**Review 阶段**：CRITICAL 问题已修复 / 接口兼容性

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

## 提交规范

```
feat(zh): 新增中文间接问句分句规则
fix(tier): 修复 LLM Tier 超时不降级
docs: 更新 PRD 分句策略章节
refactor: 统一 postprocessor 注册方式
```

## 文档清单

| 文件 | 路径 | 说明 |
|------|------|------|
| AGENTS.md | `./AGENTS.md` | 本文件，开发流程规范 |
| docs/AGENTS.md | `./docs/AGENTS.md` | 完整技术开发指南 |
| CLAUDE.md | `./CLAUDE.md` | 项目上下文和开发命令 |
| .clinerules | `./.clinerules` | 硬约束规则 |
| PRD.md | `./docs/PRD.md` | 产品需求文档 |
| ARCHITECTURE.md | `./docs/ARCHITECTURE.md` | 架构设计文档 |
| CHANGELOG.md | `./CHANGELOG.md` | 变更日志 |
| USAGE_GUIDE.md | `./docs/USAGE_GUIDE.md` | 使用指南 |

## 常用命令

```bash
# 全部测试
python -m pytest tests/

# 单元测试
python -m pytest tests/unit/

# 集成测试
python -m pytest tests/integration/

# 安装
pip install -e ".[all]"

# 启动 REST API
uvicorn splitter.api.rest_api:app --reload --port 8002
```

## 版本

**v0.9.10** — 344 测试 100% 通过。上下游均已集成。
