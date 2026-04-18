#!/usr/bin/env python
# --!-- coding: utf8 --!--
"""
Unit tests for the Manuskript MCP tools layer.

These tests use the sample project bundled with Manuskript so they
work without a running QApplication or external services.
"""

import os
import shutil
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_PROJECT_MSK = os.path.join(
    os.path.dirname(__file__),  # manuskript/tests/mcp/
    "..", "..", "..",           # repo root
    "sample-projects", "book-of-acts.msk",
)
SAMPLE_PROJECT_MSK = os.path.normpath(SAMPLE_PROJECT_MSK)


@pytest.fixture(scope="module")
def project_copy():
    """
    Return a path to a temporary copy of the sample project so that
    write tests do not pollute the original.
    """
    tmp = tempfile.mkdtemp(prefix="manuskript_mcp_test_")
    src_msk = SAMPLE_PROJECT_MSK
    src_folder = src_msk[:-4]  # strip .msk

    if not os.path.isfile(src_msk):
        pytest.skip(f"Sample project not found: {src_msk}")

    dst_msk = os.path.join(tmp, "book-of-acts.msk")
    shutil.copyfile(src_msk, dst_msk)
    if os.path.isdir(src_folder):
        shutil.copytree(src_folder, os.path.join(tmp, "book-of-acts"))

    yield dst_msk

    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# project_reader tests
# ---------------------------------------------------------------------------

class TestProjectReader:
    def test_read_infos(self, project_copy):
        from manuskript.mcp.project_reader import read_project
        data = read_project(project_copy)
        assert "infos" in data
        infos = data["infos"]
        assert isinstance(infos, dict)
        # The sample project is "The Acts of the Apostles"
        assert "Title" in infos
        assert "Acts" in infos["Title"]

    def test_read_characters(self, project_copy):
        from manuskript.mcp.project_reader import read_project
        data = read_project(project_copy)
        chars = data["characters"]
        assert isinstance(chars, list)
        assert len(chars) > 0
        # Check that every character has at least a Name field
        for c in chars:
            assert "Name" in c, f"Character missing Name: {c}"

    def test_read_outline(self, project_copy):
        from manuskript.mcp.project_reader import read_project
        data = read_project(project_copy)
        outline = data["outline"]
        assert isinstance(outline, list)
        assert len(outline) > 0

    def test_read_plots(self, project_copy):
        from manuskript.mcp.project_reader import read_project
        data = read_project(project_copy)
        plots = data["plots"]
        assert isinstance(plots, list)
        assert len(plots) > 0
        for p in plots:
            assert "ID" in p
            assert "name" in p

    def test_read_world(self, project_copy):
        from manuskript.mcp.project_reader import read_project
        data = read_project(project_copy)
        world = data["world"]
        assert isinstance(world, list)
        assert len(world) > 0

    def test_read_summary(self, project_copy):
        from manuskript.mcp.project_reader import read_project
        data = read_project(project_copy)
        assert "summary" in data
        assert isinstance(data["summary"], dict)

    def test_read_labels(self, project_copy):
        from manuskript.mcp.project_reader import read_project
        data = read_project(project_copy)
        assert isinstance(data["labels"], list)

    def test_read_statuses(self, project_copy):
        from manuskript.mcp.project_reader import read_project
        data = read_project(project_copy)
        assert isinstance(data["statuses"], list)


class TestSearch:
    def test_search_returns_list(self, project_copy):
        from manuskript.mcp.project_reader import search_project
        results = search_project(project_copy, "Peter")
        assert isinstance(results, list)

    def test_search_finds_character(self, project_copy):
        from manuskript.mcp.project_reader import search_project
        results = search_project(project_copy, "Peter")
        assert any(r["type"] == "character" for r in results), (
            "Expected at least one character result for 'Peter'"
        )

    def test_search_case_insensitive(self, project_copy):
        from manuskript.mcp.project_reader import search_project
        lower = search_project(project_copy, "peter", case_sensitive=False)
        upper = search_project(project_copy, "Peter", case_sensitive=False)
        assert len(lower) == len(upper)

    def test_search_no_results(self, project_copy):
        from manuskript.mcp.project_reader import search_project
        results = search_project(project_copy, "xyzzy_nonexistent_token_12345")
        assert results == []

    def test_search_has_required_keys(self, project_copy):
        from manuskript.mcp.project_reader import search_project
        results = search_project(project_copy, "Jerusalem")
        for r in results:
            for key in ("type", "id", "title", "field", "excerpt"):
                assert key in r, f"Result missing key {key!r}: {r}"


# ---------------------------------------------------------------------------
# project_writer tests
# ---------------------------------------------------------------------------

class TestWriteScene:
    def test_write_scene_replace(self, project_copy):
        from manuskript.mcp.project_reader import read_project
        from manuskript.mcp.project_writer import write_scene

        data = read_project(project_copy)

        # Find the first non-empty text scene
        def first_text_scene(items):
            for item in items:
                if item.get("_type") == "md" and item.get("ID"):
                    return item
                r = first_text_scene(item.get("children", []))
                if r:
                    return r
            return None

        scene = first_text_scene(data["outline"])
        if scene is None:
            pytest.skip("No text scene found in sample project.")

        scene_id = scene["ID"]
        new_content = "TEST CONTENT — REPLACED BY MCP TEST"
        path = write_scene(project_copy, scene_id, new_content, append=False)
        assert path is not None

        # Verify change
        data2 = read_project(project_copy)
        scene2 = first_text_scene(data2["outline"])
        assert scene2 is not None
        assert scene2.get("text", "").strip() == new_content

    def test_write_scene_append(self, project_copy):
        from manuskript.mcp.project_reader import read_project
        from manuskript.mcp.project_writer import write_scene

        data = read_project(project_copy)

        def first_text_scene(items):
            for item in items:
                if item.get("_type") == "md" and item.get("ID"):
                    return item
                r = first_text_scene(item.get("children", []))
                if r:
                    return r
            return None

        scene = first_text_scene(data["outline"])
        if scene is None:
            pytest.skip("No text scene found.")

        scene_id = scene["ID"]
        original_text = scene.get("text", "")
        appended = "\nAPPENDED BY MCP TEST"
        write_scene(project_copy, scene_id, appended, append=True)

        data2 = read_project(project_copy)
        scene2 = first_text_scene(data2["outline"])
        assert appended.strip() in scene2.get("text", "")

    def test_write_scene_invalid_id(self, project_copy):
        from manuskript.mcp.project_writer import write_scene
        with pytest.raises(FileNotFoundError):
            write_scene(project_copy, "99999", "content")


class TestCreateCharacter:
    def test_create_character(self, project_copy):
        from manuskript.mcp.project_reader import read_project
        from manuskript.mcp.project_writer import create_character

        result = create_character(
            project_copy,
            name="Test Character",
            motivation="To test the MCP server",
            goal="Complete successfully",
            conflict="Missing assertions",
            epiphany="All tests pass",
            summary="A character born from unit tests",
        )
        assert "id" in result
        assert "path" in result
        assert os.path.isfile(os.path.join(os.path.dirname(project_copy), "book-of-acts", result["path"]))

        # Verify readable
        data = read_project(project_copy)
        names = [c.get("Name", "") for c in data["characters"]]
        assert "Test Character" in names

    def test_create_character_increments_id(self, project_copy):
        from manuskript.mcp.project_writer import create_character
        r1 = create_character(project_copy, name="Alpha")
        r2 = create_character(project_copy, name="Beta")
        assert r1["id"] != r2["id"]


class TestAddPlotBeat:
    def test_add_plot_beat(self, project_copy):
        from manuskript.mcp.project_reader import read_project
        from manuskript.mcp.project_writer import add_plot_beat

        data = read_project(project_copy)
        assert data["plots"], "No plots in sample project."
        plot_id = data["plots"][0]["ID"]

        added = add_plot_beat(
            project_copy,
            plot_id=plot_id,
            title="MCP Test Beat",
            summary="Added by the MCP test suite",
        )
        assert added is True

        data2 = read_project(project_copy)
        plot2 = next(p for p in data2["plots"] if p["ID"] == plot_id)
        beat_titles = [s.get("name", "") for s in plot2.get("steps", [])]
        assert "MCP Test Beat" in beat_titles

    def test_add_plot_beat_invalid_id(self, project_copy):
        from manuskript.mcp.project_writer import add_plot_beat
        result = add_plot_beat(project_copy, plot_id="99999", title="Ghost beat")
        assert result is False


class TestUpdateWorldItem:
    def test_create_world_item(self, project_copy):
        from manuskript.mcp.project_reader import read_project
        from manuskript.mcp.project_writer import update_world_item

        result = update_world_item(
            project_copy,
            name="MCP Test Location",
            description="A place created by the MCP test suite.",
        )
        assert result["action"] == "created"
        assert result["id"] != ""

        data = read_project(project_copy)

        def find_item(items, name):
            for w in items:
                if w.get("name", "").lower() == name.lower():
                    return w
                found = find_item(w.get("children", []), name)
                if found:
                    return found
            return None

        found = find_item(data["world"], "MCP Test Location")
        assert found is not None
        assert found.get("description") == "A place created by the MCP test suite."

    def test_update_world_item(self, project_copy):
        from manuskript.mcp.project_writer import update_world_item

        # First create
        update_world_item(project_copy, name="MCP Update Test", description="original")
        # Then update
        result = update_world_item(project_copy, name="MCP Update Test", description="updated")
        assert result["action"] == "updated"
