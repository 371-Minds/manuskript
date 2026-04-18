#!/usr/bin/env python
# --!-- coding: utf8 --!--
"""
Character Development Agent.

Given a character name and high-level description, fleshes out
motivation/goal/conflict/epiphany, cross-references existing characters,
and creates the character via create_character_tool.
"""

import asyncio
import os
from typing import Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from manuskript.agents.base import _default_model, _reports_dir, agent_with_mcp

_INSTRUCTION = """\
You are a creative writing assistant helping to develop a rich character profile.

Your workflow:
1. Read project://characters to understand the existing cast.
2. Read project://plots and project://outline for context on how the new character fits in.
3. Based on the user's description, develop a full profile including:
   - Motivation (deep psychological driver)
   - Goal (concrete, external objective)
   - Conflict (internal and external obstacles)
   - Epiphany (what they learn or how they change)
   - Summary sentence (one line capturing their arc)
4. Ensure the new character does not duplicate an existing one.
   If a similar character already exists, note that and adapt.
5. Call create_character_tool to save the character.
6. Provide a brief narrative bio (2-3 paragraphs) as a creative writing exercise.

Be specific and avoid generic archetypes unless specifically requested.
"""


async def run_character_agent(
    project_path: str,
    name: str,
    description: str,
    importance: str = "0",
    model: Optional[str] = None,
) -> str:
    """
    Run the character development agent to create a new character.

    Parameters
    ----------
    project_path:
        Path to the .msk project file.
    name:
        The character's name.
    description:
        High-level description or notes about the character.
    importance:
        '0' = minor, '1' = secondary, '2' = major.
    model:
        Override the default model.

    Returns
    -------
    str
        The agent's final response text.
    """
    async with agent_with_mcp(project_path, "character_agent", _INSTRUCTION, model) as (agent, _toolset):
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="manuskript_character",
            session_service=session_service,
        )

        session = await session_service.create_session(
            app_name="manuskript_character",
            user_id="writer",
        )

        from google.genai.types import Content, Part
        user_message = Content(
            role="user",
            parts=[Part(text=(
                f"Create a character named '{name}' (importance={importance}).\n"
                f"Description: {description}"
            ))],
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
        report_path = os.path.join(reports, f"character_{name.replace(' ', '_')}.md")
        with open(report_path, "wt", encoding="utf-8") as fh:
            fh.write(f"# Character Development — {name}\n\n")
            fh.write(final_response)

        return final_response
