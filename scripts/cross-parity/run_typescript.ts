/**
 * 跨实现差分测试（TS 侧）——见同目录 README.md。
 * 用法：npm exec --yes --package=tsx -- tsx <splitter>/scripts/cross-parity/run_typescript.ts <corpus.json> <out.json>
 * 注意：需在 Multi-Publish packages/story2video-engine 目录下运行，以便解析 ./src/text-segmentation。
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

interface Case { id: string; text: string; config?: { min_chars_per_block?: number; max_chars_per_block?: number; time_calculation_method?: string } }

async function main(): Promise<void> {
  // 引擎模块路径：argv[3] 显式传入（指向 Multi-Publish packages/story2video-engine/src/text-segmentation.ts）
  const modulePath = process.argv[3] ?? resolve('../../src/text-segmentation');
  const { SubtitleSegmenter } = await import(pathToFileURL(resolve(modulePath)).href);

  const corpusPath = process.argv[2]; // 语料 JSON
  const outPath = process.argv[4] ?? (() => { throw new Error('缺少输出路径 argv[4]'); })(); // 输出 JSON
  const corpus = JSON.parse(readFileSync(corpusPath, 'utf-8')) as Case[];
  const out: Record<string, unknown> = {};
  for (const c of corpus) {
    const cfg = {
      minCharsPerBlock: c.config?.min_chars_per_block ?? 8,
      maxCharsPerBlock: c.config?.max_chars_per_block ?? 15,
      timeCalculationMethod: (c.config?.time_calculation_method === 'equal' ? 'equal' : 'proportional') as 'equal' | 'proportional',
    };
    const seg = new SubtitleSegmenter(cfg);
    const subs = seg.segment(c.text, 10, 0);
    out[c.id] = { blocks: subs.map((s) => s.text), starts: subs.map((s) => s.startTime), durs: subs.map((s) => s.duration) };
  }
  writeFileSync(outPath, JSON.stringify(out));
  console.log(`ts parity done: ${Object.keys(out).length} cases -> ${outPath}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
