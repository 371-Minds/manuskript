#!/usr/bin/env python
# --!-- coding: utf8 --!--
"""
Style & Consistency Agent.

Reads a configurable sample of scenes and produces a report on POV
inconsistencies, timeline issues, and repeated phrases.  This agent is
read-only — it never calls write tools.
"""

import asyncio
import os
from typing import Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from manuskript.agents.base import _default_model, _reports_dir, agent_with_mcp

_INSTRUCTION = """\
You are a developmental editor performing a style and consistency review.

Your workflow:
1. Read project://outline to see the full scene list.
2. Read project://characters to understand the cast.
3. For each scene in the sample, call get_scene_text_tool to retrieve its text.
4. Analyse the scenes for:
   a. **POV shifts** — unintentional changes in point-of-view character mid-scene.
   b. **Tense shifts** — inconsistent verb tenses (past vs present).
   c. **Repeated phrases** — words or expressions used too frequently.
   d. **Timeline gaps** — scenes that imply time has passed but don't signal it clearly.
   e. **Dialogue tags** — over-reliance on said-bookisms (e.g. "he exclaimed breathlessly").
   f. **Passive voice clusters** — paragraphs heavy with passive constructions.
5. Produce a Markdown report with:
   - **Executive Summary** (overall style health)
   - **POV Issues** (scene ID, title, description of issue)
   - **Tense Issues**
   - **Repeated Phrases** (word/phrase + count + affected scenes)
   - **Timeline Notes**
   - **Dialogue Observations**
   - **Recommendations** (top 5 actionable improvements)

This is a read-only review.  Do NOT call any write tools.
"""


async def run_style_agent(
    project_path: str,
    max_scenes: int = 10,
    model: Optional[str] = None,
) -> str:
    """
    Run the style and consistency agent on a sample of scenes.

    Parameters
    ----------
    project_path:
        Path to the .msk project file.
    max_scenes:
        Maximum number of scenes to analyse (default 10).
    model:
        Override the default model.

    Returns
    -------
    str
        A Markdown-formatted style report.
    """
    instruction = _INSTRUCTION + f"\n\nAnalyse at most {max_scenes} scenes (pick the first ones with non-empty text)."

    async with agent_with_mcp(project_path, "style_agent", instruction, model) as (agent, _toolset):
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="manuskript_style",
            session_service=session_service,
        )

        session = await session_service.create_session(
            app_name="manuskript_style",
            user_id="writer",
        )

        from google.genai.types import Content, Part
        user_message = Content(
            role="user",
            parts=[Part(text="Please perform a style and consistency review of this manuscript.")],
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
        report_path = os.path.join(reports, "style_consistency_report.md")
        with open(report_path, "wt", encoding="utf-8") as fh:
            fh.write("# Style & Consistency Report\n\n")
            fh.write(final_response)

        return final_response
