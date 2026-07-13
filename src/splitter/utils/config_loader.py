"""Configuration loader for splitter.

Supports loading from YAML files and dicts, with deep merge capabilities.
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Union
from pathlib import Path
import copy

import yaml


# 默认配置（与 config/splitter.yaml 同步）
DEFAULT_CONFIG: Dict[str, Any] = {
    "language": "auto",
    "mode": "balanced",
    "max_input_length": 200000,  # 大文本截断阈值（>200K 时分块递归处理）
    "enable_era": False,
    "enable_llm": False,
    "enable_script_analysis": False,  # v0.7
    "enable_paragraph_aware": False,  # 段落感知场景分组（视频管线推荐 True）
    "enable_topic_segmentation": False,
    "min_tier": 2,
    "sentence_tokenizer": {
        "language": "auto",
        "handle_abbreviations": True,
        "max_sentence_length": 200,
        "custom_abbreviations": ["等", "即", "如", "称"],
        "language_specific": {
            "zh": {
                "tokenizer": "jieba",
                "use_pos": True,
                "entity_protection": True,
            },
            "en": {
                "tokenizer": "whitespace",
                "use_pos": False,
                "abbreviation_table": "default_en",
                "quote_pairs": [['"', '"'], ["'", "'"]],
                "handle_ellipsis": True,
                "handle_em_dash": True,
            },
            "ja": {
                "enabled": False,
            },
        },
    },
    "scene": {
        "target_seconds": 6.0,
        "base_words_per_second": 3.3,
        "speech_rate": 1.0,
        "min_words_per_segment": 10,
        "max_words_per_segment": 50,
        "enforce_sentence_boundary": True,
        "allow_single_sentence_overflow": True,
    },
    "subtitle": {
        "min_chars_per_block": 8,
        "max_chars_per_block": 15,
        "punctuation_priority": [
            "。",
            "！",
            "？",
            "；",
            "，",
            ".",
            "!",
            "?",
            ",",
            "、",
            " ",
            "\n",
        ],
        "time_calculation_method": "proportional",
    },
    "length": {  # v0.6 新增
        "strategy": "B",
        "min_chars": 3,
        "max_chars": 15,
        "prefer_punctuation": True,
        "warning_on_violation": True,
    },
    "llm": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
        "base_url": None,
        "timeout": 30,
        "max_retries": 2,
    },
    "texttiling": {
        "min_text_length": 100,
        "window_size": 20,
        "depth_score_threshold": 0.3,
        "min_tokens_for_boundary": 20,
    },
}


def load_config(source: Union[str, Path, Dict[str, Any], None] = None) -> Dict[str, Any]:
    """加载配置。

    Args:
        source: 配置文件路径（YAML）或字典，None 时返回默认配置

    Returns:
        合并后的配置字典
    """
    if source is None:
        return copy.deepcopy(DEFAULT_CONFIG)

    if isinstance(source, dict):
        return merge_config(DEFAULT_CONFIG, source)

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    if path.suffix.lower() in (".yaml", ".yml"):
        with open(path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
    elif path.suffix.lower() == ".json":
        import json

        with open(path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
    else:
        raise ValueError(f"Unsupported config file format: {path.suffix}")

    return merge_config(DEFAULT_CONFIG, user_config)


def merge_config(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """深度合并两个配置字典。override 优先。

    Args:
        base: 基础配置
        override: 用户配置（覆盖基础）

    Returns:
        合并后的新字典
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result
