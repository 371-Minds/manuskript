#!/usr/bin/env python
# --!-- coding: utf8 --!--
"""
AI Assistant panel for the Manuskript main window.

Provides a collapsible dock widget that lets the user select and run any
of the Manuskript ADK agents without blocking the Qt event loop.

The panel:
  - Shows a dropdown to choose the active agent.
  - Has a "Run Agent" button that spawns the agent in a QThread.
  - Displays streaming progress in a read-only text pane.
  - Offers "Accept" / "Discard" buttons for proposed writes.
"""

import asyncio
import os
import threading
from typing import Optional

from PyQt5.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDockWidget,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from manuskript import settings as S

import logging

LOGGER = logging.getLogger(__name__)

# Agent display names mapped to internal keys
_AGENTS = {
    "Plot Consistency": "plot",
    "Style & Consistency": "style",
    "Writing Continuation": "continuation",
    "Character Development": "character",
    "World Builder": "world",
}

# Agents that require a scene ID
_NEEDS_SCENE = {"continuation", "world"}
# Agents that require a character name
_NEEDS_NAME = {"character"}


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class _AgentWorker(QObject):
    """Runs an ADK agent in a background thread and emits progress signals."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        project_path: str,
        agent_key: str,
        scene_id: str = "",
        character_name: str = "",
        character_description: str = "",
        max_scenes: int = 10,
        dry_run: bool = False,
    ):
        super().__init__()
        self._project = project_path
        self._agent = agent_key
        self._scene_id = scene_id
        self._char_name = character_name
        self._char_desc = character_description
        self._max_scenes = max_scenes
        self._dry_run = dry_run

    def run(self) -> None:
        """Entry point called by QThread.started."""
        try:
            result = asyncio.run(self._run_agent())
            self.finished.emit(result)
        except Exception as exc:
            LOGGER.exception("Agent run failed: %s", exc)
            self.error.emit(str(exc))

    async def _run_agent(self) -> str:
        if self._agent == "plot":
            from manuskript.agents.plot_agent import run_plot_agent
            return await run_plot_agent(self._project)

        elif self._agent == "style":
            from manuskript.agents.style_agent import run_style_agent
            return await run_style_agent(self._project, max_scenes=self._max_scenes)

        elif self._agent == "continuation":
            from manuskript.agents.continuation_agent import run_continuation_agent
            return await run_continuation_agent(
                self._project,
                scene_id=self._scene_id,
                dry_run=self._dry_run,
            )

        elif self._agent == "character":
            from manuskript.agents.character_agent import run_character_agent
            return await run_character_agent(
                self._project,
                name=self._char_name,
                description=self._char_desc,
            )

        elif self._agent == "world":
            from manuskript.agents.world_agent import run_world_agent
            return await run_world_agent(self._project, scene_id=self._scene_id)

        return "Unknown agent."


# ---------------------------------------------------------------------------
# Main panel widget
# ---------------------------------------------------------------------------

class AiPanel(QWidget):
    """AI Assistant panel widget.  Designed to be embedded in a QDockWidget."""

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self._mw = main_window
        self._worker: Optional[_AgentWorker] = None
        self._thread: Optional[QThread] = None
        self._last_result: str = ""

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        # --- Agent selector ---
        agent_group = QGroupBox("Agent")
        agent_layout = QVBoxLayout(agent_group)

        self._combo_agent = QComboBox()
        for label in _AGENTS:
            self._combo_agent.addItem(label)
        self._combo_agent.currentIndexChanged.connect(self._on_agent_changed)
        agent_layout.addWidget(self._combo_agent)

        root_layout.addWidget(agent_group)

        # --- Parameter fields ---
        param_group = QGroupBox("Parameters")
        param_layout = QVBoxLayout(param_group)

        # Scene ID
        self._lbl_scene = QLabel("Scene ID:")
        self._txt_scene = QLineEdit()
        self._txt_scene.setPlaceholderText("e.g. 3")
        self._row_scene = QHBoxLayout()
        self._row_scene.addWidget(self._lbl_scene)
        self._row_scene.addWidget(self._txt_scene)
        param_layout.addLayout(self._row_scene)

        # Character name
        self._lbl_name = QLabel("Character name:")
        self._txt_name = QLineEdit()
        self._txt_name.setPlaceholderText("e.g. Ada Lovelace")
        self._row_name = QHBoxLayout()
        self._row_name.addWidget(self._lbl_name)
        self._row_name.addWidget(self._txt_name)
        param_layout.addLayout(self._row_name)

        # Character description
        self._lbl_desc = QLabel("Description:")
        self._txt_desc = QTextEdit()
        self._txt_desc.setPlaceholderText("Short description for the character agent…")
        self._txt_desc.setFixedHeight(60)
        param_layout.addWidget(self._lbl_desc)
        param_layout.addWidget(self._txt_desc)

        # Max scenes
        self._lbl_max = QLabel("Max scenes:")
        self._spn_max = QSpinBox()
        self._spn_max.setRange(1, 100)
        self._spn_max.setValue(10)
        self._row_max = QHBoxLayout()
        self._row_max.addWidget(self._lbl_max)
        self._row_max.addWidget(self._spn_max)
        self._row_max.addStretch()
        param_layout.addLayout(self._row_max)

        root_layout.addWidget(param_group)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        self._btn_run = QPushButton("▶  Run Agent")
        self._btn_run.clicked.connect(self._run_agent)
        self._btn_cancel = QPushButton("■  Stop")
        self._btn_cancel.setEnabled(False)
        self._btn_cancel.clicked.connect(self._cancel_agent)
        btn_layout.addWidget(self._btn_run)
        btn_layout.addWidget(self._btn_cancel)
        root_layout.addLayout(btn_layout)

        # --- Output pane ---
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout(output_group)
        self._txt_output = QTextEdit()
        self._txt_output.setReadOnly(True)
        self._txt_output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        output_layout.addWidget(self._txt_output)

        # Accept / Discard
        action_layout = QHBoxLayout()
        self._btn_accept = QPushButton("✔  Accept")
        self._btn_accept.setEnabled(False)
        self._btn_accept.clicked.connect(self._accept_result)
        self._btn_discard = QPushButton("✘  Discard")
        self._btn_discard.setEnabled(False)
        self._btn_discard.clicked.connect(self._discard_result)
        action_layout.addWidget(self._btn_accept)
        action_layout.addWidget(self._btn_discard)
        output_layout.addLayout(action_layout)

        root_layout.addWidget(output_group, stretch=1)

        # Trigger initial param visibility
        self._on_agent_changed(0)

    # ------------------------------------------------------------------
    # Param visibility
    # ------------------------------------------------------------------

    def _on_agent_changed(self, index: int) -> None:
        agent_key = _AGENTS[self._combo_agent.currentText()]
        needs_scene = agent_key in _NEEDS_SCENE
        needs_name = agent_key in _NEEDS_NAME
        needs_max = agent_key == "style"

        for w in (self._lbl_scene, self._txt_scene):
            w.setVisible(needs_scene)
        for w in (self._lbl_name, self._txt_name, self._lbl_desc, self._txt_desc):
            w.setVisible(needs_name)
        for w in (self._lbl_max, self._spn_max):
            w.setVisible(needs_max)

    # ------------------------------------------------------------------
    # Agent control
    # ------------------------------------------------------------------

    def _run_agent(self) -> None:
        if self._thread and self._thread.isRunning():
            return

        if not self._mw or not self._mw.currentProject:
            QMessageBox.warning(self, "No project", "Please open a project first.")
            return

        # Check AI key
        if not os.environ.get("MANUSKRIPT_AI_KEY") and not os.environ.get("GOOGLE_API_KEY"):
            QMessageBox.warning(
                self,
                "API key not set",
                "Set the MANUSKRIPT_AI_KEY or GOOGLE_API_KEY environment variable "
                "before running an AI agent.\n\nSee .env.example for details.",
            )
            return

        agent_key = _AGENTS[self._combo_agent.currentText()]

        # Validate required fields
        if agent_key in _NEEDS_SCENE and not self._txt_scene.text().strip():
            QMessageBox.warning(self, "Scene ID required", "Please enter a Scene ID.")
            return
        if agent_key in _NEEDS_NAME and not self._txt_name.text().strip():
            QMessageBox.warning(self, "Name required", "Please enter a character name.")
            return

        self._txt_output.clear()
        self._txt_output.setPlainText("Running agent…\n")
        self._btn_run.setEnabled(False)
        self._btn_cancel.setEnabled(True)
        self._btn_accept.setEnabled(False)
        self._btn_discard.setEnabled(False)

        self._worker = _AgentWorker(
            project_path=self._mw.currentProject,
            agent_key=agent_key,
            scene_id=self._txt_scene.text().strip(),
            character_name=self._txt_name.text().strip(),
            character_description=self._txt_desc.toPlainText().strip(),
            max_scenes=self._spn_max.value(),
        )
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_agent_finished)
        self._worker.error.connect(self._on_agent_error)
        self._thread.start()

    def _cancel_agent(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.requestInterruption()
            self._thread.quit()
            self._thread.wait(3000)
            self._txt_output.append("\n[Agent cancelled]")
        self._btn_run.setEnabled(True)
        self._btn_cancel.setEnabled(False)

    def _on_agent_finished(self, result: str) -> None:
        self._last_result = result
        self._txt_output.setPlainText(result)
        self._btn_run.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        # Enable accept/discard only if there is output worth acting on
        agent_key = _AGENTS[self._combo_agent.currentText()]
        if agent_key not in ("plot", "style"):  # read-only agents
            self._btn_accept.setEnabled(True)
            self._btn_discard.setEnabled(True)

        if self._thread:
            self._thread.quit()

    def _on_agent_error(self, message: str) -> None:
        self._txt_output.setPlainText(f"Error:\n{message}")
        self._btn_run.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        if self._thread:
            self._thread.quit()

    # ------------------------------------------------------------------
    # Accept / Discard
    # ------------------------------------------------------------------

    def _accept_result(self) -> None:
        QMessageBox.information(
            self,
            "Changes applied",
            "The agent has already written changes to the project files during execution.\n\n"
            "Reload the project (File → Close Project, then reopen it) to see the "
            "updates reflected in the editor.",
        )
        self._btn_accept.setEnabled(False)
        self._btn_discard.setEnabled(False)

    def _discard_result(self) -> None:
        self._last_result = ""
        self._txt_output.clear()
        self._btn_accept.setEnabled(False)
        self._btn_discard.setEnabled(False)
