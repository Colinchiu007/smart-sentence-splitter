# PM-PRD-v0.2 — TextTiling 主题分割

**版本**: v0.2.0
**日期**: 2026-06-13
**作者**: PM (COO role)
**关联**: PRD v0.2.0 (主项目), F-03 功能专项

---

## 1. 背景与目标

### 1.1 现状（v0.1 的局限）

v0.1 的 Tier 2 分句器（ChineseSplitter）只用了 jieba 分词+词性标注，但**没有真正理解主题边界**：
- 长段落（> 200字）内多个主题切换时，规则分句器按标点切，可能在同一个主题中切断
- 多主题文章（如"中国历史 → 转到现代科技 → 转到未来展望"）整体被当作一个段落，**场景分割**会把多主题内容混到一段视频里
- 用户场景：内容创作者做视频时，希望每段视频只讲一个主题

### 1.2 v0.2 目标

实现 **TextTiling 主题分割**（Tier 2 升级），让分句器在长段落中**识别主题边界**：
- 在主题转换点处插入次级分句标记
- 输出 `SentenceBlock.tier = "tier2_semantic"`（带 `is_topic_boundary=True`）
- 让下游场景分割器**优先在主题边界处切分**

## 2. TextTiling 算法简介

TextTiling 是 Hearst (1997) 提出的无监督主题分割算法。核心思想：

1. **分块（Tokenization）** — 把文本切成 N 个 token
2. **滑动窗口** — 用 k 个 token 组成一个 tile
3. **相似度计算** — 相邻 tile 之间的词汇相似度（余弦 / Jaccard）
4. **深度评分（Depth Score）** — 每个 tile 与左右邻居的相似度落差
5. **边界识别** — 局部极大值 = 主题边界

**优势**：
- ✅ 无监督，无需训练数据
- ✅ 语言无关（基于词汇分布，不依赖语法）
- ✅ 零外部依赖（纯 Python + stdlib）

**局限**：
- ⚠️ 短文本（< 100 词）效果差（窗口不够）
- ⚠️ 需要合理的窗口大小（w = 20 是经验值）
- ⚠️ 中文需要先分词（jieba 处理后调用 TextTiling）

## 3. v0.2 功能需求

### 3.1 P0 必做（核心）

| 编号 | 功能 | 描述 | 验收标准 |
|------|------|------|---------|
| **F2-01** | **TextTiling 算法实现** | 滑动窗口 + 余弦相似度 + 深度评分 | 单测覆盖：算法核心 4 步 |
| **F2-02** | **中英文支持** | 中文用 jieba 预分词，英文空白分词 | 输入中文/英文，输出主题边界列表 |
| **F2-03** | **边界标记** | 在边界处插入 `is_topic_boundary=True` 的虚拟 SentenceBlock | 下游 SceneSegmenter 优先在边界切分 |
| **F2-04** | **SentenceSplitter 接口适配** | 实现 `BaseSentenceSplitter.split()` | 集成到 TierChain，tier 标识 `tier2_semantic` |
| **F2-05** | **降级链** | jieba/算法异常时降级到 Tier 3 规则 | 异常不中断 pipeline |

### 3.2 P1 增强

| 编号 | 功能 | 描述 |
|------|------|------|
| F2-06 | 可配置窗口大小 | `w=20` 默认，支持 10-50 调节 |
| F2-07 | 边界阈值 | `depth_score_threshold` 默认 0.3 |
| F2-08 | 短文本早退 | 文本 < 100 字符时直接返回原句不切分 |

## 4. 算法详细设计

### 4.1 核心数据结构

```python
@dataclass
class TopicBoundary:
    """主题边界标记"""
    position: int          # 在 token 列表中的位置
    depth_score: float     # 深度评分 0-1
    confidence: float      # 置信度 0-1
    text_before: str       # 边界前 30 字符（调试用）
    text_after: str        # 边界后 30 字符
```

### 4.2 算法步骤

```
输入: tokens: List[str], window_size: int = 20
输出: List[TopicBoundary]

Step 1: 构建 tile 序列
  - tiles = [tokens[i:i+w] for i in range(0, len(tokens)-w, w//2)]
  - 重叠窗口（步长 = w//2）保证边界不漏

Step 2: 向量化（词袋模型）
  - vocab = {token: idx for idx, token in enumerate(unique_tokens)}
  - tile_vectors = [Counter(tokens) → sparse vector]

Step 3: 相邻 tile 相似度
  - sims[i] = cosine_similarity(tile_vectors[i], tile_vectors[i+1])
  - 长度 = len(tiles) - 1

Step 4: 深度评分
  - depth[i] = (sims[i-1] - sims[i]) + (sims[i+1] - sims[i])
            = sims[i-1] + sims[i+1] - 2*sims[i]
  - 即当前点比左右邻居低多少

Step 5: 边界识别
  - boundaries = [i for i, d in enumerate(depth) if d > threshold]
  - 局部极大值

Step 6: 边界 → 文本位置
  - boundary_token_pos = tile[i].start
  - 转换为字符 offset
```

### 4.3 关键参数

| 参数 | 默认值 | 范围 | 说明 |
|------|--------|------|------|
| `window_size` (w) | 20 | 10-50 | 滑动窗口 token 数 |
| `step_size` | w // 2 | - | 滑动步长（重叠率 50%） |
| `depth_score_threshold` | 0.3 | 0.1-0.8 | 深度评分阈值 |
| `min_text_length` | 100 字符 | - | 短文本早退阈值 |
| `smoothing_passes` | 1 | 0-3 | 相似度序列平滑次数 |

## 5. 与现有架构的集成

### 5.1 Tier 链改造

```
原 Tier 链:
  Tier 1 (LLM) → Tier 2 (ChineseSplitter+jieba) → Tier 3 (ChineseRuleSplitter)

v0.2 新 Tier 链:
  Tier 1 (LLM, 未来)
  → Tier 2A (TextTilingSemanticSplitter) ← 本次新增
  → Tier 2B (ChineseSplitter+jieba)      ← 降级
  → Tier 3 (ChineseRuleSplitter)         ← 兜底
```

**关键设计**：TextTiling 单独作为 Tier 2A，因为它解决的是**主题边界**问题，而原 Tier 2 解决的是**单句切分**问题。两者协同工作：

```
TextTiling 标识主题边界位置
         ↓
ChineseSplitter 按句子切分
         ↓
合并：在主题边界处插入虚拟 SentenceBlock(is_topic_boundary=True)
         ↓
输出到 SceneSegmenter
```

### 5.2 新的 SentenceBlock 扩展

```python
@dataclass
class SentenceBlock:
    # ... 原有字段
    is_topic_boundary: bool = False    # ← 新增
    topic_depth_score: float = 0.0     # ← 新增（仅边界处有值）
```

### 5.3 新的 Splitter 类

```python
# src/splitter/texttiling/splitter.py
class TextTilingSemanticSplitter(BaseSentenceSplitter):
    language = "auto"  # 支持中英文
    tier = "tier2_semantic"

    def __init__(self, config: dict = None):
        # window_size, threshold 等
        ...

    def split(self, text: str) -> List[SentenceBlock]:
        # 1. 检测语言 → 调对应分词器
        # 2. 短文本早退
        # 3. 调用 TextTiling.find_boundaries()
        # 4. 调 Tier 3 规则分句
        # 5. 在边界处插入虚拟 SentenceBlock
        ...

    def is_available(self) -> bool:
        # 始终可用（jieba 缺失时降级到字符级）
        return True
```

## 6. 验收测试矩阵

| # | 场景 | 期望 | 测试方法 |
|---|------|------|---------|
| TT-01 | 单主题文本 | 0 个边界 | 输入"今天天气真好。我们去散步" |
| TT-02 | 双主题文本 | 1 个边界 | 输入主题A 内容 + 主题B 内容 |
| TT-03 | 三主题文本 | 2 个边界 | 输入3 个不同主题段 |
| TT-04 | 短文本（< 100 字） | 0 边界早退 | 验证短文本不切 |
| TT-05 | 中文 jieba 集成 | 边界位置正确 | 输入含中文长文，jieba 分词后检测 |
| TT-06 | 英文空白分词 | 边界位置正确 | 输入英文长文 |
| TT-07 | 边界置信度 | depth_score > threshold | 验证数学正确 |
| TT-08 | 降级链 | TextTiling 异常 → Tier 3 兜底 | mock 算法抛异常 |
| TT-09 | is_topic_boundary 标记 | 边界处 virtual block | 检查 SentenceBlock 字段 |
| TT-10 | 与 pipeline 集成 | tier_used 包含 "tier2" | 端到端测试 |

## 7. 工期与风险

| 工作量 | 评估 |
|--------|------|
| TextTiling 算法核心 | 0.5 天 |
| 中英文分词集成 | 0.3 天 |
| 边界 → SentenceBlock 转换 | 0.2 天 |
| 集成到 pipeline | 0.3 天 |
| 测试用例 | 0.5 天 |
| 文档同步 | 0.2 天 |
| **总计** | **2.0 天** |

**风险与缓解**：

| 风险 | 影响 | 缓解 |
|------|------|------|
| TextTiling 在短文本上误判 | 测试失败 | 短文本早退（min_text_length=100） |
| jieba 词典大小影响启动 | 启动慢 1s | 懒加载（按需导入） |
| 边界位置与规则分句冲突 | 边界未生效 | 边界位置用 token → char offset 精确转换 |
| 多语言混合文本 | 算法不准 | v0.2 限定单一语言输入，混合文本 P1 再做 |

## 8. 交付清单

- [ ] `src/splitter/texttiling/texttiling.py` — 算法核心
- [ ] `src/splitter/texttiling/splitter.py` — Splitter 适配
- [ ] `src/splitter/texttiling/sentence_similarity.py` — 余弦相似度
- [ ] `tests/unit/test_texttiling.py` — 算法测试（5+ 用例）
- [ ] `tests/unit/test_tt_splitter.py` — Splitter 集成测试（10+ 用例）
- [ ] `docs/ARCH-002-texttiling.md` — 详细设计
- [ ] 同步更新：PRD / CHANGELOG / README / AGENTS
- [ ] Git commit + tag `v0.2.0`

## 9. 与 v0.1 兼容性

- ✅ **不破坏现有 API** — `SmartSentenceSplitter` 接口不变
- ✅ **不破坏现有测试** — 101 个 v0.1 测试必须仍然全绿
- ✅ **可选启用** — `enable_topic_segmentation: true` 才启用，默认 false
- ✅ **零依赖新增** — 仅使用 `math` + `collections.Counter`（stdlib）

## 10. 成功标准

- ✅ TextTiling 算法实现 + 单测 5+ 用例全绿
- ✅ Splitter 集成 + 单测 10+ 用例全绿
- ✅ pipeline 集成：长文本能识别主题边界
- ✅ v0.1 全部 101 测试仍通过
- ✅ 总测试数 ≥ 130（增加 30+ 用例）
- ✅ 文档同步到位
- ✅ 提交 + tag v0.2.0 推送 GitHub

---

**版本**: v0.2.0
**关联**: PRD v0.2.0 §11 (多语言) / F-03 (TextTiling)
**下一步**: 写 ARCH-002 详细技术方案
