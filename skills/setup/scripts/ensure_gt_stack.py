#!/usr/bin/env python3
"""Install or refresh the gt-stack helper script.

Strategy: symlink the in-plugin `bin/gt-stack` into a user-owned PATH
directory (default: `~/.local/bin`). That keeps a single source of truth
inside the concierge plugin, so plugin upgrades ship updated gt-stack
automatically.

Plan/apply pattern matches ensure_gt.py: default prints the plan,
`--apply` performs the change. Idempotent — re-running on an already-
installed symlink is a no-op.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def plugin_root() -> Path:
    # scripts/ -> setup/ -> skills/ -> plugin root
    return Path(__file__).resolve().parents[3]


def default_install_dir() -> Path:
    raw = os.environ.get("GT_STACK_BIN_DIR") or "~/.local/bin"
    return Path(raw).expanduser().resolve()


def on_path(dir_path: Path) -> bool:
    parts = os.environ.get("PATH", "").split(os.pathsep)
    return any(Path(p).expanduser().resolve() == dir_path for p in parts if p)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install or refresh the gt-stack helper by symlinking it into a PATH directory.")
    parser.add_argument("--install-dir", default="", help="Directory to symlink gt-stack into. Defaults to $GT_STACK_BIN_DIR or ~/.local/bin.")
    parser.add_argument("--apply", action="store_true", help="Apply changes instead of printing the plan.")
    args = parser.parse_args()

    source = plugin_root() / "bin" / "gt-stack"
    target_dir = Path(args.install_dir).expanduser().resolve() if args.install_dir else default_install_dir()
    target = target_dir / "gt-stack"

    print(f"SOURCE {source}")
    print(f"TARGET {target}")

    if not source.exists():
        print(f"ERROR source {source} not found; the concierge plugin checkout is incomplete")
        return 1

    already_linked = target.is_symlink() and target.resolve() == source
    already_file = target.exists() and not target.is_symlink()
    print(f"INSTALL_DIR_ON_PATH {str(on_path(target_dir)).lower()}")
    print(f"ALREADY_LINKED {str(already_linked).lower()}")
    print(f"ALREADY_NON_SYMLINK {str(already_file).lower()}")

    if already_linked:
        print("STATUS ok")
        return 0

    if already_file:
        print(f"ERROR {target} exists and is not a symlink; refusing to overwrite")
        return 2

    if not args.apply:
        print("PLAN symlink will be created on --apply")
        return 0

    target_dir.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        target.unlink()
    os.symlink(source, target)
    # Ensure the source is executable (in case a fresh clone has wrong bits)
    mode = source.stat().st_mode
    source.chmod(mode | 0o111)

    print(f"CMD ln -s {source} {target}")
    print("STATUS installed")

    if not on_path(target_dir):
        print(f"NOTE {target_dir} is not on PATH. Add it to your shell profile:")
        print(f'  export PATH="{target_dir}:$PATH"')

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
