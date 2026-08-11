"""共享字幕分割测试向量断言（规范 v1.0，双实现共用）。

加载 tests/vectors/subtitle_segmentation_vectors.json，对每个向量：
- 用 SubtitleSegmenter 跑输入文本，断言输出字幕文本序列与 expected_blocks 逐字一致；
- 断言时间戳：proportional 模式下相对误差 < 0.01s。

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


@pytest.mark.parametrize("vector", _load_vectors(), ids=lambda v: v["id"])
def test_vector_blocks(vector):
    cfg = vector.get("config", {})
    seg = SubtitleSegmenter(cfg)
    scene = SceneSegment(
        segment_id=0,
        text=vector["input"],
        estimated_duration=DURATION,
        target_words=len(vector["input"]),
    )
    subs = seg.segment(scene)
    actual = [s.text for s in subs]
    assert actual == vector["expected_blocks"], (
        f"向量 {vector['id']} 字幕块不一致\n  expected={vector['expected_blocks']}\n  actual  ={actual}"
    )


@pytest.mark.parametrize("vector", _load_vectors(), ids=lambda v: v["id"])
def test_vector_timestamps_proportional(vector):
    """proportional：时长按字数比例分配，相对误差 < 0.01s。"""
    cfg = {**vector.get("config", {}), "time_calculation_method": "proportional"}
    seg = SubtitleSegmenter(cfg)
    scene = SceneSegment(
        segment_id=0,
        text=vector["input"],
        estimated_duration=DURATION,
        target_words=len(vector["input"]),
    )
    subs = seg.segment(scene)
    assert subs, f"向量 {vector['id']} 无字幕块"
    # 首块 start_time=0
    assert subs[0].start_time == pytest.approx(0.0, abs=0.01)
    # 总时长 ≈ DURATION
    total = sum(s.duration for s in subs)
    assert total == pytest.approx(DURATION, abs=0.01 * len(subs) + 0.01)
    # 顺序连续
    for i in range(1, len(subs)):
        assert subs[i].start_time == pytest.approx(subs[i - 1].start_time + subs[i - 1].duration, abs=0.02)
    # display_order 连续
    assert [s.display_order for s in subs] == list(range(len(subs)))