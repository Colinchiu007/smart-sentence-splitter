# PM-PRD-ARCH-v0.7 — 剧本分析 + 分镜增强

**版本**: v0.7.0
**日期**: 2026-06-14
**状态**: 实施中

---

## 1. 问题

PROJECT-012 现有分句 + 场景打包仅按字数（6s），缺少剧本结构理解：
- 不知道角色是谁 → 无法保持角色一致性
- 不知道场景切换（地点变化）→ 分割不准确
- 每句/每场是孤立的 → PROJECT-011 没有上下文

## 2. 新增模块

### script_analyzer.py — 剧本分析器

从完整剧本文本提取全局元数据:
- 角色列表 (人名词性标注 → jieba nr tag)
- 故事梗概 (第一段摘要)
- 地点/场景列表 (地点实体)
- 关键名词表

### scene_segmenter 升级 — 分镜级场景分割

原有: 按字数合并 (无视内容)
新增: 地点变化时强制分场景

### SceneSegment 扩展

| 新增字段 | 类型 | 说明 |
|----------|------|------|
| characters | List[str] | 本场出现的角色 |
| setting | str | 本场地点的描述 |
| mood | str | 本场情绪标签 |
| story_phase | str | 开头/发展/高潮/结局 |

### Exporter 升级 — 分镜输出格式

新增 `to_storyboard()` 输出完整分镜 JSON。

## 3. 架构

```
完整剧本
  │
  ├→ script_analyzer.analyze()
  │   ├→ character_list   ← jieba 词性 (nr)
  │   ├→ synopsis         ← 第一段
  │   └→ key_terms        ← 高频名词
  │
  ├→ pipeline.split()  (现有)
  │   └→ scene_segmenter (升级: 地点变化→新场景)
  │       └→ SceneSegment (新增: characters/setting/mood)
  │
  └→ exporter.to_storyboard()
      └→ PROJECT-011 消费
```

## 4. 测试计划

| 模块 | 测试数 | 内容 |
|------|--------|------|
| script_analyzer | 10 | 角色提取/场景提取/梗概 |
| scene_segmenter 升级 | 5 | 地点变化分场景 |
| SceneSegment 新字段 | 5 | 序列化/默认值 |
| exporter storyboard | 5 | 完整输出格式 |
| 集成 | 5 | 全流程剧本→分镜 |
| **合计** | **~30** | |
