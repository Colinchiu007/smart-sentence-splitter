"""Scene segmenter (Layer 2).

将 SentenceBlock 列表合并为 SceneSegment。
规则：
- 不切断句子
- 目标字数 = target_seconds * base_words_per_second * speech_rate
- 上下界: min_words_per_segment / max_words_per_segment
- 语义边界优先：尽量在句子边界处切
"""

from __future__ import annotations
from typing import List

from ..models import SentenceBlock, SceneSegment


class SceneSegmenter:
    """场景级分割器。"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.target_seconds = self.config.get("target_seconds", 6.0)
        self.base_words_per_second = self.config.get("base_words_per_second", 3.3)
        self.speech_rate = self.config.get("speech_rate", 1.0)
        self.min_words = self.config.get("min_words_per_segment", 10)
        self.max_words = self.config.get("max_words_per_segment", 50)
        self.enforce_sentence_boundary = self.config.get("enforce_sentence_boundary", True)
        self.allow_single_sentence_overflow = self.config.get("allow_single_sentence_overflow", True)

    def calculate_target_words(self) -> int:
        """计算目标字数。"""
        target = int(self.target_seconds * self.base_words_per_second * self.speech_rate)
        return max(self.min_words, min(target, self.max_words))

    def segment(self, sentences: List[SentenceBlock]) -> List[SceneSegment]:
        """将 SentenceBlock 列表合并为 SceneSegment 列表。"""
        if not sentences:
            return []

        target_words = self.calculate_target_words()
        scenes: List[SceneSegment] = []
        current_sentences: List[SentenceBlock] = []
        current_word_count = 0
        scene_id = 0

        for sentence in sentences:
            sentence_len = len(sentence.text)

            # 决定是否需要开始新段落
            if not current_sentences:
                # 段落为空：必须接受
                current_sentences.append(sentence)
                current_word_count += sentence_len
            elif current_word_count + sentence_len <= target_words:
                # 未达上限，可以加入
                current_sentences.append(sentence)
                current_word_count += sentence_len
            else:
                # 已达上限，开始新段落
                scenes.append(self._create_scene(current_sentences, current_word_count, scene_id))
                scene_id += 1
                current_sentences = [sentence]
                current_word_count = sentence_len

        # 处理最后一个段落
        if current_sentences:
            scenes.append(self._create_scene(current_sentences, current_word_count, scene_id))

        return scenes

    def _create_scene(
        self,
        sentences: List[SentenceBlock],
        word_count: int,
        scene_id: int,
    ) -> SceneSegment:
        """构造 SceneSegment。"""
        text = "".join(s.text for s in sentences)
        estimated_duration = word_count / (self.base_words_per_second * self.speech_rate)
        return SceneSegment(
            text=text,
            segment_id=scene_id,
            estimated_duration=estimated_duration,
            target_words=word_count,
            sentences=list(sentences),
        )
