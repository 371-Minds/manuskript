#!/usr/bin/env python
# --!-- coding: utf8 --!--
"""
Manuskript MCP Server.

Exposes a Manuskript project as MCP resources and tools so that any
MCP-compatible client (e.g. Claude, Google ADK) can read and write
project data autonomously.

Usage::

    python -m manuskript.mcp --project /path/to/project.msk
    # or with SSE transport:
    python -m manuskript.mcp --project /path/to/project.msk --transport sse --port 8765
"""

import json
import os
from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP

from manuskript.mcp.project_reader import read_project, search_project
from manuskript.mcp.project_writer import (
    add_plot_beat,
    create_character,
    update_world_item,
    write_scene,
)

# The project path is configured at startup (see __main__.py)
_project_path: Optional[str] = None


def _project() -> str:
    if not _project_path:
        raise RuntimeError(
            "No project loaded.  Start the server with --project <path>."
        )
    return _project_path


# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="manuskript",
    instructions=(
        "You are an AI writing assistant with full access to a Manuskript "
        "project.  Use the provided resources to read project data and the "
        "provided tools to make changes.  Always read before writing so you "
        "understand the existing content and style."
    ),
)


# ---------------------------------------------------------------------------
# Resources  (read-only)
# ---------------------------------------------------------------------------

@mcp.resource("project://outline")
def resource_outline() -> str:
    """Full chapter/scene tree of the project."""
    data = read_project(_project())
    return json.dumps(data["outline"], ensure_ascii=False, indent=2)


@mcp.resource("project://characters")
def resource_characters() -> str:
    """All character profiles (name, motivation, goal, conflict, epiphany, etc.)."""
    data = read_project(_project())
    return json.dumps(data["characters"], ensure_ascii=False, indent=2)


@mcp.resource("project://plots")
def resource_plots() -> str:
    """All plot lines and their resolution steps."""
    data = read_project(_project())
    return json.dumps(data["plots"], ensure_ascii=False, indent=2)


@mcp.resource("project://world")
def resource_world() -> str:
    """World-building entries (places, factions, items, etc.)."""
    data = read_project(_project())
    return json.dumps(data["world"], ensure_ascii=False, indent=2)


@mcp.resource("project://settings")
def resource_settings() -> str:
    """Project metadata: title, author, summary, premise."""
    data = read_project(_project())
    return json.dumps(
        {
            "infos": data["infos"],
            "summary": data["summary"],
            "labels": data["labels"],
            "statuses": data["statuses"],
        },
        ensure_ascii=False,
        indent=2,
    )


# ---------------------------------------------------------------------------
# Tools  (read-write)
# ---------------------------------------------------------------------------

@mcp.tool()
def write_scene_tool(
    scene_id: Annotated[str, "The numeric ID of the scene to write (e.g. '3')"],
    content: Annotated[str, "The new text content for the scene"],
    append: Annotated[bool, "If True, append to existing text rather than replacing it"] = False,
) -> str:
    """
    Write or append text to an existing scene in the manuscript outline.

    Use append=True to add content after the existing text; use append=False
    (default) to fully replace it.  Read the scene's current content via the
    project://outline resource before calling this tool.
    """
    path = write_scene(_project(), scene_id, content, append=append)
    return f"Scene {scene_id} updated successfully (file: {path})."


@mcp.tool()
def create_character_tool(
    name: Annotated[str, "Character's full name"],
    motivation: Annotated[str, "What drives this character?"] = "",
    goal: Annotated[str, "What does this character want to achieve?"] = "",
    conflict: Annotated[str, "What stands in the character's way?"] = "",
    epiphany: Annotated[str, "What does this character learn by the end?"] = "",
    summary: Annotated[str, "One-sentence summary of the character's arc"] = "",
    importance: Annotated[str, "Importance level: '0'=minor, '1'=secondary, '2'=major"] = "0",
) -> str:
    """
    Create a new character in the project.

    Before creating, read project://characters to verify the character does
    not already exist and to ensure the new character fits the existing cast.
    """
    result = create_character(
        _project(),
        name=name,
        motivation=motivation,
        goal=goal,
        conflict=conflict,
        epiphany=epiphany,
        summary=summary,
        importance=importance,
    )
    return (
        f"Character '{name}' created with ID={result['id']} "
        f"(file: {result['path']})."
    )


@mcp.tool()
def add_plot_beat_tool(
    plot_id: Annotated[str, "The numeric ID of the plot to add a beat to"],
    title: Annotated[str, "Short title for this beat"],
    summary: Annotated[str, "Summary of what happens in this beat"] = "",
    characters: Annotated[
        str,
        "Comma-separated character IDs involved in this beat (e.g. '0,2')",
    ] = "",
) -> str:
    """
    Append a new plot beat (resolution step) to an existing plot line.

    Read project://plots first to find the correct plot_id and understand
    the existing beat structure.
    """
    char_list = [c.strip() for c in characters.split(",") if c.strip()] if characters else []
    added = add_plot_beat(_project(), plot_id, title, summary=summary, characters=char_list)
    if added:
        return f"Beat '{title}' added to plot {plot_id}."
    return f"Plot with ID={plot_id} not found.  Use project://plots to list available plots."


@mcp.tool()
def update_world_item_tool(
    name: Annotated[str, "Name of the world item (place, faction, item, etc.)"],
    description: Annotated[str, "Description of this world element"] = "",
    passion: Annotated[str, "What is special or desirable about this element?"] = "",
    conflict: Annotated[str, "What tension or conflict surrounds this element?"] = "",
) -> str:
    """
    Create or update a world-building entry in the project's world model.

    If an entry with the same name already exists, its attributes are updated.
    Read project://world first to understand the existing world structure.
    """
    result = update_world_item(
        _project(),
        name=name,
        description=description,
        passion=passion,
        conflict=conflict,
    )
    action = result["action"]
    return f"World item '{name}' {action} (ID={result['id']})."


@mcp.tool()
def search_project_tool(
    query: Annotated[str, "The text to search for across all project content"],
    case_sensitive: Annotated[bool, "Whether the search is case-sensitive"] = False,
) -> str:
    """
    Search the project for a word or phrase across characters, scenes, plots, and world items.

    Returns a JSON array of matches, each with type, id, title, field, and an excerpt.
    """
    results = search_project(_project(), query, case_sensitive=case_sensitive)
    return json.dumps(results, ensure_ascii=False, indent=2)


@mcp.tool()
def get_scene_text_tool(
    scene_id: Annotated[str, "The numeric ID of the scene to retrieve"],
) -> str:
    """
    Retrieve the full text of a specific scene by ID.

    Use this before writing to understand the existing content and maintain
    narrative continuity.
    """
    data = read_project(_project())

    def find_scene(items):
        for item in items:
            if item.get("ID") == str(scene_id):
                return item
            found = find_scene(item.get("children", []))
            if found:
                return found
        return None

    scene = find_scene(data["outline"])
    if scene is None:
        return f"Scene with ID={scene_id!r} not found."

    result = {
        "id": scene.get("ID", ""),
        "title": scene.get("title", ""),
        "type": scene.get("_type", ""),
        "pov": scene.get("POV", ""),
        "status": scene.get("status", ""),
        "text": scene.get("text", ""),
        "summarySentence": scene.get("summarySentence", ""),
        "notes": scene.get("notes", ""),
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Server initialisation helper
# ---------------------------------------------------------------------------

def configure(project_path: str) -> None:
    """Set the project path used by all resources and tools."""
    global _project_path
    if not os.path.exists(project_path):
        raise FileNotFoundError(f"Project not found: {project_path!r}")
    _project_path = os.path.abspath(project_path)
