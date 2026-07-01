"""Fuzz 测试 — 随机文本 + 标点组合, 验证引擎不崩溃 (v0.9.7 新增).

测试策略:
- 随机生成中文/英文/混排文本
- 极端标点组合 (连续标点/空字符/纯符号)
- 超长单词/超短文本/空文本
"""

import re
import random
import pytest
from splitter import SmartSentenceSplitter


# ===== 随机文本生成器 =====

ZH_CHARS = list("天地人大小明红花草树木山河风雨雷电光云星日月春夏秋冬"
                "你我他她它们了个之中上下左右前后里外东西南北来去进出"
                "说走跑跳看听闻读写算学教画画唱游玩耍爱恨情仇悲欢离合"
                "柴米油盐酱醋茶工商学兵农医政法经科教文卫体娱乐美艺术")

EN_WORDS = ["the", "a", "an", "is", "are", "was", "were", "be",
            "hello", "world", "test", "quick", "brown", "fox", "jump",
            "over", "lazy", "dog", "cat", "run", "walk", "talk", "say",
            "big", "small", "hot", "cold", "good", "bad", "happy", "sad"]

PUNCTUATION_ZH = "。！？，、；：……——（）《》“”‘’"
PUNCTUATION_EN = ".!?,;:'\"()-[]{}"
PUNCTUATION_EXTREME = "。！？，、；：……——？！。，；：！？" * 3


def random_zh_text(min_len=10, max_len=500):
    """生成随机中文文本。"""
    length = random.randint(min_len, max_len)
    text = ""
    while len(text) < length:
        chunk_len = random.randint(2, 20)
        chunk = "".join(random.choices(ZH_CHARS, k=chunk_len))
        punct = random.choice(PUNCTUATION_ZH)
        if random.random() < 0.3:
            chunk = "《" + chunk + "》"
        text += chunk + punct
    return text[:length]


def random_en_text(min_len=10, max_len=500):
    """生成随机英文文本。"""
    length = random.randint(min_len, max_len)
    text = ""
    words = []
    for _ in range(random.randint(3, 50)):
        word = random.choice(EN_WORDS)
        if random.random() < 0.2:
            word = word.capitalize()
        words.append(word)
    text = " ".join(words)
    for _ in range(random.randint(1, 5)):
        punct = random.choice(PUNCTUATION_EN)
        pos = random.randint(0, len(text) - 1)
        text = text[:pos] + punct + text[pos:]
    return text[:length]


def random_mixed_text(min_len=10, max_len=500):
    """生成随机中英混排文本。"""
    ratio = random.random()
    zh = random_zh_text(min_len, max_len)
    en = random_en_text(min_len, max_len)
    if ratio < 0.5:
        return zh + " " + en + " " + zh
    return en + " " + zh + " " + en


# ===== 极端场景 =====

EXTREME_CASES = [
    "",                                   # 空文本
    "   ",                                # 纯空白
    "。！？，、；：……——",                 # 纯标点
    "a" * 10000,                          # 超长单词
    "。" * 1000,                           # 纯句号
    "！" * 1000,                           # 纯叹号
    "测试" * 5000,                        # 重复词
    "《》" * 100,                          # 空书名号
    "「」" * 100,                          # 空引号
    "（）" * 100,                          # 空括号
    "小明说：" * 1000,                     # 重复信号词
    "A" * 100 + "。" + "B" * 100 + "！" + "C" * 100,  # 等长块
    "\\n" * 100,                           # 纯换行转义
    "测试.Test.测试!Hello?世界",          # 中英混无空格
    "1234567890" * 1000,                  # 纯数字
    " \t\n\r" * 500,                      # 各种空白符
]

# ===== 测试 =====


class TestFuzz:
    """随机文本 fuzz 测试 — 只验证不崩溃。"""

    def test_random_zh_10_iterations(self):
        """10 轮随机中文。"""
        s = SmartSentenceSplitter()
        for i in range(10):
            text = random_zh_text()
            try:
                r = s.split(text)
                assert r is not None
            except Exception as e:
                pytest.fail(f"Round {i} crashed: {e}")

    def test_random_en_10_iterations(self):
        """10 轮随机英文。"""
        s = SmartSentenceSplitter()
        for i in range(10):
            text = random_en_text()
            try:
                r = s.split(text)
                assert r is not None
            except Exception as e:
                pytest.fail(f"Round {i} crashed: {e}")

    def test_random_mixed_10_iterations(self):
        """10 轮随机中英混排。"""
        s = SmartSentenceSplitter()
        for i in range(10):
            text = random_mixed_text()
            try:
                r = s.split(text)
                assert r is not None
            except Exception as e:
                pytest.fail(f"Round {i} crashed: {e}")

    def test_extreme_cases(self):
        """极端场景不崩溃。"""
        s = SmartSentenceSplitter()
        for i, text in enumerate(EXTREME_CASES):
            try:
                r = s.split(text)
                assert r is not None
            except Exception as e:
                pytest.fail(f"Extreme case [{i}] crashed: {e}")

    def test_extreme_with_script_analysis(self):
        """启用剧本分析时极端场景不崩溃。"""
        s = SmartSentenceSplitter({"enable_script_analysis": True})
        for i, text in enumerate(EXTREME_CASES[:10]):  # 前 10 个
            try:
                r = s.split(text)
                assert r is not None
            except Exception as e:
                pytest.fail(f"Script + extreme [{i}] crashed: {e}")

    def test_batch_fuzz(self):
        """随机批量请求不崩溃。"""
        s = SmartSentenceSplitter()
        batch = [random_zh_text(5, 100) for _ in range(20)]
        for text in batch:
            try:
                r = s.split(text)
                assert r is not None
            except Exception as e:
                pytest.fail(f"Batch fuzz crashed: {e}")

    def test_modes_fast_balanced_precise(self):
        """三种模式在随机文本下不崩溃。"""
        text = random_zh_text(100, 500)
        for mode in ["fast", "balanced", "precise"]:
            try:
                s = SmartSentenceSplitter({"mode": mode})
                r = s.split(text)
                assert r is not None
            except Exception as e:
                pytest.fail(f"Mode '{mode}' crashed: {e}")

    def test_length_strategies(self):
        """A/B/off 三种字数策略在随机文本下不崩溃。"""
        text = random_zh_text(100, 500)
        for strategy in ["A", "B", "off"]:
            try:
                s = SmartSentenceSplitter({"length": {"strategy": strategy, "max_chars": 10}})
                r = s.split(text)
                assert r is not None
            except Exception as e:
                pytest.fail(f"Strategy '{strategy}' crashed: {e}")
