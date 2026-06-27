"""MCP Server for Smart Sentence Splitter — v0.5.1 新增.

将分句引擎暴露为 MCP Tool，AI Agent 可通过 MCP 协议调用。

端点:
- tool: split_text — 分句
- resource: status://health — 健康状态
- resource: status://capabilities — 能力声明

启动:
    python -m splitter.api.mcp_server
    # 或注册到 Hermes/Kanban 的 MCP 配置
"""

from __future__ import annotations
import json
import os
import sys
from typing import Any, Dict, Optional, Sequence

# MCP SDK
import mcp.types as types
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

# 项目
from ..pipeline import SmartSentenceSplitter
from .. import __version__

# === MCP Server ===

server = Server("smart-sentence-splitter")


def _build_splitter(config: Optional[Dict[str, Any]] = None) -> SmartSentenceSplitter:
    """构造分句器（优先读环境变量）。"""
    cfg: Dict[str, Any] = {
        "mode": "balanced",
        "language": "auto",
    }
    if config:
        cfg.update(config)

    # 如果设了 API key 环境变量，自动启用 LLM
    if os.getenv("OPENAI_API_KEY") or os.getenv("XFYUN_API_KEY"):
        cfg.setdefault("enable_llm", True)
        llm_cfg = cfg.setdefault("llm", {})
        llm_cfg.setdefault("provider", "openai" if os.getenv("OPENAI_API_KEY") else "xfyun")

    # mode=precise 自动启用 topic seg 和 LLM
    mode = cfg.get("mode", "balanced")
    if mode == "precise":
        cfg.setdefault("enable_topic_segmentation", True)
    if mode == "fast":
        cfg["min_tier"] = 3
        cfg["enable_topic_segmentation"] = False

    return SmartSentenceSplitter(cfg)


# === Tool: split_text ===


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """工具列表。"""
    return [
        types.Tool(
            name="split_text",
            description="将文本按语义和字数约束分割为句子列表",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "待分句的文本",
                    },
                    "language": {
                        "type": "string",
                        "description": "语言 (auto/zh/en)",
                        "default": "auto",
                    },
                    "mode": {
                        "type": "string",
                        "description": "模式 (fast/balanced/precise)",
                        "default": "balanced",
                    },
                    "enable_era": {
                        "type": "boolean",
                        "description": "启用时代检测",
                        "default": False,
                    },
                    "enable_topic_segmentation": {
                        "type": "boolean",
                        "description": "启用 TextTiling 主题分割",
                        "default": False,
                    },
                    "enable_llm": {
                        "type": "boolean",
                        "description": "启用 LLM Tier",
                        "default": False,
                    },
                },
                "required": ["text"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """工具调用入口。"""
    if name != "split_text":
        raise ValueError(f"Unknown tool: {name}")

    if not arguments or "text" not in arguments:
        raise ValueError("Missing required argument: text")

    text = arguments["text"]
    config = {
        "language": arguments.get("language", "auto"),
        "mode": arguments.get("mode", "balanced"),
        "enable_era": arguments.get("enable_era", False),
        "enable_topic_segmentation": arguments.get("enable_topic_segmentation", False),
        "enable_llm": arguments.get("enable_llm", False),
    }

    splitter = _build_splitter(config)
    result = splitter.split(text)

    # 构造可读输出
    sentences_text = "\n".join(f"  [{s.index}] {s.text}" for s in result.sentences)

    summary = (
        f"语言: {result.language}, Tier: {result.tier_used}, "
        f"句子数: {len(result.sentences)}, 场景数: {result.total_scenes}"
    )

    output = f"""## 分句结果

{summary}

### 句子列表
{sentences_text}

### JSON 输出
```json
{json.dumps(result.to_dict(), ensure_ascii=False, indent=2)}
```"""

    return [types.TextContent(type="text", text=output)]


# === Resource: health & capabilities ===


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """资源列表。"""
    return [
        types.Resource(
            uri="status://health",
            name="Health Status",
            description="服务健康状态",
            mimeType="application/json",
        ),
        types.Resource(
            uri="status://capabilities",
            name="Capabilities",
            description="能力声明、支持的 tier/language/mode",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """读取资源。"""
    if uri == "status://health":
        return json.dumps(
            {
                "status": "ok",
                "version": __version__,
            },
            ensure_ascii=False,
        )

    if uri == "status://capabilities":
        return json.dumps(
            {
                "version": __version__,
                "languages": ["zh", "en", "mixed", "auto"],
                "tiers": ["tier1_llm", "tier2_semantic", "tier3_rule"],
                "modes": ["fast", "balanced", "precise"],
                "features": [
                    "sentence_segmentation",
                    "scene_segmentation",
                    "subtitle_segmentation",
                    "era_detection",
                    "topic_boundary_detection",
                    "user_dictionary",
                    "llm_tier",
                ],
            },
            ensure_ascii=False,
        )

    raise ValueError(f"Unknown resource: {uri}")


# === 启动 ===


async def main():
    """主入口（stdio 模式）。"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="smart-sentence-splitter",
                server_version=__version__,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
