---
name: smart-sentence-splitter-design
description: smart-sentence-splitter DESIGN.md — 设计文档
---

# Smart Sentence Splitter — 设计文档

> **版本**: v0.9.10 | **更新**: 2026-07-01
> **关联**: docs/ARCHITECTURE.md, docs/PRD.md

## 一、核心设计原则

### 1.1 设计目标

- **规则优先，LLM 辅助**：80% 场景无需 LLM 调用，规则引擎可在 45ms 内完成 10K 字符分句
- **渐进式精度**：从纯规则 → jieba 分词 → TextTiling → LLM，精度逐级提升但成本递增
- **零配置开箱即用**：纯规则模式无需任何外部依赖即可工作

### 1.2 三层递进架构（Tier Chain）

```
输入文本
   │
   ├── Tier 0: 纯规则引擎（<1ms）
   │   ├── 中文标点分割（。/！/？/；）
   │   ├── 英文句点分割（. 后跟大写或换行）
   │   ├── 引号/括号边界保护
   │   └── 缩写白名单（Mr./Dr./U.S. 等）
   │
   ├── Tier 1: 语义增强（~50ms）
   │   ├── jieba 分词 → 句边界概率模型
   │   └── TextTiling 算法 → 主题边界检测
   │
   └── Tier 2: LLM 精分（~1-3s）
       ├── Prompt-based 语义分句
       └── 仅在前两轮结果置信度 < 阈值时触发
```

### 1.3 LanguageRouter

自动检测输入语言并选择对应策略：

| 语言 | 检测方式 | 主要分割符 | 特殊处理 |
|------|---------|-----------|---------|
| 中文 | CJK 字符比例 | 。！？； | 引号/书名号保护 |
| 英文 | 字母比例 > 80% | . ! ? | 缩写白名单 |
| 日文 | 假名字符比例 | 。！？・ | 分かち書き |

### 1.4 Scene & Subtitle 分组

分句后的进阶处理，面向视频生成场景：

| 分组级别 | 说明 | 触发条件 |
|---------|------|---------|
| Scene | 场景分组 | TextTiling 主题边界 + 时间戳(SSE模式) |
| Subtitle | 字幕分组 | 句长 + 语义完整性 + 字幕时长约束 |

---

## 二、性能设计

### 2.1 大文本分块策略（`_handle_large_text`）

| 指标 | 值 |
|------|-----|
| max_input_length | 200K 字符 |
| 分块大小 | 50K 字符（重叠 1K）|
| 10K chars ~45ms | Tier 0 纯规则 |
| 200K chars ~1.2s | Tier 0 + Tier 1 |
| SSE 首包延迟 | <100ms（流式输出） |

### 2.2 SSE 流式端点设计

```
POST /v1/split/stream
  → 立即返回 text/event-stream
  → 每分完一个完整句发送 data: {"sentence": "...", "index": N}
  → 全部完成后发送 data: [DONE]
  
收益：200K 文本首句 +100ms 即可输出，无需等全部完成
```

---

## 三、API 设计

| 端点 | 方法 | 输入 | 输出 |
|------|------|------|------|
| `/split` | POST | `{"text": "..."}` | `{"sentences": [...]}` |
| `/v1/split` | POST | `{"text": "..."}` | `{"sentences": [...], "tier_used": 0/1/2}` |
| `/v1/split/stream` | POST | `{"text": "..."}` | SSE `text/event-stream` |
| `/health` | GET | — | `{"status": "ok"}` |

---

## 四、测试策略

| 层级 | 覆盖 | 数量 |
|------|------|------|
| 单元测试 | 各 Tier 分句逻辑 | ~200 |
| 语言路由 | 中/英/日/混合 | ~50 |
| 边界测试 | 空文本/长文本/特殊字符 | ~40 |
| SSE 端点 | 流式输出/中断/错误 | ~30 |
| 性能测试 | 10K/50K/200K 延迟 | ~15 |
