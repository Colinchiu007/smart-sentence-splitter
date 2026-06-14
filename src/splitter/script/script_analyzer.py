"""ScriptAnalyzer — 剧本分析器 (v0.7 新增).

从完整剧本文本提取:
- 角色列表 (人名 → jieba nr tag)
- 故事梗概 (第一段)
- 地点/场景列表 (地名实体)
- 关键词表 (高频名词)
- 场景变化检测 (地点变化 → 新场景)

设计原则:
- 零 LLM 依赖, 纯规则+jieba
- jieba 是可选依赖 (无 jieba 时降级为字符启发式)
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Set
import re
import logging

logger = logging.getLogger(__name__)

# 场景切换信号词
LOCATION_TRANSITION_VERBS = [
    "走进", "来到", "回到", "离开", "进入", "走出",
    "跑到", "冲向", "赶往", "前往", "返回", "到达",
    "走出", "踏入", "跨入", "转入",
]

# 地点后缀词
LOCATION_SUFFIXES = [
    "里", "外", "上", "下", "前", "后",
    "超市", "商店", "学校", "医院", "公园", "广场",
    "家", "公司", "办公室", "房间", "厨房", "卧室",
    "街道", "马路", "小区", "大楼", "楼",
    "餐厅", "饭店", "咖啡馆", "酒吧",
    "森林", "河边", "山上", "海边",
    "城市", "农村", "小镇", "村庄",
    "世界", "战场", "基地", "避难所",
]

# 单字非人名过滤
STOP_NAMES = {"你", "我", "他", "她", "它", "们", "人", "谁", "这", "那"}


class ScriptAnalyzer:
    """剧本分析器。"""

    def __init__(self):
        self._jieba_available = False
        try:
            import jieba.posseg as pseg  # noqa
            self._jieba_available = True
        except ImportError:
            logger.warning("jieba not available, using fallback character heuristic")

    def analyze(self, text: str) -> Dict[str, Any]:
        """完整分析管道。"""
        characters = self.extract_characters(text)
        synopsis = self.extract_synopsis(text)
        settings = self.extract_settings(text)
        key_terms = self.extract_key_terms(text)
        return {
            "characters": characters,
            "synopsis": synopsis,
            "settings": settings,
            "key_terms": key_terms,
        }

    # ===== 角色提取 =====

    def extract_characters(self, text: str) -> List[str]:
        """提取角色名列表。

        用 jieba 词性标注提取 nr (人名), 去重 + 过滤停用词。
        无 jieba 时: 用正则找"xx走"/"xx说"模式的 2-3 字词。
        """
        if not text or not text.strip():
            return []
        if self._jieba_available:
            return self._extract_characters_jieba(text)
        return self._extract_characters_fallback(text)

    def _extract_characters_jieba(self, text: str) -> List[str]:
        from jieba import posseg as pseg
        chars: Set[str] = set()
        words = pseg.cut(text)
        for word, flag in words:
            if flag.startswith("nr") and len(word) >= 2 and word not in STOP_NAMES:
                chars.add(word)
        return sorted(chars)

    def _extract_characters_fallback(self, text: str) -> List[str]:
        """无 jieba 时: 提取句首 2-3 字的名词 (启发式)。"""
        chars: Set[str] = set()
        sentences = re.split(r'[。！？；.!?;]', text)
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            # 句首 2-3 字可能的人名
            match = re.match(r'^([\u4e00-\u9fff]{2,4})[说走看跑问叫喊]', s)
            if match and match.group(1) not in STOP_NAMES:
                chars.add(match.group(1))
        return sorted(chars)

    # ===== 梗概提取 =====

    def extract_synopsis(self, text: str, max_chars: int = 200) -> str:
        """从文本第一段提取梗概。"""
        if not text or not text.strip():
            return ""
        # 按双换行分割段落
        paragraphs = re.split(r'\n\s*\n', text.strip())
        first = paragraphs[0].strip().replace('\n', '')
        if len(first) <= max_chars:
            return first
        return first[:max_chars] + "..."

    # ===== 场景/地点提取 =====

    def extract_settings(self, text: str) -> List[str]:
        """提取地点/场景名称。"""
        settings: Set[str] = set()
        # 使用 jieba ns 标签
        if self._jieba_available:
            from jieba import posseg as pseg
            words = pseg.cut(text)
            for word, flag in words:
                if flag.startswith("ns") and len(word) >= 2 and word not in STOP_NAMES:
                    settings.add(word)
        # jieba ns 不总能覆盖, 用后缀补充 — 只加文本中实际出现的
        for suffix in LOCATION_SUFFIXES:
            # 后缀本身在文本中独立出现
            if len(suffix) >= 2 and suffix in text:
                settings.add(suffix)
            # 带前导字的组合地点
            pattern = rf'([\u4e00-\u9fff]{{1,4}}{suffix})'
            for m in re.finditer(pattern, text):
                loc = m.group(1)
                if self._is_valid_location(loc):
                    settings.add(loc)
        return sorted(settings)

    # ===== 关键词提取 =====

    def extract_key_terms(self, text: str, top_n: int = 20) -> List[str]:
        """提取高频关键词（≥2 字名词）。"""
        import collections
        if not self._jieba_available:
            return []
        import jieba
        words = jieba.lcut(text)
        counter = collections.Counter(
            w for w in words if len(w) >= 2 and w not in STOP_NAMES
        )
        return [w for w, _ in counter.most_common(top_n)]

    # ===== 场景变化检测 =====

    def detect_scene_changes(
        self, sentences: List[str]
    ) -> List[Dict[str, Any]]:
        """检测场景变化点。

        Returns:
            List of {sentence_idx, location, change_type}
        """
        changes: List[Dict[str, Any]] = []
        current_location = ""

        for i, sentence in enumerate(sentences):
            detected_location = self._detect_location(sentence)
            if detected_location and detected_location != current_location:
                changes.append({
                    "sentence_idx": i,
                    "location": detected_location,
                    "change_type": "location",
                })
                current_location = detected_location
        return changes

    def _detect_location(self, sentence: str) -> Optional[str]:
        """检测单句中是否有地点变化。"""
        # 1. 先找信号词
        for verb in LOCATION_TRANSITION_VERBS:
            if verb in sentence:
                after = sentence.split(verb, 1)[1]
                for suffix in LOCATION_SUFFIXES:
                    idx = after.find(suffix)
                    if idx >= 0:
                        # 取信号词后到 suffix 结束
                        loc = after[:idx + len(suffix)]
                        # 过滤明显不是地名的
                        if self._is_valid_location(loc):
                            return loc
        # 2. 没有信号词: 看句中有无独立出现的地名
        for suffix in LOCATION_SUFFIXES:
            idx = sentence.find(suffix)
            if idx >= 0:
                # 取后缀前 2-3 字
                start = max(0, idx - 3)
                loc = sentence[start:idx + len(suffix)]
                if self._is_valid_location(loc):
                    return loc
        return None

    def _is_valid_location(self, loc: str) -> bool:
        """检查地点字符串是否合理。"""
        loc = loc.strip()
        if len(loc) < 2 or len(loc) > 8:
            return False
        # 必须以后缀结尾
        if not any(loc.endswith(s) for s in LOCATION_SUFFIXES):
            return False
        # 过滤动词/介词开头
        bad_starts = {"了", "的", "把", "被", "将", "从", "到", "去", "在",
                       "又", "再", "才", "就", "是", "很", "太", "还", "已",
                       "正在", "已经", "然后", "后来", "终于", "后来", "后又",
                       "放学", "出发", "回来", "出去", "进来",
                       "小明", "小红", "小王", "小李", "小张", "老王", "老李",
                       "他", "她", "它", "你", "我", "们"}
        for bs in bad_starts:
            if loc.startswith(bs):
                return False
        # 过滤以地点信号词开头的
        for verb in LOCATION_TRANSITION_VERBS:
            if loc.startswith(verb):
                return False
        return True