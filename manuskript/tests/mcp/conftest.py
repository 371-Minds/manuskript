#!/usr/bin/env python
# --!-- coding: utf8 --!--
"""
Pytest conftest for the MCP test suite.

These tests are pure-Python (no PyQt5) and must be run with the
``--import-mode=importlib`` flag to avoid triggering the parent
``manuskript/tests/__init__.py`` which imports PyQt5:

    pytest manuskript/tests/mcp/ --import-mode=importlib

Alternatively you can run them directly:

    python -m pytest manuskript/tests/mcp/ --import-mode=importlib
"""
