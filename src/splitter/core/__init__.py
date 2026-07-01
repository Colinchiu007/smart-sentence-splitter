"""Core abstractions and abstract base classes."""

from .base_splitter import BaseSentenceSplitter
from .base_tokenizer import BaseTokenizer

__all__ = ["BaseSentenceSplitter", "BaseTokenizer"]
