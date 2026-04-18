#!/usr/bin/env python
# --!-- coding: utf8 --!--
"""
World Builder Agent.

Given a scene (by ID), identifies named entities — places, factions,
artefacts — that are mentioned in the scene text but not yet recorded
in the world model, and proposes/creates new world entries.
"""

import asyncio
import os
from typing import Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from manuskript.agents.base import _default_model, _reports_dir, agent_with_mcp

_INSTRUCTION = """\
You are a world-building assistant helping to maintain a consistent story world.

Your workflow:
1. Call get_scene_text_tool with the provided scene_id to retrieve the scene text.
2. Read project://world to see what is already recorded.
3. Extract all named entities from the scene:
   - Locations (cities, buildings, landscapes, realms)
   - Factions, organisations, institutions
   - Objects of significance (artefacts, weapons, books, etc.)
   - Any concept that would benefit from a world entry
4. For each entity NOT already present in project://world:
   a. Write a concise description (1-3 sentences).
   b. Note any passion or conflict associated with it.
   c. Call update_world_item_tool to create the entry.
5. Provide a summary of what was added and what already existed.

Keep descriptions factual and grounded in what the scene text tells us.
Avoid over-extrapolating beyond what is written.
"""


async def run_world_agent(
    project_path: str,
    scene_id: str,
    model: Optional[str] = None,
) -> str:
    """
    Run the world builder agent for a given scene.

    Parameters
    ----------
    project_path:
        Path to the .msk project file.
    scene_id:
        Numeric ID of the scene to analyse.
    model:
        Override the default model.

    Returns
    -------
    str
        The agent's final response text.
    """
    async with agent_with_mcp(project_path, "world_agent", _INSTRUCTION, model) as (agent, _toolset):
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="manuskript_world",
            session_service=session_service,
        )

        session = await session_service.create_session(
            app_name="manuskript_world",
            user_id="writer",
        )

        from google.genai.types import Content, Part
        user_message = Content(
            role="user",
            parts=[Part(text=f"Extract and create world entries from scene ID={scene_id}.")],
        )

        final_response = ""
        async for event in runner.run_async(
            user_id="writer",
            session_id=session.id,
            new_message=user_message,
        ):
            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        final_response += part.text

        # Persist report
        reports = _reports_dir(project_path)
        report_path = os.path.join(reports, f"world_builder_scene_{scene_id}.md")
        with open(report_path, "wt", encoding="utf-8") as fh:
            fh.write(f"# World Builder Report — Scene {scene_id}\n\n")
            fh.write(final_response)

        return final_response
