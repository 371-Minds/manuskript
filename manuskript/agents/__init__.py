#!/usr/bin/env python
# --!-- coding: utf8 --!--
"""
Manuskript AI Agents package.

Each agent uses Google ADK with an MCP toolset pointing at the local
Manuskript MCP server.  Agents are async and write their output to
stdout or to a project-local ``_ai_reports/`` directory.
"""
