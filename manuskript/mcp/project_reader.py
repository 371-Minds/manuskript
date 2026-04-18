#!/usr/bin/env python
# --!-- coding: utf8 --!--
"""
Pure-Python Manuskript project reader.

Reads .msk project files (both folder-based and zip-based) without
requiring a running QApplication or any PyQt5 imports.
"""

import os
import re
import zipfile
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET


# ---------------------------------------------------------------------------
# MMD helpers (mirrors version_1.py parseMMDFile without the Qt dependency)
# ---------------------------------------------------------------------------

def _parse_mmd(text: str, as_dict: bool = False):
    """
    Parse a MultiMarkDown-style metadata file.

    Returns (metadata, body) where metadata is either a list of
    (description, value) tuples or an OrderedDict when *as_dict* is True.
    """
    md: List[Tuple[str, str]] = []
    mdd: OrderedDict = OrderedDict()
    body: List[str] = []
    descr = ""
    val = ""
    in_body = False

    for line in text.split("\n"):
        if not in_body:
            m = re.match(r"^([^\s].*?):\s*(.*)$", line)
            if m:
                if descr:
                    key = "" if descr == "None" else descr
                    md.append((key, val))
                    mdd[key] = val
                descr = m.group(1)
                val = m.group(2)
            elif line[:4] == "    ":
                val += "\n" + line.strip()
            elif line == "":
                in_body = True
                if descr:
                    key = "" if descr == "None" else descr
                    md.append((key, val))
                    mdd[key] = val
        else:
            body.append(line)

    # Remove leading blank line after the blank separator
    if body and body[0] == "":
        body = body[1:]

    body_str = "\n".join(body)
    return (mdd, body_str) if as_dict else (md, body_str)


# ---------------------------------------------------------------------------
# Project loader
# ---------------------------------------------------------------------------

def _load_files(project_path: str) -> Dict[str, Any]:
    """
    Load all files from a project into a flat dict keyed by relative path.

    Supports both folder-based (plain text) and zip-based projects.
    Binary files (*.xml, *.opml) are stored as bytes; everything else as str.
    """
    files: Dict[str, Any] = {}

    is_zip = False
    try:
        zf = zipfile.ZipFile(project_path)
        is_zip = True
    except (zipfile.BadZipFile, IsADirectoryError):
        is_zip = False

    if is_zip:
        for name in zf.namelist():
            data = zf.read(name)
            if name.endswith((".xml", ".opml")):
                files[name] = data
            else:
                try:
                    files[name] = data.decode("utf-8")
                except UnicodeDecodeError:
                    files[name] = data
        zf.close()
    else:
        project_dir = os.path.dirname(os.path.abspath(project_path))
        folder_name = os.path.splitext(os.path.basename(project_path))[0]
        base = os.path.join(project_dir, folder_name)

        for dirpath, _dirs, filenames in os.walk(base):
            rel_dir = os.path.relpath(dirpath, base)
            if rel_dir == ".":
                rel_dir = ""
            for fname in filenames:
                if fname.startswith("."):
                    continue
                rel_path = os.path.join(rel_dir, fname) if rel_dir else fname
                abs_path = os.path.join(dirpath, fname)
                if fname.endswith((".xml", ".opml")):
                    with open(abs_path, "rb") as fh:
                        files[rel_path] = fh.read()
                else:
                    try:
                        with open(abs_path, "rt", encoding="utf-8") as fh:
                            files[rel_path] = fh.read()
                    except (UnicodeDecodeError, PermissionError):
                        pass

    return OrderedDict(sorted(files.items()))


# ---------------------------------------------------------------------------
# Public read functions
# ---------------------------------------------------------------------------

def read_project(project_path: str) -> Dict[str, Any]:
    """
    Parse a Manuskript project and return a dict with keys:
      - ``settings``: the raw settings JSON string
      - ``infos``: OrderedDict of book metadata
      - ``summary``: OrderedDict of summary texts
      - ``characters``: list of character dicts
      - ``outline``: nested list representing the chapter/scene tree
      - ``plots``: list of plot dicts
      - ``world``: list of world-item dicts (nested)
      - ``labels``: list of label names
      - ``statuses``: list of status names
    """
    files = _load_files(project_path)

    return {
        "settings": _read_settings(files),
        "infos": _read_infos(files),
        "summary": _read_summary(files),
        "characters": _read_characters(files),
        "outline": _read_outline(files),
        "plots": _read_plots(files),
        "world": _read_world(files),
        "labels": _read_labels(files),
        "statuses": _read_statuses(files),
    }


def _read_settings(files: Dict) -> str:
    return files.get("settings.txt", "")


def _read_infos(files: Dict) -> Dict[str, str]:
    if "infos.txt" not in files:
        return {}
    md, _ = _parse_mmd(files["infos.txt"], as_dict=True)
    return dict(md)


def _read_summary(files: Dict) -> Dict[str, str]:
    if "summary.txt" not in files:
        return {}
    md, _ = _parse_mmd(files["summary.txt"], as_dict=True)
    return dict(md)


def _read_characters(files: Dict) -> List[Dict[str, Any]]:
    characters = []
    char_files = sorted(k for k in files if k.startswith("characters" + os.sep) or k.startswith("characters/"))
    for path in char_files:
        if not path.endswith(".txt"):
            continue
        md, _body = _parse_mmd(files[path])
        c: Dict[str, Any] = {"_path": path, "infos": []}
        color_seen = False
        for desc, val in md:
            if desc in ("Name", "ID", "Importance", "POV", "Motivation", "Goal",
                        "Conflict", "Epiphany", "Phrase Summary", "Paragraph Summary",
                        "Full Summary", "Notes"):
                c[desc] = val
            elif desc == "Color" and not color_seen:
                c["Color"] = val
                color_seen = True
            else:
                c["infos"].append({"description": desc, "value": val})
        characters.append(c)
    return characters


def _read_outline_recursive(files: Dict, base_key: str, subtree: Dict) -> List[Dict]:
    """Recursively build an outline list from the nested dict produced by _build_outline_tree."""
    items = []
    for key, value in subtree.items():
        if key.endswith(":lastPath"):
            continue
        if isinstance(value, dict):
            # Folder
            folder_text = value.get("folder.txt", "")
            md, _body = _parse_mmd(folder_text, as_dict=True) if folder_text else ({}, "")
            item = dict(md)
            item["_type"] = "folder"
            item["_path"] = value.get("folder.txt:lastPath", "")
            item["children"] = _read_outline_recursive(files, base_key, value)
            items.append(item)
        elif isinstance(value, str):
            md, body = _parse_mmd(value, as_dict=True)
            item = dict(md)
            item["_type"] = item.get("type", "md")
            item["text"] = body
            item["_path"] = subtree.get(key + ":lastPath", "")
            items.append(item)
    return items


def _read_outline(files: Dict) -> List[Dict]:
    outline_files = sorted(
        k for k in files
        if k.startswith("outline" + os.sep) or k.startswith("outline/")
    )

    # Build nested dict structure
    tree: OrderedDict = OrderedDict()
    for path in outline_files:
        parts = path.replace("\\", "/").split("/")[1:]  # strip "outline/"
        parent = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                parent[part] = files[path]
                parent[part + ":lastPath"] = path
            else:
                if part not in parent:
                    parent[part] = OrderedDict()
                if not isinstance(parent[part], dict):
                    parent[part] = OrderedDict()
                parent = parent[part]

    return _read_outline_recursive(files, "outline", tree)


def _read_plots(files: Dict) -> List[Dict]:
    if "plots.xml" not in files:
        return []
    root = ET.fromstring(files["plots.xml"])
    plots = []
    for plot_el in root:
        p: Dict[str, Any] = dict(plot_el.attrib)
        p["steps"] = []
        for step_el in plot_el:
            p["steps"].append(dict(step_el.attrib))
        plots.append(p)
    return plots


def _read_world_recursive(items_el) -> List[Dict]:
    result = []
    for outline in items_el:
        w: Dict[str, Any] = dict(outline.attrib)
        w["children"] = _read_world_recursive(outline)
        result.append(w)
    return result


def _read_world(files: Dict) -> List[Dict]:
    if "world.opml" not in files:
        return []
    root = ET.fromstring(files["world.opml"])
    body = root.find("body")
    if body is None:
        return []
    return _read_world_recursive(body)


def _read_labels(files: Dict) -> List[str]:
    if "labels.txt" not in files:
        return []
    return [line.split(":")[0].strip() for line in files["labels.txt"].splitlines() if line.strip()]


def _read_statuses(files: Dict) -> List[str]:
    if "status.txt" not in files:
        return []
    return [line.strip() for line in files["status.txt"].splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Search helper
# ---------------------------------------------------------------------------

def search_project(project_path: str, query: str, case_sensitive: bool = False) -> List[Dict]:
    """
    Full-text search across characters, outline scenes, plots, and world items.

    Returns a list of match dicts with keys: ``type``, ``id``, ``title``,
    ``field``, ``excerpt``.
    """
    data = read_project(project_path)
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(query), flags)
    results = []

    def excerpt(text: str, max_len: int = 120) -> str:
        m = pattern.search(text)
        if not m:
            return text[:max_len]
        start = max(0, m.start() - 40)
        end = min(len(text), m.end() + 80)
        snip = text[start:end]
        return ("…" if start else "") + snip + ("…" if end < len(text) else "")

    def matches(text: str) -> bool:
        return bool(pattern.search(text or ""))

    # Characters
    for c in data["characters"]:
        for field, val in c.items():
            if field in ("_path", "infos", "Color"):
                continue
            if matches(str(val)):
                results.append({
                    "type": "character",
                    "id": c.get("ID", ""),
                    "title": c.get("Name", ""),
                    "field": field,
                    "excerpt": excerpt(str(val)),
                })
                break
        for info in c.get("infos", []):
            for field in ("description", "value"):
                if matches(info.get(field, "")):
                    results.append({
                        "type": "character_info",
                        "id": c.get("ID", ""),
                        "title": c.get("Name", ""),
                        "field": field,
                        "excerpt": excerpt(info[field]),
                    })

    # Outline
    def search_outline(items, depth=0):
        for item in items:
            for field in ("title", "text", "summarySentence", "summaryFull", "notes"):
                val = item.get(field, "")
                if matches(str(val)):
                    results.append({
                        "type": "scene" if item.get("_type") != "folder" else "folder",
                        "id": item.get("ID", ""),
                        "title": item.get("title", ""),
                        "field": field,
                        "excerpt": excerpt(str(val)),
                    })
                    break
            search_outline(item.get("children", []), depth + 1)

    search_outline(data["outline"])

    # Plots
    for p in data["plots"]:
        for field in ("name", "description", "result"):
            if matches(p.get(field, "")):
                results.append({
                    "type": "plot",
                    "id": p.get("ID", ""),
                    "title": p.get("name", ""),
                    "field": field,
                    "excerpt": excerpt(p.get(field, "")),
                })
                break

    # World
    def search_world(items):
        for w in items:
            for field in ("name", "description", "passion", "conflict"):
                if matches(w.get(field, "")):
                    results.append({
                        "type": "world",
                        "id": w.get("ID", ""),
                        "title": w.get("name", ""),
                        "field": field,
                        "excerpt": excerpt(w.get(field, "")),
                    })
                    break
            search_world(w.get("children", []))

    search_world(data["world"])

    return results
