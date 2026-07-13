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
        has_topic_boundaries = any(s.is_topic_boundary for s in sentences)
        # 如果有 topic 边界, 提高字数阈值避免字数切的碎片化
        if has_topic_boundaries:
            effective_target = target_words * 3
        else:
            effective_target = target_words

        scenes: List[SceneSegment] = []
        current_sentences: List[SentenceBlock] = []
        current_word_count = 0
        scene_id = 0

        for sentence in sentences:
            sentence_len = len(sentence.text)

            # v0.9.10: 主题边界 → 强制新段落
            if sentence.is_topic_boundary and not has_topic_boundaries:
                # 没有主题边界时当作普通句子处理
                pass
            if sentence.is_topic_boundary and current_sentences:
                scenes.append(self._create_scene(current_sentences[:], current_word_count, scene_id))
                scene_id += 1
                current_sentences = [sentence]
                current_word_count = sentence_len
                continue

            # 字数检查
            if not current_sentences:
                current_sentences.append(sentence)
                current_word_count += sentence_len
            elif current_word_count + sentence_len <= effective_target:
                current_sentences.append(sentence)
                current_word_count += sentence_len
            elif self.allow_single_sentence_overflow and len(current_sentences) <= 1:
                # 允许单句溢出: 当前场景只有1句时继续追加，避免孤立场景
                current_sentences.append(sentence)
                current_word_count += sentence_len
            else:
                scenes.append(self._create_scene(current_sentences[:], current_word_count, scene_id))
                scene_id += 1
                current_sentences = [sentence]
                current_word_count = sentence_len

        # 处理最后一个段落
        if current_sentences:
            scenes.append(self._create_scene(current_sentences, current_word_count, scene_id))

        return scenes

    TERMINAL_PUNCTUATION = frozenset("。！？；.!?;\n")

    def _create_scene(
        self,
        sentences: List[SentenceBlock],
        word_count: int,
        scene_id: int,
    ) -> SceneSegment:
        """构造 SceneSegment。

        拼接句子时，若前句无终止标点且后句非空，自动补句号避免粘连。
        """
        parts = []
        for i, s in enumerate(sentences):
            if i > 0 and s.text.strip():
                prev = parts[-1]
                if prev and prev[-1] not in self.TERMINAL_PUNCTUATION:
                    parts.append("。" + s.text)
                else:
                    parts.append(s.text)
            else:
                parts.append(s.text)
        text = "".join(parts)
        estimated_duration = word_count / (self.base_words_per_second * self.speech_rate)
        return SceneSegment(
            text=text,
            segment_id=scene_id,
            estimated_duration=estimated_duration,
            target_words=word_count,
            sentences=list(sentences),
        )
