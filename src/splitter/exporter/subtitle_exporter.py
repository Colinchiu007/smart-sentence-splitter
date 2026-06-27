"""SubtitleExporter — SRT/ASS 字幕格式导出 (v0.8 新增).

将 SceneSegment[] (含 SubtitleBlock) 导出为:
- SRT (SubRip): 最通用, 简单时间戳 + 文本
- ASS (Advanced SubStation Alpha): 带样式, 字体/颜色/位置可控

设计要点:
- 跨场景时累加时间偏移
- 零依赖, 纯字符串拼接
"""

from __future__ import annotations
from typing import List
from ..models import SceneSegment, SubtitleBlock


# ASS 样式表
ASS_DEFAULT_STYLE = """[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,10,10,10,1"""


ASS_HEADER = """[Script Info]
Title: Smart Sentence Splitter Output
ScriptType: v4.00+
Collisions: Normal
PlayResX: 1920
PlayResY: 1080

"""


class SubtitleExporter:
    """字幕导出器 — SRT/ASS 两种格式。"""

    def to_srt(self, scenes: List[SceneSegment]) -> str:
        """导出 SRT 格式字幕。

        Args:
            scenes: SceneSegment 列表 (含 subtitles)

        Returns:
            SRT 格式字符串
        """
        if not scenes:
            return ""

        blocks: List[str] = []
        current_time = 0.0
        global_index = 1

        for scene in scenes:
            for sub in scene.subtitles:
                start = current_time + sub.start_time
                end = start + sub.duration
                text = sub.text.replace("\n", " ")
                blocks.append(
                    f"{global_index}\n{self._format_srt_time(start)} --> {self._format_srt_time(end)}\n{text}\n"
                )
                global_index += 1
            # 累加场景时长
            current_time += scene.estimated_duration

        return "\n".join(blocks)

    def to_ass(self, scenes: List[SceneSegment]) -> str:
        """导出 ASS 格式字幕。"""
        if not scenes:
            return ASS_HEADER + ASS_DEFAULT_STYLE + "\n\n[Events]\n"

        lines: List[str] = []
        lines.append(ASS_HEADER)
        lines.append(ASS_DEFAULT_STYLE)
        lines.append("")
        lines.append("[Events]")
        lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")

        current_time = 0.0
        for scene in scenes:
            for sub in scene.subtitles:
                start = current_time + sub.start_time
                end = start + sub.duration
                # ASS 中换行用 \N
                text = sub.text.replace("\n", r"\N")
                # 角色名作为 Name 字段
                name = ",".join(scene.characters) if scene.characters else ""
                lines.append(
                    f"Dialogue: 0,{self._format_ass_time(start)},{self._format_ass_time(end)},Default,{name},0,0,0,,{text}"
                )
            current_time += scene.estimated_duration

        return "\n".join(lines)

    def count_subtitles(self, scenes: List[SceneSegment]) -> int:
        """统计总字幕块数。"""
        return sum(len(s.subtitles) for s in scenes)

    def total_duration(self, scenes: List[SceneSegment]) -> float:
        """总时长 (秒)。"""
        return sum(s.estimated_duration for s in scenes)

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        """SRT 时间格式: HH:MM:SS,mmm (逗号)"""
        if seconds < 0:
            seconds = 0.0
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    def _format_ass_time(seconds: float) -> str:
        """ASS 时间格式: H:MM:SS.cc (点)"""
        if seconds < 0:
            seconds = 0.0
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds - int(seconds)) * 100)
        return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"
