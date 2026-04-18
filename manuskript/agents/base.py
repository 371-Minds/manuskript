#!/usr/bin/env python
# --!-- coding: utf8 --!--
"""
Base helpers shared by all Manuskript ADK agents.
"""

import os
import subprocess
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Tuple

from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters


def _default_model() -> str:
    """Return the configured AI model or a safe default."""
    return os.environ.get("MANUSKRIPT_AI_MODEL", "gemini-2.0-flash")


def _reports_dir(project_path: str) -> str:
    """Return (and create) the _ai_reports directory next to the project folder."""
    project_dir = os.path.dirname(os.path.abspath(project_path))
    reports = os.path.join(project_dir, "_ai_reports")
    os.makedirs(reports, exist_ok=True)
    return reports


def _mcp_server_params(project_path: str) -> StdioServerParameters:
    """Build StdioServerParameters that launch the Manuskript MCP server."""
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "manuskript.mcp", "--project", os.path.abspath(project_path)],
        env=None,
    )


@asynccontextmanager
async def agent_with_mcp(
    project_path: str,
    name: str,
    instruction: str,
    model: "str | None" = None,
) -> AsyncIterator[Tuple[Agent, MCPToolset]]:
    """
    Async context manager that creates an ADK Agent with all Manuskript MCP
    tools loaded.  Yields (agent, toolset) and cleans up on exit.
    """
    params = _mcp_server_params(project_path)
    toolset = MCPToolset(connection_params=params)
    tools, _ = await toolset.__aenter__()

    agent = Agent(
        name=name,
        model=model or _default_model(),
        instruction=instruction,
        tools=tools,
    )

    try:
        yield agent, toolset
    finally:
        await toolset.__aexit__(None, None, None)
