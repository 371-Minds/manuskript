#!/usr/bin/env python
# --!-- coding: utf8 --!--
"""
CLI entry point for the Manuskript MCP server.

Usage::

    python -m manuskript.mcp --project /path/to/my-book.msk
    python -m manuskript.mcp --project /path/to/my-book.msk --transport sse --port 8765
"""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m manuskript.mcp",
        description="Run the Manuskript MCP server for a given project file.",
    )
    parser.add_argument(
        "--project",
        required=True,
        metavar="PATH",
        help="Path to the .msk project file.",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport to use (default: stdio).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port number when using SSE transport (default: 8765).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host when using SSE transport (default: 127.0.0.1).",
    )

    args = parser.parse_args()

    # Late import so argparse errors surface first
    from manuskript.mcp.server import configure, mcp

    try:
        configure(args.project)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
