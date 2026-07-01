"""Language detection utility (zero-dependency, heuristic-based).

检测策略（零依赖启发式）：
1. 统计 CJK 字符比例
2. 统计 ASCII 字母比例
3. 统计假名比例（平假名+片假名）

判定规则：
- CJK 比例 > 30% → zh
- CJK + 假名 > 30% → ja
- ASCII 比例 > 90% → en
- 都不满足 → mixed
"""

from __future__ import annotations
from typing import Tuple


def is_chinese(char: str) -> bool:
    """判断单个字符是否属于 CJK 统一汉字。"""
    if not char:
        return False
    code = ord(char)
    return (
        0x4E00 <= code <= 0x9FFF  # CJK Unified Ideographs
        or 0x3400 <= code <= 0x4DBF  # CJK Extension A
        or 0x20000 <= code <= 0x2A6DF  # CJK Extension B
    )


def is_japanese_kana(char: str) -> bool:
    """判断单个字符是否为日文假名。"""
    if not char:
        return False
    code = ord(char)
    return (
        0x3040 <= code <= 0x309F  # Hiragana
        or 0x30A0 <= code <= 0x30FF  # Katakana
    )


def is_english_letter(char: str) -> bool:
    """判断单个字符是否为英文字母。"""
    if not char:
        return False
    return char.isascii() and char.isalpha()


def detect_language(text: str) -> str:
    """检测文本的主要语言。

    Args:
        text: 输入文本

    Returns:
        "zh" | "en" | "ja" | "mixed"
    """
    if not text or not text.strip():
        return "zh"  # 兜底

    text = text.strip()
    cjk_count = 0
    kana_count = 0
    ascii_letter_count = 0
    total_meaningful = 0

    for char in text:
        if char.isspace() or char in ".,!?;:\"'()[]{}，。！？；：（）【】":
            continue
        total_meaningful += 1
        if is_chinese(char):
            cjk_count += 1
        elif is_japanese_kana(char):
            kana_count += 1
        elif is_english_letter(char):
            ascii_letter_count += 1

    if total_meaningful == 0:
        return "zh"

    cjk_ratio = cjk_count / total_meaningful
    kana_ratio = kana_count / total_meaningful
    ascii_ratio = ascii_letter_count / total_meaningful

    # 假名存在 → 日文
    if kana_ratio > 0.1:
        return "ja"

    # CJK 占主导 → 中文
    if cjk_ratio > 0.3:
        # 但如果有较多英文 → mixed
        if ascii_ratio > 0.2:
            return "mixed"
        return "zh"

    # ASCII 英文占主导
    if ascii_ratio > 0.9:
        return "en"

    # 都不满足 → mixed
    return "mixed"


def detect_language_with_confidence(text: str) -> Tuple[str, float]:
    """检测语言并返回置信度（0-1）。"""
    if not text or not text.strip():
        return "zh", 0.0

    text = text.strip()
    cjk_count = sum(1 for c in text if is_chinese(c))
    kana_count = sum(1 for c in text if is_japanese_kana(c))
    ascii_letter_count = sum(1 for c in text if is_english_letter(c))
    total = cjk_count + kana_count + ascii_letter_count
    if total == 0:
        return "zh", 0.0

    lang = detect_language(text)
    if lang == "ja":
        confidence = (kana_count + cjk_count) / total
    elif lang == "zh":
        confidence = cjk_count / total
    elif lang == "en":
        confidence = ascii_letter_count / total
    else:  # mixed
        confidence = 0.5

    return lang, round(confidence, 2)
