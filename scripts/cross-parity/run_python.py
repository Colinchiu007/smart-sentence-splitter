# -*- coding: utf-8 -*-
"""跨实现差分测试：比较 Python 与 TypeScript 字幕分割输出。

用法：
  1. Python 侧（在 splitter 仓库）：
     python scripts/cross-parity/run_python.py scripts/cross-parity/corpus.json /tmp/out_py.json
  2. TS 侧（在 Multi-Publish packages/story2video-engine）：
     npm exec --yes --package=tsx -- tsx <splitter>/scripts/cross-parity/run_typescript.ts <splitter>/scripts/cross-parity/corpus.json /tmp/out_ts.json
  3. 对比：
     python scripts/cross-parity/compare.py /tmp/out_py.json /tmp/out_ts.json

输出：{id: {blocks, starts, durs}}；compare.py 输出逐字段不一致清单并返回非零退出码。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 仓库根（含 src/）
from splitter.models import SceneSegment
from splitter.scene_subtitle.subtitle_segmenter import SubtitleSegmenter

def main() -> None:
    corpus_path, out_path = sys.argv[1], sys.argv[2]
    corpus = json.loads(Path(corpus_path).read_text(encoding="utf-8"))
    out = {}
    for c in corpus:
        cfg = dict(c.get("config") or {})
        cfg.setdefault("min_chars_per_block", 8)
        cfg.setdefault("max_chars_per_block", 15)
        cfg.setdefault("time_calculation_method", "proportional")
        seg = SubtitleSegmenter(cfg)
        scene = SceneSegment(segment_id=0, text=c["text"], estimated_duration=10.0, target_words=len(c["text"]))
        subs = seg.segment(scene)
        out[c["id"]] = {"blocks": [s.text for s in subs], "starts": [s.start_time for s in subs], "durs": [s.duration for s in subs]}
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"python parity done: {len(out)} cases -> {out_path}")

if __name__ == "__main__":
    main()
