#!/usr/bin/env python3
"""Install this Agent Skill for one or more supported agent clients."""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
from typing import Dict, Iterable, List


SKILL_NAME = "agy-image"
USER_ROOTS: Dict[str, pathlib.Path] = {
    "codex": pathlib.Path.home() / ".codex" / "skills",
    "claude": pathlib.Path.home() / ".claude" / "skills",
    "universal": pathlib.Path.home() / ".agents" / "skills",
    "gemini": pathlib.Path.home() / ".gemini" / "skills",
    "copilot": pathlib.Path.home() / ".copilot" / "skills",
    "openclaw": pathlib.Path.home() / ".openclaw" / "skills",
}
PROJECT_ROOTS: Dict[str, pathlib.Path] = {
    "codex": pathlib.Path(".agents") / "skills",
    "claude": pathlib.Path(".claude") / "skills",
    "universal": pathlib.Path(".agents") / "skills",
    "gemini": pathlib.Path(".gemini") / "skills",
    "copilot": pathlib.Path(".github") / "skills",
    "openclaw": pathlib.Path(".openclaw") / "skills",
}
COPY_ITEMS = (
    "SKILL.md",
    "agents",
    "assets",
    "references",
    "scripts",
    "skill_lifecycle.yaml",
)


def selected_agents(values: Iterable[str]) -> List[str]:
    selected: List[str] = []
    for value in values:
        names = list(USER_ROOTS) if value == "all" else [value]
        for name in names:
            if name not in selected:
                selected.append(name)
    return selected


def copy_skill(source: pathlib.Path, destination: pathlib.Path, force: bool) -> None:
    if destination.exists():
        if not force:
            raise FileExistsError(
                f"{destination} already exists; use --force to replace this skill copy"
            )
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for item_name in COPY_ITEMS:
        source_item = source / item_name
        if not source_item.exists():
            continue
        destination_item = destination / item_name
        if source_item.is_dir():
            shutil.copytree(source_item, destination_item)
        else:
            shutil.copy2(source_item, destination_item)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install agy-image for Agent Skills compatible clients."
    )
    parser.add_argument(
        "--agent",
        action="append",
        choices=[*USER_ROOTS, "all"],
        default=[],
        help="Target agent; repeatable. Defaults to universal.",
    )
    parser.add_argument(
        "--scope", choices=("user", "project"), default="user"
    )
    parser.add_argument(
        "--project-root",
        type=pathlib.Path,
        default=pathlib.Path.cwd(),
        help="Project root for --scope project (default: current directory).",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source = pathlib.Path(__file__).resolve().parent.parent
    if not (source / "SKILL.md").is_file():
        print(json.dumps({"status": "failed", "error": "SKILL.md not found"}))
        return 1

    agents = selected_agents(args.agent or ["universal"])
    destinations: List[pathlib.Path] = []
    for agent in agents:
        if args.scope == "user":
            root = USER_ROOTS[agent]
        else:
            root = args.project_root.resolve() / PROJECT_ROOTS[agent]
        destination = root / SKILL_NAME
        if destination not in destinations:
            destinations.append(destination)

    if args.dry_run:
        print(json.dumps({
            "status": "dry-run",
            "source": str(source),
            "destinations": [str(path) for path in destinations],
        }, indent=2))
        return 0

    installed: List[str] = []
    try:
        for destination in destinations:
            copy_skill(source, destination, args.force)
            installed.append(str(destination))
    except (OSError, FileExistsError) as exc:
        print(json.dumps({
            "status": "failed",
            "error": str(exc),
            "installed_before_failure": installed,
        }))
        return 1

    print(json.dumps({"status": "completed", "installed": installed}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
