"""Test postprocessor chain."""

import pytest
from splitter.postprocessor import BasePostprocessor, PostprocessorChain, CustomMergingProcessor
from splitter.models import SplitResult, SentenceBlock, SceneSegment


class TestPostprocessorChain:
    def test_empty_chain(self):
        chain = PostprocessorChain()
        r = SplitResult()
        result = chain.run(r)
        assert result is r

    def test_custom_merging_no_config(self):
        # 没有 user_dict_path 时不应报错
        proc = CustomMergingProcessor({})
        assert proc.is_available() is True

    def test_chain_with_custom(self):
        from splitter.languages.zh.custom import Customization
        proc = CustomMergingProcessor({})
        # 手动加词
        proc.custom = Customization()
        proc.custom.add_word("自然语言处理")
        result = SplitResult(
            sentences=[
                SentenceBlock(text="自然", index=0),
                SentenceBlock(text="语言", index=1),
                SentenceBlock(text="处理", index=2),
            ],
            scenes=[SceneSegment(text="自然语言处理", segment_id=0, estimated_duration=6.0, target_words=5)],
            language="zh",
        )
        chain = PostprocessorChain([proc])
        new_result = chain.run(result)
        assert any("自然语言处理" in s.text for s in new_result.sentences)


class TestCustomMergingProcessor:
    def test_no_custom_no_change(self):
        proc = CustomMergingProcessor({})
        sents = [SentenceBlock(text="测试", index=0)]
        result = SplitResult(sentences=sents, language="zh")
        new = proc.adjust(result)
        assert len(new.sentences) == 1
        assert new.sentences[0].text == "测试"