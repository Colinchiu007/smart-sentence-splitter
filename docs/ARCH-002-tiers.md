# ARCH-002 — 三级降级链详细设计

## 1. 架构图

```
输入文本
  │
  ├─ Tier 1 (LLMSplitter)    — 语义分句 (LLM, 可配置 provider)
  │   可用性: is_available() → API key 存在
  │   降级: LLM 失败 → Tier 2
  │
  ├─ Tier 2A (TextTilingSplitter) — 主题边界识别 (词汇重复度)
  │   可用性: enable_topic_segmentation=True
  │   降级: 短文本/异常 → Tier 2B
  │
  ├─ Tier 2B (ChineseSplitter) — jieba分词+词性+EOS窗口
  │   可用性: 始终可用
  │   降级: jieba 不可用时 → Tier 3
  │
  └─ Tier 3 (Chinese/English RuleSplitter) — 纯标点规则分句
      可用性: 始终可用 (零依赖 fallback)
```

## 2. TierChain 核心逻辑

```python
# 每次 split() 重新计算 min_tier
min_tier = self.min_tier_provider()  # callable
for splitter in tier_splitters:
    if parse_tier_num(splitter.tier) < min_tier:
        continue      # 跳过低 tier
    if not splitter.is_available():
        continue      # 不可用自动降级
    try:
        result = splitter.split(text)
        return result, splitter.tier  # 首次成功即返回
    except Exception:
        continue      # 异常时降级
# 全失败 → 最后一个兜底
return last_fallback
```
