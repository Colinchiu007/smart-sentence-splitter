"""Test config loader."""

import pytest
import tempfile
import os
from pathlib import Path

from splitter.utils.config_loader import load_config, merge_config


class TestLoadConfig:
    def test_none_returns_default(self):
        config = load_config(None)
        assert config["language"] == "auto"
        assert config["enable_llm"] is False
        assert config["scene"]["target_seconds"] == 6.0

    def test_dict_input_merges(self):
        config = load_config({"enable_llm": True, "scene": {"target_seconds": 10.0}})
        assert config["enable_llm"] is True
        assert config["scene"]["target_seconds"] == 10.0
        # 默认值仍在
        assert config["scene"]["speech_rate"] == 1.0

    def test_yaml_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write("""
language: en
enable_era: true
scene:
  target_seconds: 10.0
""")
            tmp_path = f.name
        try:
            config = load_config(tmp_path)
            assert config["language"] == "en"
            assert config["enable_era"] is True
            assert config["scene"]["target_seconds"] == 10.0
            # 默认值仍在
            assert config["scene"]["speech_rate"] == 1.0
        finally:
            os.unlink(tmp_path)

    def test_json_file(self):
        import json
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"language": "en", "min_tier": 3}, f)
            tmp_path = f.name
        try:
            config = load_config(tmp_path)
            assert config["language"] == "en"
            assert config["min_tier"] == 3
        finally:
            os.unlink(tmp_path)

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")

    def test_unsupported_format_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("not yaml")
            tmp_path = f.name
        try:
            with pytest.raises(ValueError):
                load_config(tmp_path)
        finally:
            os.unlink(tmp_path)


class TestMergeConfig:
    def test_deep_merge(self):
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"c": 20}}
        result = merge_config(base, override)
        assert result["a"] == 1
        assert result["b"]["c"] == 20
        assert result["b"]["d"] == 3

    def test_override_replaces_list(self):
        base = {"items": [1, 2, 3]}
        override = {"items": [4, 5]}
        result = merge_config(base, override)
        assert result["items"] == [4, 5]

    def test_does_not_mutate_base(self):
        base = {"a": 1, "b": {"c": 2}}
        override = {"b": {"c": 20}}
        merge_config(base, override)
        assert base["b"]["c"] == 2  # 原始未变
