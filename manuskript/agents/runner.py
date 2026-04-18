#!/usr/bin/env python
# --!-- coding: utf8 --!--
"""
Agent runner — CLI entry point for all Manuskript ADK agents.

Usage::

    python -m manuskript.agents --project my.msk --agent plot
    python -m manuskript.agents --project my.msk --agent continuation --scene-id 3
    python -m manuskript.agents --project my.msk --agent character --name "Ada Lovelace" --description "A brilliant mathematician drawn into a conspiracy"
    python -m manuskript.agents --project my.msk --agent world --scene-id 5
    python -m manuskript.agents --project my.msk --agent style --max-scenes 15
"""

import argparse
import asyncio
import os
import sys


async def _run(args: argparse.Namespace) -> str:
    agent = args.agent

    if agent == "continuation":
        if not args.scene_id:
            print("Error: --scene-id is required for the continuation agent.", file=sys.stderr)
            sys.exit(1)
        from manuskript.agents.continuation_agent import run_continuation_agent
        return await run_continuation_agent(
            args.project,
            scene_id=args.scene_id,
            extra_instructions=args.instructions or "",
            dry_run=args.dry_run,
        )

    elif agent == "character":
        if not args.name:
            print("Error: --name is required for the character agent.", file=sys.stderr)
            sys.exit(1)
        from manuskript.agents.character_agent import run_character_agent
        return await run_character_agent(
            args.project,
            name=args.name,
            description=args.description or "",
            importance=args.importance or "0",
        )

    elif agent == "plot":
        from manuskript.agents.plot_agent import run_plot_agent
        return await run_plot_agent(args.project)

    elif agent == "world":
        if not args.scene_id:
            print("Error: --scene-id is required for the world agent.", file=sys.stderr)
            sys.exit(1)
        from manuskript.agents.world_agent import run_world_agent
        return await run_world_agent(args.project, scene_id=args.scene_id)

    elif agent == "style":
        from manuskript.agents.style_agent import run_style_agent
        return await run_style_agent(args.project, max_scenes=args.max_scenes or 10)

    else:
        print(f"Unknown agent: {agent!r}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m manuskript.agents",
        description="Run a Manuskript AI agent against a project.",
    )
    parser.add_argument(
        "--project",
        required=True,
        metavar="PATH",
        help="Path to the .msk project file.",
    )
    parser.add_argument(
        "--agent",
        required=True,
        choices=["continuation", "character", "plot", "world", "style"],
        help="Which agent to run.",
    )
    # Shared optional arguments
    parser.add_argument("--scene-id", metavar="ID", help="Scene ID (continuation, world agents).")
    parser.add_argument("--name", help="Character name (character agent).")
    parser.add_argument("--description", help="Character description (character agent).")
    parser.add_argument("--importance", choices=["0", "1", "2"], default="0",
                        help="Character importance: 0=minor, 1=secondary, 2=major.")
    parser.add_argument("--instructions", metavar="TEXT",
                        help="Additional instructions for the continuation agent.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Read but do not write (continuation agent).")
    parser.add_argument("--max-scenes", type=int, default=10,
                        help="Max scenes to analyse (style agent, default 10).")

    args = parser.parse_args()

    if not os.path.exists(args.project):
        print(f"Error: project not found: {args.project!r}", file=sys.stderr)
        sys.exit(1)

    result = asyncio.run(_run(args))
    print(result)


if __name__ == "__main__":
    main()
