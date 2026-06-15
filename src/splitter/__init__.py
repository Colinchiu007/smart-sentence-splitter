"""Smart Sentence Splitter - 语义分句引擎.

PROJECT-012 主包入口。
"""

from .pipeline import SmartSentenceSplitter
from .models import (
    SentenceBlock,
    SceneSegment,
    SubtitleBlock,
    EraInfo,
    SplitResult,
)
from .utils.config_loader import load_config

__version__ = "0.9.3"

__all__ = [
    "SmartSentenceSplitter",
    "SentenceBlock",
    "SceneSegment",
    "SubtitleBlock",
    "EraInfo",
    "SplitResult",
    "load_config",
]
