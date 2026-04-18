#!/usr/bin/env python
# --!-- coding: utf8 --!--
"""
Pure-Python Manuskript project writer.

Writes changes back to .msk project files (folder-based layout) without
requiring a running QApplication or any PyQt5 imports.

Only folder-based (plain-text) projects are supported for writing.
Zip projects are read-only via the MCP layer.
"""

import os
import re
import string
import zipfile
from collections import OrderedDict
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

# Character fields in the MMD file, same order as version_1.py characterMap
_CHARACTER_MAP_FIELDS = [
    ("Name",             "Name"),
    ("ID",               "ID"),
    ("Importance",       "Importance"),
    ("POV",              "POV"),
    ("Motivation",       "Motivation"),
    ("Goal",             "Goal"),
    ("Conflict",         "Conflict"),
    ("Epiphany",         "Epiphany"),
    ("Phrase Summary",   "Phrase Summary"),
    ("Paragraph Summary","Paragraph Summary"),
    ("Full Summary",     "Full Summary"),
    ("Notes",            "Notes"),
]

_CHARACTER_STANDARD_KEYS = {v for _, v in _CHARACTER_MAP_FIELDS}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    """Convert a name to a safe filename slug."""
    valid = string.ascii_letters + string.digits
    result = ""
    for c in name:
        if c in valid:
            result += c
        elif c in string.whitespace:
            result += "_"
        else:
            result += "-"
    return result


def _format_metadata(name: str, value: str, tab_length: int = 20) -> str:
    """Format a single MMD metadata line."""
    value = value or ""
    if "\n" in value:
        lines = value.split("\n")
        value = "\n".join([" " * (tab_length + 1) + l for l in lines])[tab_length + 1:]
    if not name:
        name = "None"
    name = name.replace(":", "_.._")
    return "{name}:{spaces}{value}\n".format(
        name=name,
        spaces=" " * (tab_length - len(name)),
        value=value,
    )


def _project_folder(project_path: str) -> str:
    """Return the folder that holds a project's plain-text files."""
    project_dir = os.path.dirname(os.path.abspath(project_path))
    folder_name = os.path.splitext(os.path.basename(project_path))[0]
    return os.path.join(project_dir, folder_name)


def _is_zip(project_path: str) -> bool:
    try:
        with zipfile.ZipFile(project_path):
            return True
    except (zipfile.BadZipFile, IsADirectoryError, FileNotFoundError):
        return False


def _write_file(folder: str, rel_path: str, content: str) -> None:
    """Write *content* to *folder*/*rel_path*, creating directories as needed."""
    abs_path = os.path.join(folder, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wt", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


def _write_bytes(folder: str, rel_path: str, content: bytes) -> None:
    abs_path = os.path.join(folder, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as fh:
        fh.write(content)


# ---------------------------------------------------------------------------
# Scene writer
# ---------------------------------------------------------------------------

def write_scene(project_path: str, scene_id: str, content: str, append: bool = False) -> str:
    """
    Write (or append to) the text of an outline scene identified by *scene_id*.

    Returns the relative path of the modified file.

    Raises FileNotFoundError if the project folder cannot be located or the
    scene file cannot be found.
    """
    if _is_zip(project_path):
        raise ValueError("Zip projects are read-only via the MCP server. "
                         "Please convert your project to folder format first.")

    folder = _project_folder(project_path)
    scene_file = _find_scene_file(folder, scene_id)
    if scene_file is None:
        raise FileNotFoundError(f"No scene with ID={scene_id!r} found in {folder!r}.")

    abs_path = os.path.join(folder, scene_file)
    with open(abs_path, "rt", encoding="utf-8") as fh:
        original = fh.read()

    # Split into header and body
    header, body = _split_mmd(original)

    if append:
        new_body = (body.rstrip("\n") + "\n\n" + content) if body.strip() else content
    else:
        new_body = content

    new_content = header + "\n\n" + new_body
    with open(abs_path, "wt", encoding="utf-8", newline="\n") as fh:
        fh.write(new_content)

    return scene_file


def _find_scene_file(folder: str, scene_id: str) -> Optional[str]:
    """Walk the outline directory and return the relative path of the scene with the given ID."""
    outline_dir = os.path.join(folder, "outline")
    if not os.path.isdir(outline_dir):
        return None
    for dirpath, _dirs, filenames in os.walk(outline_dir):
        for fname in filenames:
            if not fname.endswith(".md") and fname != "folder.txt":
                continue
            abs_path = os.path.join(dirpath, fname)
            try:
                with open(abs_path, "rt", encoding="utf-8") as fh:
                    text = fh.read()
            except (PermissionError, UnicodeDecodeError):
                continue
            # Quick scan for ID line
            for line in text.split("\n"):
                m = re.match(r"^ID:\s*(.+)$", line)
                if m and m.group(1).strip() == str(scene_id):
                    return os.path.relpath(abs_path, folder)
                if line == "":  # End of MMD header
                    break
    return None


def _split_mmd(text: str):
    """Return (header_str, body_str) splitting on the blank line."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line == "":
            header = "\n".join(lines[:i])
            body_rest = lines[i + 1:]
            if body_rest and body_rest[0] == "":
                body_rest = body_rest[1:]
            return header, "\n".join(body_rest)
    return text, ""


# ---------------------------------------------------------------------------
# Character writer
# ---------------------------------------------------------------------------

def _next_char_id(folder: str) -> str:
    """Return the next unused integer ID for a character file."""
    chars_dir = os.path.join(folder, "characters")
    used = set()
    if os.path.isdir(chars_dir):
        for fname in os.listdir(chars_dir):
            m = re.match(r"^(\d+)-", fname)
            if m:
                used.add(int(m.group(1)))
    k = 0
    while k in used:
        k += 1
    return str(k)


def create_character(
    project_path: str,
    name: str,
    motivation: str = "",
    goal: str = "",
    conflict: str = "",
    epiphany: str = "",
    summary: str = "",
    importance: str = "0",
    color: str = "#aaaaaa",
) -> Dict[str, str]:
    """
    Create a new character and write its file to the characters/ directory.

    Returns a dict with ``id`` and ``path`` of the created character.
    """
    if _is_zip(project_path):
        raise ValueError("Zip projects are read-only via the MCP server.")

    folder = _project_folder(project_path)
    chars_dir = os.path.join(folder, "characters")
    os.makedirs(chars_dir, exist_ok=True)

    char_id = _next_char_id(folder)
    slug = _slugify(name)
    rel_path = os.path.join("characters", f"{char_id}-{slug}.txt")

    content = ""
    fields = [
        ("Name",             name),
        ("ID",               char_id),
        ("Importance",       importance),
        ("Motivation",       motivation),
        ("Goal",             goal),
        ("Conflict",         conflict),
        ("Epiphany",         epiphany),
        ("Phrase Summary",   summary),
        ("Color",            color),
    ]
    for field_name, val in fields:
        if val:
            content += _format_metadata(field_name, val, 20)

    _write_file(folder, rel_path, content)
    return {"id": char_id, "path": rel_path}


# ---------------------------------------------------------------------------
# Plot beat writer
# ---------------------------------------------------------------------------

def add_plot_beat(
    project_path: str,
    plot_id: str,
    title: str,
    summary: str = "",
    characters: Optional[List[str]] = None,
) -> bool:
    """
    Append a new beat (step) to the plot identified by *plot_id*.

    Returns True if the beat was added, False if the plot was not found.
    """
    if _is_zip(project_path):
        raise ValueError("Zip projects are read-only via the MCP server.")

    folder = _project_folder(project_path)
    plots_path = os.path.join(folder, "plots.xml")
    if not os.path.isfile(plots_path):
        raise FileNotFoundError(f"plots.xml not found in {folder!r}.")

    tree = ET.parse(plots_path)
    root = tree.getroot()

    for plot_el in root:
        if plot_el.get("ID") == str(plot_id):
            # Determine next step ID
            existing_ids = [int(s.get("ID", "0")) for s in plot_el if s.tag == "step"]
            next_id = 0
            while next_id in existing_ids:
                next_id += 1

            step_el = ET.SubElement(plot_el, "step")
            step_el.set("name", title)
            step_el.set("ID", str(next_id))
            step_el.set("summary", summary or "")
            if characters:
                step_el.set("meta", ",".join(str(c) for c in characters))

            _indent_xml(root)
            ET.ElementTree(root).write(plots_path, encoding="UTF-8", xml_declaration=True)
            return True

    return False


# ---------------------------------------------------------------------------
# World item writer
# ---------------------------------------------------------------------------

def update_world_item(
    project_path: str,
    name: str,
    description: str = "",
    passion: str = "",
    conflict: str = "",
) -> Dict[str, str]:
    """
    Create or update a world item.  If an item with *name* already exists
    (case-insensitive match), its attributes are updated.  Otherwise a new
    top-level item is appended.

    Returns a dict with ``id``, ``name``, and ``action`` ("created" or "updated").
    """
    if _is_zip(project_path):
        raise ValueError("Zip projects are read-only via the MCP server.")

    folder = _project_folder(project_path)
    world_path = os.path.join(folder, "world.opml")
    if not os.path.isfile(world_path):
        raise FileNotFoundError(f"world.opml not found in {folder!r}.")

    tree = ET.parse(world_path)
    root = tree.getroot()
    body = root.find("body")
    if body is None:
        body = ET.SubElement(root, "body")

    # Try to find existing item
    item_el, action = _find_or_create_world_item(body, name)

    if description:
        item_el.set("description", description)
    if passion:
        item_el.set("passion", passion)
    if conflict:
        item_el.set("conflict", conflict)

    if action == "created":
        # Assign new ID
        all_ids = [int(el.get("ID", "0")) for el in root.iter("outline") if el.get("ID")]
        new_id = 0
        while new_id in all_ids:
            new_id += 1
        item_el.set("ID", str(new_id))
        item_el.set("name", name)

    _indent_xml(root)
    ET.ElementTree(root).write(world_path, encoding="UTF-8", xml_declaration=True)
    return {"id": item_el.get("ID", ""), "name": name, "action": action}


def _find_or_create_world_item(body_el, name: str):
    """
    Search recursively for an outline element with the given name.
    Returns (element, "updated") if found, or (new_element, "created") if not.
    """
    for el in body_el.iter("outline"):
        if el.get("name", "").lower() == name.lower():
            return el, "updated"
    new_el = ET.SubElement(body_el, "outline")
    return new_el, "created"


# ---------------------------------------------------------------------------
# XML indentation helper (Python < 3.9 doesn't have ET.indent)
# ---------------------------------------------------------------------------

def _indent_xml(elem, level: int = 0) -> None:
    indent = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():  # type: ignore[reportPossiblyUnbound]
            child.tail = indent  # type: ignore[reportPossiblyUnbound]
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent
