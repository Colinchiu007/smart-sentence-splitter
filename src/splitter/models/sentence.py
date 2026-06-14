"""SentenceBlock data model."""

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class SentenceBlock:
    """语义分句结果中的一个句子。

    Attributes:
        text: 句子原始文本
        index: 全局序号（从0开始）
        char_count: 字符数
        word_count: 词数（jieba 分词结果；英文为空白分词数）
        words: 分词结果列表
        pos_tags: 词性标注（与 words 一一对应；英文可为空）
        language: 该句语言标签（zh / en / ja / mixed）
        tier: 来源 tier 名称（tier1_llm / tier2_semantic / tier3_rule）
        confidence: 置信度 0-1
        is_topic_boundary: 是否为主题边界标记（v0.2 TextTiling 用）
        topic_depth_score: 主题边界深度评分（仅 is_topic_boundary=True 时有值）
    """

    text: str
    index: int
    char_count: int = 0
    word_count: int = 0
    words: List[str] = field(default_factory=list)
    pos_tags: List[str] = field(default_factory=list)
    language: str = "zh"
    tier: str = "tier3_rule"
    confidence: float = 1.0
    is_topic_boundary: bool = False
    topic_depth_score: float = 0.0
    # v0.6 新增字段
    length_status: str = "ok"  # ok | too_short | too_long
    length_strategy_applied: str = "none"  # none | A | B

    def __post_init__(self):
        if not self.text:
            raise ValueError("SentenceBlock.text cannot be empty")
        if self.char_count == 0:
            self.char_count = len(self.text)
        if self.index < 0:
            raise ValueError("SentenceBlock.index must be >= 0")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("SentenceBlock.confidence must be in [0, 1]")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SentenceBlock":
        return cls(**data)
