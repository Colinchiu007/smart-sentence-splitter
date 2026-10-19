"""跨仓「单源规则表 + 共享向量」对账锁（sidecar 侧，与 mulpub 同款）。

## 这条锁解决什么问题

字幕切分规则表与切割向量在两仓各存一份手工副本，**没有任何东西会告诉你「只改了一边」**：
两仓单测各读自己仓的副本，全绿；而线上 8002 跑的是本仓副本，本地降级实现跑的是 mulpub 副本。
两者只在 sidecar 不可用那一刻才会同时出现在同一条链路上。

本文件把「两仓数据必须逐字节相同」变成机械判据：`tests/vectors/sidecar-parity.lock.json`
登记 LF 归一化 sha256，两仓各查自己那一半。

## 口径

LF 归一化后的**字节**哈希（CRLF→LF 再算）。不做 JSON 语义比较：跨语言侧
（Python `json.dumps` 与 JS `JSON.stringify` 的浮点/转义规则不同）没有可靠的公共规范化，
用两套规范化再比较等于在判据里埋一个自己就会漂移的东西。

## 改数据时要做什么

见锁文件自带的 `howToUpdate`：**两个仓库同批改**（数据 + 锁 + 重新生成金标），
否则本仓绿了 mulpub 侧仍会因为金标版本对账变红。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
LOCK_PATH = REPO / "tests" / "vectors" / "sidecar-parity.lock.json"
RULES_PATH = REPO / "src" / "splitter" / "scene_subtitle" / "subtitle_rules.json"
VECTORS_PATH = REPO / "tests" / "vectors" / "subtitle_segmentation_vectors.json"


def lf_sha256(path: Path) -> str:
    """LF 归一化后取 sha256 —— 与 mulpub 侧 `lfSha256()` 同一口径。"""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_lock() -> dict:
    with open(LOCK_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_lock_schema_and_required_fields():
    lock = load_lock()
    assert lock["schema"] == "sidecar-parity-lock/1"
    assert len(lock["rulesLfSha256"]) == 64
    assert len(lock["vectorsLfSha256"]) == 64
    # howToUpdate 不是装饰：改了数据却不知道下一步做什么，是这条锁最容易退化成噪声的形态。
    assert "gen_subtitle_python_golden" in lock.get("howToUpdate", "")


def test_rules_match_lock():
    lock = load_lock()
    actual = lf_sha256(RULES_PATH)
    assert actual == lock["rulesLfSha256"], (
        "本仓 subtitle_rules.json 与 sidecar-parity.lock.json 登记值不一致。\n"
        "两种情况：\n"
        "  (a) 你改了规则表 —— 必须把同一份内容改到 mulpub 仓，更新两个仓库的 "
        "sidecar-parity.lock.json，并重新生成 subtitle_python_golden.json；\n"
        "  (b) 你改了锁 —— 说明本仓数据没跟着改，先把数据改到与锁一致。\n"
        "不要「只把锁改成新值」了事：那样 mulpub 侧会在它自己的 CI 上变红。"
    )


def test_vectors_match_lock():
    lock = load_lock()
    actual = lf_sha256(VECTORS_PATH)
    assert actual == lock["vectorsLfSha256"], (
        "本仓 subtitle_segmentation_vectors.json 与锁登记值不一致。\n"
        "向量是两仓共用的同一份：改一边必须同步另一边，并同批更新两仓的锁。\n"
        "期望值（expected_blocks）必须是手工真值，不得直接抄实现输出。"
    )


def test_lock_hash_is_line_ending_insensitive():
    """哈希口径必须对行尾不敏感，否则本仓 CRLF 检出会必假红。"""
    lf = RULES_PATH.read_bytes().replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    digest = lambda b: hashlib.sha256(b).hexdigest()  # noqa: E731 - 就地一行更清楚

    assert hashlib.sha256(lf).hexdigest() == hashlib.sha256(crlf.replace(b"\r\n", b"\n")).hexdigest()
    assert hashlib.sha256(lf).hexdigest() == load_lock()["rulesLfSha256"]
    # 未归一化时两者必须不同——否则上一条断言是空转。
    assert digest(crlf) != digest(lf)


# ---------------------------------------------------------------------------
# 金标新鲜度：本仓也存了一份金标（由 scripts/gen_subtitle_python_golden.py 产出），
# 它只在 Multi-Publish 侧被消费。**如果本仓这份悄悄过期，没有任何判据会发现**
# —— 过期金标仍会被复制过去并通过对方的测试，只是它描述的是旧行为。
# 所以这里断言金标记录的 provenance 与本仓当前数据版本一致：改了规则表/向量/语料
# 却没重跑生成器 ⇒ 当场变红。
# ---------------------------------------------------------------------------

GOLDEN_PATH = REPO / "tests" / "vectors" / "subtitle_python_golden.json"
CORPUS_PATH = REPO / "tests" / "vectors" / "subtitle_parity_corpus.json"


def test_golden_provenance_matches_current_data_version():
    lock = load_lock()
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        golden = json.load(f)
    prov = golden["provenance"]
    assert prov["rulesLfSha256"] == lock["rulesLfSha256"], (
        "金标是在另一版规则表上生成的。改了规则表就必须重跑 "
        "`PYTHONPATH=<repo>/src python scripts/gen_subtitle_python_golden.py`，"
        "否则对方仓的内容对账会拿着一份描述旧行为的金标跑测试。"
    )
    assert prov["vectorsLfSha256"] == lock["vectorsLfSha256"], (
        "金标是在另一版向量上生成的，请重跑生成器。"
    )
    assert prov["corpusLfSha256"] == lf_sha256(CORPUS_PATH), (
        "金标里的语料哈希与本仓当前语料不一致：语料改过但生成器没重跑。"
    )


def test_golden_covers_every_corpus_case():
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        golden = json.load(f)
    with open(CORPUS_PATH, encoding="utf-8") as f:
        corpus = json.load(f)
    golden_ids = sorted(c["id"] for c in golden["cases"])
    corpus_ids = sorted(c["id"] for c in corpus["cases"])
    assert golden_ids == corpus_ids, "金标与语料的用例集不一致（增删用例后必须重跑生成器）"
    assert len(golden_ids) == len(set(golden_ids)), "金标存在重复 id"
