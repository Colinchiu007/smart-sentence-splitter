# PM-PRD-v0.3 — 4 个竞品复用集成

**版本**: v0.3.0
**日期**: 2026-06-13
**作者**: PM (COO role)
**状态**: 待 CEO 签字

---

## 1. 背景

v0.2 已完成 TextTiling 主题分割 + 5 个即时复用点。本迭代聚焦**深化复用**：把 4 个竞品（HanLP / LAC / THULAC / FoolNLTK）分析中**未落地的高价值模式**集成进 v0.3，每个改动都是**已分析过**、**有具体出处**的成熟模式。

## 2. 复用功能清单（7 个）

| # | 复用点 | 来源 | 文件改动 | 工期 |
|---|--------|------|---------|------|
| **F1** | **AC 自动机升级** — `Match` dataclass + emit 合并 | FoolNLTK | `languages/zh/ac.py` 重构 | 0.3 天 |
| **F2** | **DAG+DP 加权合并** — Customization 用 jieba 思路 | FoolNLTK | `languages/zh/custom.py` 重写 | 0.3 天 |
| **F3** | **Lazy 模型加载** — 按需加载 | FoolNLTK/HanLP | `era/detector.py` 加 lazy | 0.2 天 |
| **F4** | **TextTiling 真实边界增强** — 单字/单 token 不再当边界 | 原创增强 | `texttiling/splitter.py` 调优 | 0.2 天 |
| **F5** | **Postprocessor 集成到 pipeline 主流** | THULAC | `pipeline.py` 加 chain 调用 | 0.3 天 |
| **F6** | **EraDetector 后处理器化** | HanLP MTL | 新增 `EraPostprocessor` | 0.3 天 |
| **F7** | **mode=precise 自动启用** + LLM Tier 接口预留 | LAC | `pipeline.py` + 新建 `tiers/tier1_llm.py` stub | 0.4 天 |
| | | | **总计** | **2.0 天** |

## 3. 详细设计

### F1: AC 自动机升级（来自 FoolNLTK `trie.py`）

**改动**：
```python
# 旧
def search(self, text) -> List[Tuple[int, int]]:

# 新
@dataclass
class Match:
    start: int
    end: int
    keyword: str

def search(self, text) -> List[Match]:  # 返回更结构化对象
```

**保留 fail 节点 emit 合并**（FoolNLTK 细节）— 当前 ac.py 是简化版 Trie。

### F2: DAG+DP 加权合并（来自 FoolNLTK `_mearge_user_words`）

**旧**：AC 搜索 + 简单合并区间
**新**：
1. 接受分词结果列表 + 用户词典
2. 构造 DAG：单字边 + 词典边 + 分词边（各有权重）
3. DP 选最大权重路径
4. 输出最优分词

**权重公式**：`weight × length`（FoolNLTK 启发式）

### F3: Lazy 模型加载（来自 FoolNLTK `_load_seg_model`）

```python
# 旧
def __init__(self):
    self.detector = EraDetector() if enabled else None

# 新
def get_detector(self):
    if self._detector is None:
        self._detector = EraDetector()
    return self._detector
```

### F4: TextTiling 真实边界增强

**问题**：当前 v0.2 边界检测要求 `min_text_length=100`，对短文本早退。
**改进**：
- 增加 `min_tokens=20`（按 token 而非字符数）
- 单字/双字 token 永远不当作边界
- 真正"少字即跳过"逻辑

### F5: Postprocessor 集成到 pipeline 主流（THULAC Postprocesser chain）

**当前**：postprocessor.py 写了但没接
**改动**：`pipeline.split()` 在分句后调用 `postprocessor_chain.run(result)`

### F6: EraDetector 后处理器化（HanLP MTL 思想）

**当前**：EraDetector 在 pipeline 中直接调用
**新**：包装为 `EraPostprocessor`（BasePostprocessor 子类），加入 chain

**HanLP 思想借鉴**：EraDetector 与分句分离但联合输出（同一 document 多任务）

### F7: mode=precise + LLM Tier 预留接口

```python
# mode 映射
"fast" → min_tier=3
"balanced" → min_tier=2 (默认)
"precise" → min_tier=1 + enable_topic_segmentation=True

# 新增 tiers/tier1_llm.py — LLM Tier 接口 stub
class LLMSplitter(BaseSentenceSplitter):
    """Tier 1 LLM 语义分句 (未来 v0.3.1 实现)"""
    language = "auto"
    tier = "tier1_llm"

    def is_available(self) -> bool:
        return False  # 暂未实现

    def split(self, text):
        raise NotImplementedError("v0.3.1 will implement")
```

## 4. 验收测试矩阵

| # | 测试 | 期望 |
|---|------|------|
| T1 | ac.py 返回 Match 对象 | 字段完整 |
| T2 | Customization DAG+DP 输出与 jieba 思路一致 | 选最大权重 |
| T3 | EraDetector 第一次访问才加载 | lazy 生效 |
| T4 | TextTiling 短文本 20 token 仍可工作 | 不过度早退 |
| T5 | Pipeline split() 自动跑 postprocessor chain | hook 上 |
| T6 | EraPostprocessor 替换直接调用 | 输出与原版一致 |
| T7 | mode=precise 自动启用 TextTiling | 配置驱动 |

## 5. 风险

| 风险 | 缓解 |
|------|------|
| F1 重构破坏现有 Customization | 保留 `adjust()` 接口签名兼容 |
| F5 postprocessor 失败导致 pipeline 失败 | try/except + 日志（已实现） |
| F6 EraPostprocessor 性能回退 | 只在 result.scenes 上做（句子级），不开分句级 |
| F7 LLM Tier 永远 is_available=False | 留好接口，等 v0.3.1+ 实现 |

## 6. 工期

| 日期 | 工作 |
|------|------|
| 6-13 PM | PM-PRD（本文件） |
| 6-13 晚 | F1-F4（半天，4 个文件改动） |
| 6-14 上午 | F5-F6（半天，2 个文件改动） |
| 6-14 下午 | F7（半天，新建 LLM Tier stub） + 文档同步 |
| 6-14 晚 | commit + tag v0.3.0 |

---

**下一步**：CEO 签字后进入 TDD 实现阶段。
