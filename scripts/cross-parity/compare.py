# -*- coding: utf-8 -*-
"""对比两份差分输出 JSON（{id: {blocks, starts, durs}}），逐字段报告不一致。"""
import json
import sys
from pathlib import Path

def main() -> None:
    a = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    b = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    ids = set(a) | set(b)
    block_diff = [c for c in ids if a.get(c, {}).get("blocks") != b.get(c, {}).get("blocks")]
    time_diff = [c for c in ids if a.get(c, {}).get("starts") != b.get(c, {}).get("starts") or a.get(c, {}).get("durs") != b.get(c, {}).get("durs")]
    print(f"cases: {len(ids)}  blocks 不一致: {len(block_diff)}  时间戳不一致: {len(time_diff)}")
    for c in block_diff:
        print(f"  [blocks] {c}: py={a.get(c,{}).get('blocks')} ts={b.get(c,{}).get('blocks')}")
    for c in time_diff:
        if c in block_diff:
            continue
        print(f"  [time] {c}: py starts={a.get(c,{}).get('starts')} durs={a.get(c,{}).get('durs')}")
        print(f"         ts starts={b.get(c,{}).get('starts')} durs={b.get(c,{}).get('durs')}")
    sys.exit(1 if (block_diff or time_diff) else 0)

if __name__ == "__main__":
    main()
