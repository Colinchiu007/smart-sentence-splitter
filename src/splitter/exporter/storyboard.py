"""StoryboardExporter — 分镜输出格式 (v0.7 新增).

将分句结果转换成分镜 JSON 格式，供 PROJECT-011 消费。

输出格式:
{
  "story_synopsis": "...",
  "characters": [{"name": "...", "description": "..."}],
  "settings": ["..."],
  "total_scenes": 3,
  "total_duration": 15.5,
  "scenes": [
    {
      "scene_id": 0,
      "text": "...",
      "duration_s": 5.2,
      "characters": ["小明"],
      "setting": "超市",
      "mood": "焦虑",
      "phase": "开头",
      "image_hint": "小明在超市, 焦虑, 现代",
      "era": "modern",
    }
  ]
}
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from ..models import SceneSegment


class StoryboardExporter:
    """分镜导出器。"""

    def to_storyboard(
        self,
        scenes: List[SceneSegment],
        synopsis: str = "",
        characters: Optional[List[Dict[str, str]]] = None,
        settings: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """SceneSegment[] → 完整分镜 JSON。

        Args:
            scenes: 场景列表
            synopsis: 故事梗概
            characters: 角色列表 [{name, description}]
            settings: 场景/地点列表
        """
        total_duration = sum(s.estimated_duration for s in scenes)
        scene_items = [self._scene_to_item(s) for s in scenes]

        return {
            "story_synopsis": synopsis,
            "characters": characters or [],
            "settings": settings or [],
            "total_scenes": len(scenes),
            "total_duration": round(total_duration, 2),
            "scenes": scene_items,
        }

    def _scene_to_item(self, scene: SceneSegment) -> Dict[str, Any]:
        """单个 SceneSegment → 分镜条目。"""
        era = scene.era_info.era if scene.era_info else None
        return {
            "scene_id": scene.segment_id,
            "text": scene.text,
            "duration_s": round(scene.estimated_duration, 2),
            "characters": scene.characters,
            "setting": scene.setting,
            "mood": scene.mood,
            "phase": scene.story_phase,
            "image_hint": scene.to_image_hint(),
            "era": era,
            "scene_context": {
                "previous_setting": "",  # 由下游填充
                "next_setting": "",
                "characters_here": scene.characters,
            },
        }
