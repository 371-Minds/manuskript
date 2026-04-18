#!/usr/bin/env python
# --!-- coding: utf8 --!--
"""
Plot Consistency Agent.

Reads the full outline and all plot lines, identifies scenes not linked
to any plot, plot beats with no corresponding scenes, and produces a
structured consistency report.
"""

import asyncio
import os
from typing import Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from manuskript.agents.base import _default_model, _reports_dir, agent_with_mcp

_INSTRUCTION = """\
You are a story editor performing a structural analysis of a novel manuscript.

Your workflow:
1. Read project://outline to get the full scene/chapter structure.
2. Read project://plots to get all plot lines and their resolution steps.
3. Read project://characters for character information.
4. Analyse the manuscript for the following issues:
   a. Scenes with no plot association (orphaned scenes).
   b. Plot lines with beats that reference non-existent scenes.
   c. Major characters who disappear for long stretches without explanation.
   d. Plot threads that are introduced but never resolved.
   e. Timeline inconsistencies (e.g. chapter order issues).
5. Produce a structured Markdown report with sections:
   - **Summary** (overall health of the plot structure)
   - **Orphaned Scenes** (scenes not tied to any plot)
   - **Unresolved Plots** (plots missing resolution beats)
   - **Character Gaps** (characters absent for long stretches)
   - **Recommendations** (prioritised list of suggested fixes)

Be constructive and specific.  Reference scene IDs and titles when flagging issues.
Do NOT make any changes to the project — this is a read-only analysis.
"""


async def run_plot_agent(
    project_path: str,
    model: Optional[str] = None,
) -> str:
    """
    Run the plot consistency agent and return a Markdown report.

    Parameters
    ----------
    project_path:
        Path to the .msk project file.
    model:
        Override the default model.

    Returns
    -------
    str
        A Markdown-formatted consistency report.
    """
    async with agent_with_mcp(project_path, "plot_agent", _INSTRUCTION, model) as (agent, _toolset):
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="manuskript_plot",
            session_service=session_service,
        )

        session = await session_service.create_session(
            app_name="manuskript_plot",
            user_id="writer",
        )

        from google.genai.types import Content, Part
        user_message = Content(
            role="user",
            parts=[Part(text="Please analyse the plot consistency of this manuscript and produce a detailed report.")],
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
        report_path = os.path.join(reports, "plot_consistency_report.md")
        with open(report_path, "wt", encoding="utf-8") as fh:
            fh.write("# Plot Consistency Report\n\n")
            fh.write(final_response)

        return final_response
