#!/usr/bin/env python
# --!-- coding: utf8 --!--
"""
Writing Continuation Agent.

Given a scene ID, reads the existing content and POV character profile,
then generates a stylistically consistent continuation and writes it back
to the scene using the write_scene_tool (append mode).
"""

import asyncio
import os
from typing import Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from manuskript.agents.base import _default_model, _reports_dir, agent_with_mcp

_INSTRUCTION = """\
You are a creative writing assistant helping to continue a novel scene.

Your workflow:
1. Call get_scene_text_tool with the provided scene_id to read the current text.
2. Read project://characters to find the POV character's profile (motivation, voice, etc.).
3. Read project://outline to understand context (where this scene sits in the story).
4. Generate a continuation that:
   - Matches the existing tone, tense, and POV character voice.
   - Advances the scene meaningfully (conflict, discovery, or character development).
   - Is between 200 and 600 words unless instructed otherwise.
5. Call write_scene_tool with append=True to add the continuation to the scene.
6. Report a brief summary of what you wrote.

Do NOT invent new characters or plot directions that contradict what you have read.
"""


async def run_continuation_agent(
    project_path: str,
    scene_id: str,
    extra_instructions: str = "",
    model: Optional[str] = None,
    dry_run: bool = False,
) -> str:
    """
    Run the writing continuation agent for *scene_id*.

    Parameters
    ----------
    project_path:
        Path to the .msk project file.
    scene_id:
        Numeric ID of the scene to continue.
    extra_instructions:
        Optional additional guidance appended to the base instruction.
    model:
        Override the default model.
    dry_run:
        If True, the agent will read but not write (passes a note to skip writing).

    Returns
    -------
    str
        The agent's final response text.
    """
    instruction = _INSTRUCTION
    if extra_instructions:
        instruction += f"\n\nAdditional guidance: {extra_instructions}"
    if dry_run:
        instruction += "\n\nIMPORTANT: This is a dry run. Read the scene and describe what you would write, but do NOT call write_scene_tool."

    async with agent_with_mcp(project_path, "continuation_agent", instruction, model) as (agent, _toolset):
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="manuskript_continuation",
            session_service=session_service,
        )

        session = await session_service.create_session(
            app_name="manuskript_continuation",
            user_id="writer",
        )

        from google.genai.types import Content, Part
        user_message = Content(
            role="user",
            parts=[Part(text=f"Please continue scene ID={scene_id}.")],
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

        # Persist to report file
        reports = _reports_dir(project_path)
        report_path = os.path.join(reports, f"continuation_scene_{scene_id}.md")
        with open(report_path, "wt", encoding="utf-8") as fh:
            fh.write(f"# Scene Continuation — ID {scene_id}\n\n")
            fh.write(final_response)

        return final_response
