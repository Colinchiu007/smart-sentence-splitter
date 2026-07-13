import {
  Divider,
  Grid,
  H1,
  H2,
  Stack,
  Stat,
  Table,
  Text,
  Timeline,
  Callout,
} from "qoder/canvas";

const issues = [
  {
    id: "1",
    title: "字幕块末尾标点去除",
    before: "是一座由火枪、教堂和紧握的拳头构成的孤岛。",
    after: "是一座由火枪、教堂和紧握的拳头构成的孤岛",
    fix: "_clean_subtitle_blocks Step 2+4: rstrip 末尾标点",
  },
  {
    id: "2",
    title: "跨块双引号清理",
    before: '以"加固城防 / 征讨敌人为理由',
    after: "以加固城防 / 征讨敌人为理由",
    fix: "两遍匹配算法: 块内优先 → 跨块 unmatched 删除",
  },
  {
    id: "3",
    title: "不合理切分 (十字/架)",
    before: "第一刀就砍向了他胸前挂着的十字 / 架",
    after: "第一刀就砍向了他胸前挂着的十字架",
    fix: "_find_extended_split 扩大搜索 + 配对引号保护",
  },
  {
    id: "4",
    title: "孤立引号场景消除",
    before: '场景 10 仅有 " 一个字符',
    after: "合并到相邻块，无孤立场景",
    fix: "_merge_short 扩展 _PUNCT_CHARS 含引号",
  },
  {
    id: "5",
    title: "标点开头修正 (，悄无声息)",
    before: "，悄无声息地完成了合围",
    after: "悄无声息地完成了合围",
    fix: "Step 1: 开头标点移到上一块末尾",
  },
  {
    id: "6",
    title: "语义截断 (接到一/封)",
    before: "马尼克·德拉腊接到一 / 封盖着招讨大将军印信",
    after: "马尼克·德拉腊接到一封 / 盖着招讨大将军印信",
    fix: "_adjust_for_semantic 数词+量词保护",
  },
  {
    id: "7",
    title: "文本错乱 (场景 42-49)",
    before: "text.find() 反向映射失败 → 文字归错段落",
    after: "按段落独立分句，无映射问题",
    fix: "pipeline._paragraph_aware_segment 重写",
  },
];

const files = [
  ["subtitle_segmenter.py", "新增 _clean_subtitle_blocks (4步后处理), 扩展 _merge_short", "核心改动"],
  ["length_segmenter.py", "新增 _find_extended_split, _fix_leading_punctuation, _adjust_for_semantic", "核心改动"],
  ["pipeline.py", "重写 _paragraph_aware_segment 为按段落独立分句", "核心改动"],
  ["zh/splitter.py", "删除 DEBUG print 语句", "清理"],
  ["test_scene_subtitle.py", "新增 7 个测试用例", "测试"],
  ["PRD.md", "新增 v0.10 字幕质量增强章节", "文档"],
];

const tasks = [
  { title: "Task 1: 字幕后处理 (末尾标点/跨块引号/开头标点)", status: "done" as const },
  { title: "Task 2: LengthSegmenter 扩大搜索 + 切分校验", status: "done" as const },
  { title: "Task 3: _merge_short 引号纳入标点集合", status: "done" as const },
  { title: "Task 4: pipeline 文本映射修复", status: "done" as const },
  { title: "Task 5: ChineseSplitter 清理 DEBUG 输出", status: "done" as const },
  { title: "Task 6: 补充测试 (7 个新测试)", status: "done" as const },
  { title: "Task 7: 更新 PRD (v0.10 章节)", status: "done" as const },
  { title: "Task 8: 验证 (372 tests + Manila 文本)", status: "done" as const },
];

export default function SubtitleQualityFixReport() {
  return (
    <Stack gap={20}>
      <H1>字幕分割质量修复 — 完成报告</H1>
      <Text tone="secondary">
        PROJECT-012 智能语义分句引擎 · v0.10 字幕质量增强
      </Text>

      <Divider />

      <Grid columns={4} gap={16}>
        <Stat value="7" label="质量问题已修复" tone="success" />
        <Stat value="8" label="Task 全部完成" tone="success" />
        <Stat value="372" label="测试通过" tone="success" />
        <Stat value="6" label="文件已修改" />
      </Grid>

      <Divider />

      <H2>修复的 7 个质量问题</H2>
      <Table
        headers={["#", "问题", "修复前", "修复后", "修复方式"]}
        rows={issues.map((i) => [
          i.id,
          i.title,
          i.before,
          i.after,
          i.fix,
        ])}
      />

      <Divider />

      <H2>修改文件清单</H2>
      <Table
        headers={["文件", "改动内容", "类型"]}
        rows={files}
        rowTone={files.map((f) =>
          f[2] === "核心改动" ? "warning" : undefined
        )}
      />

      <Divider />

      <H2>任务执行时间线</H2>
      <Timeline
        events={tasks.map((t, i) => ({
          id: String(i),
          title: t.title,
          description: t.status === "done" ? "已完成" : "进行中",
          timestamp: "",
        }))}
      />

      <Divider />

      <H2>关键技术决策</H2>
      <Grid columns={2} gap={16}>
        <Callout tone="info" title="两遍引号匹配">
          <Text size="small">
            Pass 1: 块内匹配自包含引号对（保留块内配对）。
            Pass 2: 跨块栈匹配，删除未匹配和跨块配对的引号。
          </Text>
        </Callout>
        <Callout tone="info" title="语义保护切分">
          <Text size="small">
            _CLASSIFIERS 量词集合 + 数词检测，硬切时自动调整切分点，
            避免在「数词+量词」之间截断（如一/封 → 一封）。
          </Text>
        </Callout>
        <Callout tone="info" title="4步后处理管线">
          <Text size="small">
            Step 1: 开头标点修正 → Step 2: 末尾标点去除 →
            Step 3: 跨块引号清理 → Step 4: 再次去除暴露的标点。
          </Text>
        </Callout>
        <Callout tone="info" title="段落独立分句">
          <Text size="small">
            废弃 text.find() 反向映射，改为按段落独立调用
            tier 链分句 + 场景分割，彻底消除引号还原导致的文本错乱。
          </Text>
        </Callout>
      </Grid>

      <Divider />

      <H2>验证结果</H2>
      <Grid columns={3} gap={16}>
        <Stat value="51" label="场景数" />
        <Stat value="87" label="句子数" />
        <Stat value="153" label="字幕块数 (原 158)" />
      </Grid>
      <Callout tone="success" title="所有验证通过">
        <Text size="small">
          Manila 文本重新分句：无末尾标点、无跨块引号、无孤立引号场景、
          无标点开头的字幕块、场景 42-49 文本正确、十字架/接到一封 语义完整。
        </Text>
      </Callout>

      <Text tone="secondary" size="small">
        生成时间: 2025 · smart-sentence-splitter v0.10
      </Text>
    </Stack>
  );
}
