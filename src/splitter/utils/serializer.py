"""JSON serializer utility."""

from __future__ import annotations
from typing import Any, Union
from pathlib import Path
import json


def to_json(obj: Any, ensure_ascii: bool = False, indent: int = 2) -> str:
    """对象 → JSON 字符串。

    Args:
        obj: 任意可序列化对象
        ensure_ascii: 是否强制 ASCII（默认 False 以保留中文）
        indent: 缩进空格数

    Returns:
        JSON 字符串
    """
    return json.dumps(obj, ensure_ascii=ensure_ascii, indent=indent, default=str)


def save_to_file(obj: Any, filepath: Union[str, Path], **kwargs) -> None:
    """对象 → JSON 文件。

    Args:
        obj: 任意可序列化对象
        filepath: 输出文件路径
        **kwargs: 透传给 to_json
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = to_json(obj, **kwargs)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
