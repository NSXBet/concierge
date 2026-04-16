#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

SHARED_DIRS = [
    Path("Shared/Standards"),
    Path("Shared/Security"),
    Path("Shared/Reliability"),
    Path("Projects"),
]

SHARED_FILES = {
    Path("Shared/README.md"): "# Shared\n\n## Purpose\nShared standards, security, and reliability notes.\n",
}

PROJECT_FILES = {
    Path("README.md"): "# {project}\n\n## Purpose\n\n## Rigs\n\n## Active work\n\n## Key docs\n- [[Notes/README]]\n- [[Decisions/README]]\n",
    Path("Notes/README.md"): "# Notes\n\nWorking notes, research, and transient project context.\n",
    Path("Decisions/README.md"): "# Decisions\n\n## Durable decisions\n\n",
    Path("Convoys/README.md"): "# Convoys\n\nFeature and work-tracking notes live here.\n",
}


def default_vault() -> Path:
    raw = os.environ.get("MAIN_OBSIDIAN_ROOT") or os.environ.get("OBSIDIAN_VAULT") or "~/notes/work"
    return Path(raw).expanduser().resolve()


def parse_projects(value: str | None) -> list[str]:
    if not value:
        return []
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]


class Recorder:
    def __init__(self) -> None:
        self.created_dirs: list[str] = []
        self.created_files: list[str] = []
        self.skipped_files: list[str] = []

    def mkdir(self, path: Path) -> None:
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            self.created_dirs.append(str(path))

    def write_if_missing(self, path: Path, content: str) -> None:
        if path.exists():
            self.skipped_files.append(str(path))
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self.created_files.append(str(path))


def bootstrap(vault: Path, projects: Iterable[str]) -> Recorder:
    recorder = Recorder()
    recorder.mkdir(vault)

    for rel in SHARED_DIRS:
        recorder.mkdir(vault / rel)

    for rel, content in SHARED_FILES.items():
        recorder.write_if_missing(vault / rel, content)

    for project in projects:
        base = vault / "Projects" / project
        recorder.mkdir(base)
        recorder.mkdir(base / "Notes")
        recorder.mkdir(base / "Decisions")
        recorder.mkdir(base / "Convoys")
        for rel, template in PROJECT_FILES.items():
            recorder.write_if_missing(base / rel, template.format(project=project))

    return recorder


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or repair an Obsidian vault structure.")
    parser.add_argument("vault", nargs="?", help="Path to the vault root. Defaults to MAIN_OBSIDIAN_ROOT or OBSIDIAN_VAULT.")
    parser.add_argument("--projects", help="Comma-separated project names", default="")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser().resolve() if args.vault else default_vault()
    projects = parse_projects(args.projects)
    result = bootstrap(vault, projects)

    print(f"vault={vault}")
    print(f"created_dirs={len(result.created_dirs)}")
    for item in result.created_dirs:
        print(f"DIR {item}")
    print(f"created_files={len(result.created_files)}")
    for item in result.created_files:
        print(f"FILE {item}")
    print(f"skipped_files={len(result.skipped_files)}")
    for item in result.skipped_files:
        print(f"SKIP {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
