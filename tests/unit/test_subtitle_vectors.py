"""共享字幕分割测试向量断言（规范 v1.0，双实现共用）。

加载 tests/vectors/subtitle_segmentation_vectors.json，对每个向量：
- 用 SubtitleSegmenter 跑输入文本，断言输出字幕文本序列与 expected_blocks 逐字一致；
- 断言时间戳：proportional 模式下 start_time 用舍入后的 duration 连续累加，区间**严格连续**
  （start_time_i == round(start_time_{i-1} + duration_{i-1}, 2)）——旧实现曾产生 0.01s 间隙，
  原容差 abs=0.02 漏检，现改为严格相等；
- 断言 min_chars 不变量：每块长度 ≥ min_chars，例外必须在向量的 short_block_exceptions 中
  显式声明（含 reason）——禁止无标点硬切产生的孤悬尾块（本次 bug 根因）。

向量管理（双轨制）：
- expected_blocks 必须为**手工真值**（按《字幕分割规范 v1.0》人工推导），再与实现输出核对；
  禁止直接把实现输出写入向量（自证陷阱会让实现与向量共同漂移，测试失去拦截力）。
- 新增/修改向量时，若存在 < min_chars 的块，必须同步更新 short_block_exceptions 并写明原因。

本文件是 splitter（Python）实现的一致性护栏；Multi-Publish（TypeScript）
实现必须通过同一份向量（见其 story2video-engine 测试）。
"""

import json
from pathlib import Path

import pytest

from splitter.models import SceneSegment
from splitter.scene_subtitle.subtitle_segmenter import SubtitleSegmenter

VECTORS_PATH = Path(__file__).resolve().parent.parent / "vectors" / "subtitle_segmentation_vectors.json"
DURATION = 10.0


def _load_vectors():
    with open(VECTORS_PATH, encoding="utf-8") as f:
        return json.load(f)["vectors"]


def _run_segmenter(vector, time_method: str | None = None):
    cfg = dict(vector.get("config", {}))
    if time_method is not None:
        cfg["time_calculation_method"] = time_method
    seg = SubtitleSegmenter(cfg)
    scene = SceneSegment(
        segment_id=0,
        text=vector["input"],
        estimated_duration=DURATION,
        target_words=len(vector["input"]),
    )
    return seg.segment(scene)


@pytest.mark.parametrize("vector", _load_vectors(), ids=lambda v: v["id"])
def test_vector_blocks(vector):
    """字幕块序列与向量 expected_blocks 逐字一致（手工真值）。"""
    subs = _run_segmenter(vector)
    actual = [s.text for s in subs]
    assert actual == vector["expected_blocks"], (
        f"向量 {vector['id']} 字幕块不一致\n  expected={vector['expected_blocks']}\n  actual  ={actual}"
    )


@pytest.mark.parametrize("vector", _load_vectors(), ids=lambda v: v["id"])
def test_vector_min_chars_invariant(vector):
    """min_chars 不变量：每块长度 ≥ min_chars；例外必须显式声明（short_block_exceptions + reason）。

    例外仅允许：独立短句/短片段、标点或空格边界切分产生的短片段、合法 ≤3 字短尾。
    禁止：无标点硬切产生的孤悬尾块（如 15+4 → 4 字尾块；本次 bug 根因，应平衡为 11+8）。
    """
    min_chars = vector.get("config", {}).get("min_chars_per_block", 8)
    exceptions = {e["index"]: e.get("reason", "") for e in vector.get("short_block_exceptions", [])}
    subs = _run_segmenter(vector)
    actual = [s.text for s in subs]
    for i, b in enumerate(actual):
        if len(b) >= min_chars:
            continue
        assert i in exceptions, (
            f"向量 {vector['id']} 块 {i}（{b!r}）长度 {len(b)} < min_chars={min_chars}，"
            f"未在 short_block_exceptions 中显式声明——无标点硬切孤悬尾块是本次 bug 根因，禁止"
        )
        assert exceptions[i], f"向量 {vector['id']} 块 {i} 例外缺少 reason"
    # 反向校验：声明的例外必须真实存在且确实 < min_chars（防止死条目/向量漂移）
    for i in exceptions:
        assert i < len(actual), f"向量 {vector['id']} 例外 index {i} 越界（实际 {len(actual)} 块）"
        assert len(actual[i]) < min_chars, (
            f"向量 {vector['id']} 例外 index {i}（{actual[i]!r}）不再 < min_chars，应移除该声明"
        )


@pytest.mark.parametrize("vector", _load_vectors(), ids=lambda v: v["id"])
def test_vector_timestamps_contiguous(vector):
    """proportional：时间戳舍入后**严格连续**（start[i] == round(start[i-1] + dur[i-1], 2)）。

    旧实现直接累加未舍入 duration，产生 0.01s 间隙/重叠；原断言 abs=0.02 容差过宽漏检。
    现断言严格相等（实现统一为舍入后连续累加），任何舍入不一致都会立即失败。
    """
    subs = _run_segmenter(vector, time_method="proportional")
    assert subs, f"向量 {vector['id']} 无字幕块"
    # 首块 start_time=0
    assert subs[0].start_time == 0.0, f"向量 {vector['id']} 首块 start_time 非 0"
    # 每块 start_time/duration 均保持 2 位小数
    for s in subs:
        assert s.start_time == round(s.start_time, 2), f"向量 {vector['id']} start_time 超过 2 位小数: {s.start_time}"
        assert s.duration == round(s.duration, 2), f"向量 {vector['id']} duration 超过 2 位小数: {s.duration}"
        assert s.duration > 0, f"向量 {vector['id']} 存在非正 duration: {s.duration}"
    # 区间严格连续：start[i] == round(start[i-1] + dur[i-1], 2)
    for i in range(1, len(subs)):
        expect = round(subs[i - 1].start_time + subs[i - 1].duration, 2)
        assert subs[i].start_time == expect, (
            f"向量 {vector['id']} 块 {i} 时间戳不连续：start[{i}]={subs[i].start_time} "
            f"!= round(start[{i - 1}] + dur[{i - 1}], 2)={expect}"
        )
    # 总时长 ≈ DURATION（末块 end = start + dur）
    end = round(subs[-1].start_time + subs[-1].duration, 2)
    assert end == pytest.approx(DURATION, abs=0.01 * len(subs) + 0.01)
    # display_order 连续
    assert [s.display_order for s in subs] == list(range(len(subs)))


@pytest.mark.parametrize("vector", _load_vectors(), ids=lambda v: v["id"])
def test_vector_timestamps_equal(vector):
    """equal：等分时长，同样保持舍入后严格连续。"""
    subs = _run_segmenter(vector, time_method="equal")
    if not subs:
        return
    assert subs[0].start_time == 0.0
    for i in range(1, len(subs)):
        expect = round(subs[i - 1].start_time + subs[i - 1].duration, 2)
        assert subs[i].start_time == expect, (
            f"向量 {vector['id']} 块 {i} 时间戳不连续（equal）：{subs[i].start_time} != {expect}"
        )
