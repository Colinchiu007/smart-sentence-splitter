# PM-PRD-v0.6 — 字数控制分句 (length_strategy)

**版本**: v0.6.0
**日期**: 2026-06-14
**作者**: PM (COO role)
**状态**: 实施中

---

## 1. 目标

让用户通过参数选择"按字数控制分句"的策略：A（重切）或 B（标尺）。默认 B（不破坏现有行为）。

## 2. 关键设计决策

### 2.1 不破坏 v0.5.1 现有契约

- 默认 B 模式 = 现有行为（标点切句，超长/过短仅警告）
- 现有 239 测试 0 修改
- `length_strategy` 参数**默认 "B"**

### 2.2 A 模式算法

**输入**: 已按标点切好的 `List[SentenceBlock]`
**输出**: 按字数重切的 `List[SubtitleBlock` 或新 `List[SentenceBlock]>`

**算法**:
```
对每个 SentenceBlock:
    if len(s) <= max_chars:
        output.append(s)            # 不切
    else:
        # 用优先级标点列表贪心切
        for punct in priority_list:  # 。，！？； etc
            if not found, skip
            找最接近 max_chars 的标点切
        # 兜底：强制按 max_chars 切
        while len(s) > 0:
            chunk = s[:max_chars]
            s = s[max_chars:]
            output.append(chunk)
```

**优先级标点**: 。！？；，. ! ? ; , (中文优先)

### 2.3 B 模式算法

**输入**: 已按标点切好的 `List[SentenceBlock]`
**输出**: 原列表 + 每个 block 加 `length_status` 字段
- `ok` — 3 <= len <= max_chars
- `too_short` — len < 3
- `too_long` — len > max_chars

**不重切**，仅**打标签** + 警告。

### 2.4 配置项

```yaml
length_strategy: "B"  # A | B | off
length:
  min_chars: 3
  max_chars: 15
  prefer_punctuation: true
  warning_on_violation: true
```

### 2.5 pipeline 集成位置

在 `pipeline.split()` 步骤 4 (分句) 之后，步骤 5 (场景) 之前插入新步骤 4.5: `apply_length_strategy`。

## 3. 数据模型扩展

```python
@dataclass
class SentenceBlock:
    # ... 现有字段 ...
    length_status: str = "ok"  # ok | too_short | too_long
    length_strategy_applied: str = "none"  # none | A | B
```

## 4. 验收测试

| 场景 | 期望 |
|------|------|
| 短输入 (1句, 5字) | B 模式输出 1 句, status=ok |
| 短输入 (1句, 5字) | A 模式输出 1 块 |
| 中等输入 (1句 20字) | B 模式 status=too_long |
| 中等输入 (1句 20字) | A 模式切成 2 块 (15+5) |
| 长输入 (100字连续) | A 模式 7+ 块, 全部 3-15 |
| 长输入 (100字连续) | B 模式 1 句, status=too_long |
| 模式 off | 透传原结果 |
| 默认 (不传 length_strategy) | 等同 B 模式 |
| 中文优先标点 | A 切分在中文标点处 |
| 英文优先标点 | A 切分在英文标点处 |
| 混合 | A 模式各自语言各自标点优先 |

## 5. 风险与缓解

| 风险 | 缓解 |
|------|------|
| A 模式破坏下游场景合并 | 4.5 在场景合并前, 句子先重切 |
| A 模式切断语义 | 提供 `warning_on_violation` 提示 |
| 数据模型加字段破老测试 | 字段有默认值, 不传也对 |
| 性能 | O(n) 单遍扫描, 标点 O(1) 查表 |
