"""ScriptAnalyzer — 剧本分析器 (v0.7 新增, v0.9.5 增强).

从完整剧本文本提取:
- 角色列表 (人名 → jieba nr tag + 信号词 + 频率阈值)
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
from collections import Counter

logger = logging.getLogger(__name__)

# 角色信号词 (跟在人名后面的动作/说话词)
CHARACTER_SIGNAL_WORDS = [
    "说",
    "走",
    "去",
    "来",
    "看",
    "跑",
    "喊",
    "叫",
    "问",
    "答",
]

# 场景切换信号词 — 也用于角色提取
LOCATION_TRANSITION_VERBS = [
    "走进",
    "来到",
    "回到",
    "离开",
    "进入",
    "走出",
    "跑到",
    "冲向",
    "赶往",
    "前往",
    "返回",
    "到达",
    "走出",
    "踏入",
    "跨入",
    "转入",
]

# 2字信号词 (角色后跟"走进", "离开"等, 也说明这是角色)
CHARACTER_TRANSITION_VERBS = LOCATION_TRANSITION_VERBS + [
    "打开",
    "关上",
    "坐到",
    "站在",
    "看着",
    "听到",
]

# 地点后缀词（多字明确地点词，避免单字后缀误匹配）
LOCATION_SUFFIXES = [
    "超市",
    "商店",
    "学校",
    "医院",
    "公园",
    "广场",
    "公司",
    "办公室",
    "房间",
    "厨房",
    "卧室",
    "街道",
    "马路",
    "小区",
    "大楼",
    "餐厅",
    "饭店",
    "咖啡馆",
    "酒吧",
    "森林",
    "山上",
    "河边",
    "海边",
    "城市",
    "农村",
    "小镇",
    "村庄",
    "世界",
    "战场",
    "基地",
    "避难所",
    "体育馆",
    "图书馆",
    "博物馆",
    "电影院",
    "车站",
    "机场",
    "码头",
    "港口",
    "宫殿",
    "寺庙",
    "教堂",
    "城堡",
    "国家",
    "地区",
    "岛屿",
    "沙滩",
    "海岸",
    "餐厅",
    "饭店",
    "餐馆",
    "食堂",
]

# 单字非人名过滤 + 多字停用词
STOP_NAMES = {"你", "我", "他", "她", "它", "们", "人", "谁", "这", "那"}
STOP_MULTI_WORDS = {"我们", "你们", "他们", "她们", "它们", "自己", "大家", "别人"}

# 小X/阿X/老X 模式已够, 以下是额外禁止开头的过滤
BAD_CHAR_STARTS = {
    "了",
    "的",
    "把",
    "被",
    "将",
    "从",
    "到",
    "去",
    "在",
    "又",
    "再",
    "才",
    "就",
    "是",
    "很",
    "太",
    "还",
    "已",
    "正在",
    "已经",
    "然后",
    "后来",
    "终于",
    "放学",
    "出发",
    "回来",
    "出去",
    "进来",
}

# 特定语境下的"角色误判" — 这些词即使被 jieba 标记为 nr 也不应该保留
COMMON_NOUN_FALSE_NR = {
    "老师",
    "学生",
    "医生",
    "护士",
    "警察",
    "店员",
    "大人",
    "孩子",
    "男人",
    "女人",
    "朋友",
    "同学",
    "顾客",
    "客人",
    "主角",
    "配角",
}

# 角色名不应含的后缀 (描述性文本中的片段, 非人物)
CHARACTER_BAD_SUFFIXES = [
    "的人",
    "的事",
    "的东西",
    "的地方",
    "的时候",
    "的方式",
    "的感觉",
    "的味道",
    "的声音",
    "的样子",
    "的原因",
    "的结果",
    "的问题",
    "的机会",
    "的经历",
    "的体验",
    "的感受",
    "的故事",
]


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

    # ===== 角色提取 (增强版) =====

    def extract_characters(self, text: str) -> List[str]:
        """提取角色名列表。

        策略:
        1. 收集候选 (jieba nr / 小X / 信号词 / 过渡词)
        2. 去重 + 过滤停用词 + 过滤通用名词
        3. 频率阈值: 出现≥2次 或 有信号词匹配
        """
        if not text or not text.strip():
            return []
        if self._jieba_available:
            return self._extract_characters_jieba(text)
        return self._extract_characters_fallback(text)

    def _extract_characters_jieba(self, text: str) -> List[str]:
        """用 jieba 词性标注 + 信号词增强 + 频率阈值提取角色。"""
        from jieba import posseg as pseg
        from collections import Counter

        candidates: Set[str] = set()
        signal_matched: Set[str] = set()

        # Step 1: jieba nr 标签
        words = pseg.cut(text)
        for word, flag in words:
            if flag.startswith("nr") and len(word) >= 2 and word not in STOP_NAMES and word not in STOP_MULTI_WORDS:
                if word not in COMMON_NOUN_FALSE_NR:
                    candidates.add(word)

        # Step 2: 小X / 阿X / 老X 模式 (jieba nr 常遗漏昵称)
        for m in re.finditer(r"(?:[小阿老])([\u4e00-\u9fff])", text):
            name = m.group(0)
            if (
                len(name) >= 2
                and name not in STOP_NAMES
                and name not in STOP_MULTI_WORDS
                and name not in COMMON_NOUN_FALSE_NR
            ):
                candidates.add(name)

        # Step 3: 信号词前人名 (说/走/去/来等, 一字节信号词)
        # 注意: 限制捕获2-3字, 避免"红走进来"→"红走进"等假阳性
        for sig in CHARACTER_SIGNAL_WORDS:
            pattern = rf"([\u4e00-\u9fff]{{2,3}})(?:{re.escape(sig)})"
            for m in re.finditer(pattern, text):
                name = m.group(1)
                if name not in STOP_NAMES and not any(name.startswith(bs) for bs in BAD_CHAR_STARTS):
                    candidates.add(name)
                    signal_matched.add(name)

        # Step 4: 过渡动词前人名 (走进/离开/打开等, 双字节动词)
        for verb in CHARACTER_TRANSITION_VERBS:
            pattern = rf"([\u4e00-\u9fff]{{2,4}})(?:{re.escape(verb)})"
            for m in re.finditer(pattern, text):
                name = m.group(1)
                if name not in STOP_NAMES and not any(name.startswith(bs) for bs in BAD_CHAR_STARTS):
                    candidates.add(name)
                    signal_matched.add(name)

        # Step 5: 频率阈值 — 统计全文出现次数
        freq = Counter()
        for cand in candidates:
            freq[cand] = text.count(cand)

        # 保留规则:
        # - 出现≥2次 或
        # - 有信号词匹配 或
        # - 小X/阿X/老X模式 (保留2字以上昵称, 虽然可能含"小吃"误报)
        result: Set[str] = set()
        for cand in candidates:
            if cand in COMMON_NOUN_FALSE_NR:
                continue
            if any(cand.endswith(suf) for suf in CHARACTER_BAD_SUFFIXES):
                continue
            if freq[cand] >= 2:
                result.add(cand)
            elif cand in signal_matched:
                result.add(cand)
            elif re.match(r"^[小阿老]", cand) and len(cand) >= 2:
                result.add(cand)

        return sorted(result)

    @staticmethod
    def _get_bad_starts() -> Set[str]:
        """获取非人名开头词表。"""
        return BAD_CHAR_STARTS.copy()

    def _extract_characters_fallback(self, text: str) -> List[str]:
        """无 jieba 时: 句首启发式 + 小X模式 + 频率。"""
        chars: Set[str] = set()
        signal_matched: Set[str] = set()
        sentences = re.split(r"[。！？；.!?;]", text)

        # 1) 句首 + 信号词 (一字节, 限制捕获2-3字)
        for sig in CHARACTER_SIGNAL_WORDS:
            pattern = rf"^([\u4e00-\u9fff]{{2,3}}){re.escape(sig)}"
            for s in sentences:
                s = s.strip()
                if not s:
                    continue
                match = re.match(pattern, s)
                if match and match.group(1) not in STOP_NAMES and match.group(1) not in STOP_MULTI_WORDS:
                    chars.add(match.group(1))
                    signal_matched.add(match.group(1))

        # 2) 句首 + 过渡动词 (双字节)
        for verb in CHARACTER_TRANSITION_VERBS:
            pattern = rf"^([\u4e00-\u9fff]{{2,4}}){re.escape(verb)}"
            for s in sentences:
                s = s.strip()
                if not s:
                    continue
                match = re.match(pattern, s)
                if match and match.group(1) not in STOP_NAMES and match.group(1) not in STOP_MULTI_WORDS:
                    chars.add(match.group(1))
                    signal_matched.add(match.group(1))

        # 3) 小X / 阿X 模式
        for m in re.finditer(r"(?:[小阿老])([\u4e00-\u9fff])", text):
            name = m.group(0)
            if len(name) >= 2 and name not in STOP_NAMES and name not in STOP_MULTI_WORDS:
                chars.add(name)

        # 4) 频率过滤
        freq = Counter()
        for cand in chars:
            freq[cand] = text.count(cand)

        result: Set[str] = set()
        for cand in chars:
            # 通用名词过滤
            if cand in COMMON_NOUN_FALSE_NR:
                continue
            # 描述性后缀过滤 (的人/的事等)
            if any(cand.endswith(suf) for suf in CHARACTER_BAD_SUFFIXES):
                continue
            if freq[cand] >= 2:
                result.add(cand)
            elif cand in signal_matched:
                result.add(cand)
            # 小X模式 (2字以上昵称, 保留)
            elif re.match(r"^[小阿老]", cand) and len(cand) >= 2:
                result.add(cand)

        return sorted(result)

    # ===== 梗概提取 =====

    def extract_synopsis(self, text: str, max_chars: int = 200) -> str:
        """从文本第一段提取梗概。"""
        if not text or not text.strip():
            return ""
        paragraphs = re.split(r"\n\s*\n", text.strip())
        first = paragraphs[0].strip().replace("\n", "")
        if len(first) <= max_chars:
            return first
        return first[:max_chars] + "..."

    # ===== 场景/地点提取 =====

    def extract_settings(self, text: str) -> List[str]:
        """提取地点/场景名称。"""
        settings: Set[str] = set()
        if self._jieba_available:
            from jieba import posseg as pseg

            words = pseg.cut(text)
            for word, flag in words:
                if flag.startswith("ns") and len(word) >= 2 and word not in STOP_NAMES:
                    if self._is_valid_location(word):
                        settings.add(word)
        for suffix in LOCATION_SUFFIXES:
            if suffix in text:
                settings.add(suffix)
            # 带前导字的组合地点（前面不能是中文，避免截断完整词汇）
            pattern = f"(?<![\u4e00-\u9fff])([\u4e00-\u9fff]{{1,4}}{re.escape(suffix)})"
            for m in re.finditer(pattern, text):
                loc = m.group(1)
                if self._is_valid_location(loc):
                    settings.add(loc)
        return sorted(settings)

    @staticmethod
    def _is_valid_location(loc: str) -> bool:
        """过滤非地点匹配。"""
        bad_starts = {
            "这",
            "那",
            "哪",
            "各",
            "某",
            "全",
            "整",
            "同",
            "大",
            "小",
            "老",
            "新",
            "旧",
            "前",
            "后",
            "左",
            "右",
            "东",
            "西",
            "南",
            "北",
            "上",
            "下",
            "里",
            "外",
            "有",
            "没",
            "在",
            "是",
            "的",
            "了",
            "着",
            "过",
            "我",
            "你",
            "他",
            "她",
            "它",
            "们",
            "被",
            "把",
            "将",
            "从",
            "向",
            "往",
            "对",
            "用",
            "然后",
            "最后",
            "之后",
            "以前",
            "以后",
        }
        if len(loc) <= 1:
            return False
        first_char = loc[0]
        if first_char in bad_starts or first_char in bad_starts:
            return False
        for bs in bad_starts:
            if loc.startswith(bs):
                return False
        return True

    # ===== 关键词提取 =====

    def extract_key_terms(self, text: str) -> List[str]:
        """提取高频关键词。"""
        if not self._jieba_available:
            return []
        import jieba

        words = jieba.lcut(text)
        # 过滤停用词 + 短词
        filtered = [
            w
            for w in words
            if len(w) >= 2 and w not in STOP_NAMES and not any(w.startswith(bs) for bs in BAD_CHAR_STARTS)
        ]
        freq = Counter(filtered)
        return [w for w, _ in freq.most_common(10)]

    # ===== 场景变化检测 =====

    def detect_scene_changes(self, sentences: List) -> List[Dict]:
        """检测场景切换点。"""
        changes = []
        for i, sentence in enumerate(sentences):
            text = sentence.text if hasattr(sentence, "text") else sentence
            location = self._detect_location(text)
            if location:
                changes.append({"sentence_idx": i, "location": location})
        return changes

    def _detect_location(self, sentence: str) -> Optional[str]:
        """检测单句中是否有地点变化。"""
        for verb in LOCATION_TRANSITION_VERBS:
            if verb in sentence:
                after = sentence.split(verb, 1)[1]
                while after and after[0] in "了着过的":
                    after = after[1:]
                for suffix in LOCATION_SUFFIXES:
                    idx = after.find(suffix)
                    if idx >= 0:
                        loc = after[: idx + len(suffix)]
                        if self._is_valid_location(loc):
                            return loc
        return None
