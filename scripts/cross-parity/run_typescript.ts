/**
 * 跨实现差分测试（TS 侧）——见同目录 README.md。
 * 用法：npm exec --yes --package=tsx -- tsx <splitter>/scripts/cross-parity/run_typescript.ts <corpus.json> <out.json>
 * 注意：需在 Multi-Publish packages/story2video-engine 目录下运行，以便解析 ./src/text-segmentation。
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { SubtitleSegmenter } from '../../src/text-segmentation';

interface Case { id: string; text: string; config?: { min_chars_per_block?: number; max_chars_per_block?: number; time_calculation_method?: string } }

const corpusPath = process.argv[2];
const outPath = process.argv[3];
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
