#!/usr/bin/env python3
"""跨实现分句金标生成器（sidecar → 金标快照）。

## 它是什么、不是什么（先读这段，否则会误用）

- **不是真值来源**。字幕切分「什么算对」由 `tests/vectors/subtitle_segmentation_vectors.json`
  里的**手工真值** `expected_blocks` 定义，那条口径不变（见 test_subtitle_vectors.py 的
  「禁止直接把实现输出写入向量」）。
- **是跨实现漂移探测器**。本脚本把 **本服务（生产上 8002 实际跑的那一份）** 的输出固化成
  快照，交给 Multi-Publish 侧的 TS 与 Electron JS 实现逐字复现。它回答的问题是
  「本地降级实现和线上 sidecar 是不是同一份行为」，**不是**「这样切对不对」。
- 两者互补：如果三端一起错，金标不会红（它只比一致性），但手工向量会红。

## 用法（**没有命令行参数**）

    PYTHONPATH=<repo>/src python scripts/gen_subtitle_python_golden.py

输入输出都在仓库内的固定相对位置：

    输入  tests/vectors/subtitle_parity_corpus.json      （语料，只有输入）
    输出  tests/vectors/subtitle_python_golden.json      （金标，每例的 blocks）

**为什么不做成 `--corpus` / `--out` 参数**：那样一个本地脚本就能往任意路径读写文件，
而它真正需要的只有一个固定输入与一个固定输出。去掉路径参数既缩掉了这个口子，也让
「金标到底存哪」只有一个答案 —— 之前用参数时，同一次生成可以由不同的人写到不同位置。
（安全扫描器把「`Path(...ars)` 形态」判为路径遍历高危并阻断提交，这是它按正则判的真阳性
形态；本脚本去掉参数后该形态自然不存在，不需要任何抑制开关。）

## 生成之后还要做什么

Multi-Publish 仓有一份同内容的副本（CI 要在那边跑 TS/JS 对比）。生成后把这两个文件
复制过去，并跑两仓的对账：

    node scripts/check-sidecar-parity.js --sidecar <本仓>   # 在 Multi-Publish 仓执行

跨仓副本是否一致由那条对账判据守；本仓测试另会断言金标记录的**数据版本哈希**与
`sidecar-parity.lock.json` 一致 —— 改了规则表/向量却忘了重生成金标会当场变红。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from splitter.scene_subtitle.subtitle_segmenter import SubtitleSegmenter  # noqa: E402

RULES = REPO / "src" / "splitter" / "scene_subtitle" / "subtitle_rules.json"
VECTORS = REPO / "tests" / "vectors" / "subtitle_segmentation_vectors.json"
CORPUS = REPO / "tests" / "vectors" / "subtitle_parity_corpus.json"
GOLDEN = REPO / "tests" / "vectors" / "subtitle_python_golden.json"


def lf_sha256(path: Path) -> str:
    """LF 归一化后取 sha256 —— 与 TS/JS 侧同一口径（CRLF→LF 再算字节哈希）。"""
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def git_head() -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:  # noqa: BLE001 - 取证失败不该阻断生成
        return "unknown"


def split_blocks(text: str) -> list[str]:
    """与 TS `splitTextToSubtitles` 同口径：先 trim，空串返回空列表。"""
    trimmed = text.strip()
    if not trimmed:
        return []
    segmenter = SubtitleSegmenter()
    return segmenter._split_to_blocks(trimmed)


def main() -> int:
    if not CORPUS.exists():
        print(
            f"✗ 语料不存在：{CORPUS}\n"
            "  语料是两仓共用的同一份，请从 Multi-Publish 仓复制：\n"
            "    packages/story2video-engine/tests/fixtures/subtitle_parity_corpus.json\n"
            f"  → {CORPUS}",
            file=sys.stderr,
        )
        return 2

    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    if corpus.get("schema") != "subtitle-parity-corpus/1":
        print(f"✗ 意外的语料 schema: {corpus.get('schema')!r}", file=sys.stderr)
        return 2

    cases = []
    seen = set()
    for case in corpus["cases"]:
        cid = case["id"]
        if cid in seen:
            print(f"✗ 语料里 id 重复: {cid}", file=sys.stderr)
            return 2
        seen.add(cid)
        cases.append({"id": cid, "blocks": split_blocks(case["text"])})

    golden = {
        "schema": "subtitle-python-golden/1",
        "what": (
            "Python sidecar（生产 8002 那一份）在上述语料上的输出快照。"
            "它只用于跨实现**一致性**对账，不定义切分**正确性**；正确性由共享向量的手工真值界定。"
        ),
        "doNotHandEdit": True,
        "generatedBy": "scripts/gen_subtitle_python_golden.py",
        "provenance": {
            "repo": "smart-sentence-splitter",
            "commit": git_head(),
            "rulesLfSha256": lf_sha256(RULES),
            "vectorsLfSha256": lf_sha256(VECTORS),
            "corpusLfSha256": lf_sha256(CORPUS),
        },
        "cases": cases,
    }

    GOLDEN.write_text(json.dumps(golden, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total_blocks = sum(len(c["blocks"]) for c in cases)
    print(f"golden written: {GOLDEN}")
    print(f"  cases={len(cases)} blocks={total_blocks}")
    print(f"  rulesLfSha256   = {golden['provenance']['rulesLfSha256']}")
    print(f"  vectorsLfSha256 = {golden['provenance']['vectorsLfSha256']}")
    print(f"  corpusLfSha256  = {golden['provenance']['corpusLfSha256']}")
    print(f"  commit          = {golden['provenance']['commit']}")
    print("下一步：把 corpus 与本 golden 复制到 Multi-Publish 仓，再跑跨仓对账。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
