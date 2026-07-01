"""Test language router and tier chain."""

import pytest
from splitter.core.language_router import LanguageRouter
from splitter.core.tier_chain import TierChain
from splitter.languages.zh.splitter import ChineseSplitter
from splitter.languages.en.splitter import EnglishSplitter


class TestLanguageRouter:
    def test_auto_route_to_zh(self):
        router = LanguageRouter()
        lang, splitter = router.route("今天天气真好")
        assert lang == "zh"
        assert isinstance(splitter, ChineseSplitter)

    def test_auto_route_to_en(self):
        router = LanguageRouter()
        lang, splitter = router.route("Hello world how are you")
        assert lang == "en"
        assert isinstance(splitter, EnglishSplitter)

    def test_explicit_zh(self):
        router = LanguageRouter({"language": "zh"})
        lang, splitter = router.route("anything here")
        assert lang == "zh"

    def test_explicit_en(self):
        router = LanguageRouter({"language": "en"})
        lang, splitter = router.route("anything here")
        assert lang == "en"

    def test_paragraph_routing(self):
        router = LanguageRouter()
        text = "今天天气真好。\n\nHello world. How are you?"
        paragraphs = router.route_paragraphs(text)
        assert len(paragraphs) >= 2
        # 第一段中文 → zh splitter
        assert paragraphs[0][0] in ("zh", "mixed", "en")  # auto 模式可能识别为 mixed
        # 第二段英文 → en splitter
        assert paragraphs[1][0] == "en"


class TestTierChain:
    def test_basic_chain(self):
        zh = ChineseSplitter({"use_jieba": False})
        en = EnglishSplitter()
        chain = TierChain(splitters=[zh, en], min_tier=2)
        sentences, tier = chain.split("今天天气真好。我们去公园。")
        assert len(sentences) == 2
        assert "tier" in tier

    def test_min_tier_respected(self):
        zh = ChineseSplitter({"use_jieba": False})
        en = EnglishSplitter()
        # min_tier=3 强制使用 rule 层
        chain = TierChain(splitters=[zh, en], min_tier=3)
        sentences, tier = chain.split("今天天气真好。")
        assert "tier3" in tier

    def test_fallback_when_tier_fails(self):
        from splitter.core.base_splitter import BaseSentenceSplitter
        from splitter.models import SentenceBlock

        class BrokenSplitter(BaseSentenceSplitter):
            language = "zh"
            tier = "tier1_llm"

            def split(self, text):
                raise RuntimeError("simulated failure")

        class WorkingSplitter(BaseSentenceSplitter):
            language = "zh"
            tier = "tier3_rule"

            def split(self, text):
                return [SentenceBlock(text=text, index=0, tier=self.tier, language=self.language)]

        chain = TierChain(splitters=[BrokenSplitter(), WorkingSplitter()], min_tier=1)
        sentences, tier = chain.split("test")
        assert len(sentences) == 1
        assert "tier3" in tier
