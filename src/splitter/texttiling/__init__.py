"""TextTiling topic segmentation module.

包含：
- TextTiling: 算法核心
- TopicBoundary: 边界标记 dataclass
- TextTilingSemanticSplitter: 集成到 BaseSentenceSplitter 的 splitter
"""

from .texttiling import TextTiling, TopicBoundary
from .splitter import TextTilingSemanticSplitter
from .sentence_similarity import cosine_similarity, jaccard_similarity

__all__ = [
    "TextTiling",
    "TopicBoundary",
    "TextTilingSemanticSplitter",
    "cosine_similarity",
    "jaccard_similarity",
]
