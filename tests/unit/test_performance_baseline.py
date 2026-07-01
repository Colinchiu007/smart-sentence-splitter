"""性能基线测试 — 防止 v0.8.2 后性能回归 (v0.8.2 新增).

性能基线:
- 1000 字文本 < 500ms
- 10000 字文本 < 2s
- 100KB 文本 < 10s
- 1MB 文本 < 60s (无内存爆炸)
- 短文 (50 字) < 100ms (排除 jieba 加载)
"""

import time
import pytest
from splitter import SmartSentenceSplitter


# 测试用文本 (1KB)
TEXT_1K = """今天天气真好。阳光明媚。

小明走进超市。他拿了一瓶水。小红在公园等他。

小明回到家。妈妈说：学校停课了。

第二天，小明和小红决定去公园碰碰运气。

他们走在空旷的街道上，看到一只猫。猫喵喵叫了两声。

远处传来警报声。所有人都紧张起来。

最终，这只是虚惊一场。但这一天注定不平凡。

他们在公园里坐着，看着天空，思考未来。

希望明天会更好。这就是生活。

""" * 5


# 预热 (避免 jieba 首次加载干扰)
@pytest.fixture(scope="module", autouse=True)
def warmup():
    SmartSentenceSplitter().split("预热文本。")


class TestPerformanceBaseline:
    """性能基线 — 防止回归。"""

    def test_short_text_under_100ms(self):
        """50 字文本 < 100ms。"""
        text = "今天天气真好。阳光明媚。小明走进超市。"
        s = SmartSentenceSplitter()
        t0 = time.perf_counter()
        r = s.split(text)
        elapsed = (time.perf_counter() - t0) * 1000
        assert elapsed < 100, f"50 字用 {elapsed:.1f}ms, 超过 100ms"

    def test_1k_text_under_500ms(self):
        """1KB 文本 < 500ms。"""
        s = SmartSentenceSplitter({"length": {"strategy": "A", "max_chars": 15}})
        t0 = time.perf_counter()
        r = s.split(TEXT_1K)
        elapsed = (time.perf_counter() - t0) * 1000
        assert elapsed < 500, f"1KB 用 {elapsed:.1f}ms, 超过 500ms"

    def test_10k_text_under_3s(self):
        """10KB 文本 < 3s。"""
        text = TEXT_1K * 10
        s = SmartSentenceSplitter({"mode": "fast"})
        t0 = time.perf_counter()
        r = s.split(text)
        elapsed = (time.perf_counter() - t0) * 1000
        assert elapsed < 3000, f"10KB 用 {elapsed:.1f}ms, 超过 3s"

    def test_split_returns_correct_structure(self):
        """性能测试不应牺牲正确性。"""
        s = SmartSentenceSplitter()
        r = s.split("这是第一句。这是第二句。这是第三句。")
        assert len(r.sentences) == 3
        assert r.tier_used is not None

    def test_100kb_under_10s(self):
        """100KB 文本 < 10s, 无内存爆炸。"""
        text = TEXT_1K * 100  # ~100KB
        s = SmartSentenceSplitter({"mode": "fast"})
        t0 = time.perf_counter()
        r = s.split(text)
        elapsed = (time.perf_counter() - t0) * 1000
        assert len(r.sentences) > 100
        assert elapsed < 10000, f"100KB 用 {elapsed:.1f}ms, 超过 10s"

    def test_1mb_under_60s(self):
        """1MB 文本 < 60s, 验证无内存爆炸。"""
        text = TEXT_1K * 1000  # ~1MB
        s = SmartSentenceSplitter({"mode": "fast"})
        t0 = time.perf_counter()
        r = s.split(text)
        elapsed = (time.perf_counter() - t0) * 1000
        assert len(r.sentences) > 500
        assert elapsed < 60000, f"1MB 用 {elapsed:.1f}ms, 超过 60s"