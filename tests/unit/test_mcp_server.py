"""MCP Server 单元测试 — v0.5.1 新增."""

import json
from pathlib import Path
from unittest.mock import patch

from splitter.api.mcp_server import server, _build_splitter


class TestMCPServerCapabilities:
    """MCP Server 配置信息测试。"""

    def test_server_name(self):
        assert server.name == "smart-sentence-splitter"

    def test_build_splitter_default(self):
        s = _build_splitter({})
        assert s is not None

    def test_build_splitter_with_llm_key(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
            s = _build_splitter({"enable_llm": True, "mode": "precise"})
            # LLM enabled
            r = s.split("测试。")
            assert r is not None


class TestMCPServerImportable:
    """MCP Server 文件可编译。"""

    def test_file_exists(self):
        src = Path(__file__).parent.parent.parent / "src" / "splitter" / "api" / "mcp_server.py"
        assert src.exists()
        assert src.stat().st_size > 2000

    def test_file_compiles(self):
        src = Path(__file__).parent.parent.parent / "src" / "splitter" / "api" / "mcp_server.py"
        content = src.read_text(encoding="utf-8")
        compile(content, str(src), "exec")