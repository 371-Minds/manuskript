# AI Features — MCP Server & ADK Agents

Manuskript includes a built-in **MCP (Model Context Protocol) server** and a
suite of **Google ADK agents** that let any MCP-compatible AI client read and
write project data autonomously.

---

## Quick-start

### 1. Install AI dependencies

```bash
pip install mcp[cli]>=1.0 google-adk>=1.0 python-dotenv>=1.0 anyio>=4.0
```

### 2. Set your API key

Copy `.env.example` to `.env` and fill in your key:

```bash
cp .env.example .env
# Edit .env and set MANUSKRIPT_AI_KEY=your_key
```

Load it in your shell:

```bash
# bash / zsh
export $(grep -v '^#' .env | xargs)
```

### 3. Start the MCP server

```bash
python -m manuskript.mcp --project /path/to/my-book.msk
```

The server speaks **stdio** by default (compatible with Claude Desktop,
Cursor, and Google ADK).  Use `--transport sse` for HTTP-based clients.

---

## MCP Resources (read-only)

| URI | Description |
|-----|-------------|
| `project://outline` | Full chapter/scene tree (title, ID, text, POV, status…) |
| `project://characters` | All character profiles (name, motivation, goal, conflict, epiphany…) |
| `project://plots` | Plot lines and their resolution beats |
| `project://world` | World-building entries (places, factions, items…) |
| `project://settings` | Book metadata: title, author, summary, premise, labels, statuses |

---

## MCP Tools (read-write)

| Tool | Description |
|------|-------------|
| `get_scene_text_tool(scene_id)` | Retrieve the full text of a scene by ID |
| `write_scene_tool(scene_id, content, append)` | Write or append text to a scene |
| `create_character_tool(name, motivation, goal, conflict, epiphany, summary, importance)` | Create a new character |
| `add_plot_beat_tool(plot_id, title, summary, characters)` | Append a beat to a plot |
| `update_world_item_tool(name, description, passion, conflict)` | Create or update a world entry |
| `search_project_tool(query, case_sensitive)` | Full-text search across the project |

---

## ADK Agents

All agents are in `manuskript/agents/`.  Run via the CLI:

```bash
python -m manuskript.agents --project my.msk --agent <name> [options]
```

### Writing Continuation Agent

Continues an existing scene, respecting the POV character's voice.

```bash
python -m manuskript.agents --project my.msk --agent continuation --scene-id 3
```

| Parameter | Description |
|-----------|-------------|
| `--scene-id` | **Required.** Numeric ID of the scene to continue. |
| `--instructions` | Optional extra guidance (e.g. "focus on the conflict"). |
| `--dry-run` | Read and describe what would be written, without saving. |

Output saved to: `_ai_reports/continuation_scene_<id>.md`

---

### Character Development Agent

Creates a fully fleshed-out character from a name and brief description.

```bash
python -m manuskript.agents --project my.msk --agent character \
    --name "Ada Lovelace" \
    --description "A mathematician drawn into a conspiracy" \
    --importance 1
```

| Parameter | Description |
|-----------|-------------|
| `--name` | **Required.** Character name. |
| `--description` | Optional high-level description. |
| `--importance` | `0`=minor, `1`=secondary, `2`=major (default: `0`). |

Output saved to: `_ai_reports/character_<name>.md`

---

### Plot Consistency Agent

Analyses the manuscript for structural issues (orphaned scenes, unresolved plots, character gaps).

```bash
python -m manuskript.agents --project my.msk --agent plot
```

Read-only — does not modify the project.

Output saved to: `_ai_reports/plot_consistency_report.md`

---

### World Builder Agent

Extracts named entities from a scene and creates world entries for unknown ones.

```bash
python -m manuskript.agents --project my.msk --agent world --scene-id 7
```

| Parameter | Description |
|-----------|-------------|
| `--scene-id` | **Required.** Numeric ID of the scene to analyse. |

Output saved to: `_ai_reports/world_builder_scene_<id>.md`

---

### Style & Consistency Agent

Reviews a sample of scenes for POV shifts, tense inconsistencies, repeated phrases, and more.

```bash
python -m manuskript.agents --project my.msk --agent style --max-scenes 20
```

| Parameter | Description |
|-----------|-------------|
| `--max-scenes` | Number of scenes to analyse (default: `10`). |

Read-only — does not modify the project.

Output saved to: `_ai_reports/style_consistency_report.md`

---

## UI Panel

The **AI Assistant** dock panel is available under **Tools → AI Assistant**
(or `Ctrl+Alt+A`).  It lets you run any agent from within the application
without leaving the editor.

The panel requires an open project and a valid API key in the environment.

---

## Configuration

AI settings are stored under the `ai` key in `settings.txt` (inside the
project folder):

| Key | Default | Description |
|-----|---------|-------------|
| `provider` | `"google"` | AI provider: `google`, `openai`, `anthropic`, `local` |
| `model` | `"gemini-2.0-flash"` | Model name |
| `mcp_transport` | `"stdio"` | Transport: `stdio` or `sse` |
| `mcp_port` | `8765` | Port for SSE transport |
| `consent_given` | `false` | Whether the user has opted in to sending data |

**The API key is never stored in the settings file.**  It is always read from
the `MANUSKRIPT_AI_KEY` (or `GOOGLE_API_KEY`) environment variable.

---

## Security & Privacy

- No project content is ever sent to an external API without you explicitly
  running an agent.
- The MCP server binds to `127.0.0.1` (localhost) by default when using SSE.
- API keys are read exclusively from environment variables — they are never
  written to disk by Manuskript.
- All agent reports are saved locally in `_ai_reports/` next to your project
  folder.

---

## Supported project formats

| Format | Read | Write |
|--------|------|-------|
| Folder-based (plain text, default) | ✅ | ✅ |
| Zip-based (`.msk` zip) | ✅ | ❌ (read-only) |

To enable writing for a zip project, open it in Manuskript, go to
**Settings → Save → Plain text** and save once to convert.
