"""English language package."""

from .splitter import EnglishSplitter
from .tokenizer import WhitespaceTokenizer
from .abbreviations import EN_ABBREVIATIONS

__all__ = ["EnglishSplitter", "WhitespaceTokenizer", "EN_ABBREVIATIONS"]
