#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def default_gt_root() -> Path:
    raw = os.environ.get("MAIN_GT_ROOT") or os.environ.get("GT_TOWN_ROOT") or "~/gt"
    return Path(raw).expanduser().resolve()


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=os.environ.copy(),
    )
    return proc.returncode, proc.stdout.strip()


def is_initialized(gt_root: Path) -> bool:
    return (gt_root / "mayor").exists() and (gt_root / ".beads").exists()


def list_rigs(gt_root: Path) -> list[str]:
    if not gt_root.exists():
        return []
    rigs: list[str] = []
    for child in sorted(gt_root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "config.json").exists() and (child / "mayor/rig").exists():
            rigs.append(child.name)
    return rigs


def derive_name(spec: str) -> tuple[str, str]:
    if "=" in spec:
        name, url = spec.split("=", 1)
        return name.strip(), url.strip()
    url = spec.strip()
    parsed = urlparse(url)
    candidate = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    if candidate.endswith(".git"):
        candidate = candidate[:-4]
    candidate = re.sub(r"[^a-zA-Z0-9._-]+", "-", candidate).strip("-") or "repo"
    return candidate.lower(), url


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize or inspect a Gas Town root and optionally add rigs.")
    parser.add_argument("--gt-root", default="", help="GT root path. Defaults to MAIN_GT_ROOT or GT_TOWN_ROOT.")
    parser.add_argument("--repo", action="append", default=[], help="Repo spec as URL or name=url. Repeatable.")
    parser.add_argument("--apply", action="store_true", help="Apply changes instead of printing the plan.")
    args = parser.parse_args()

    gt_root = Path(args.gt_root).expanduser().resolve() if args.gt_root else default_gt_root()
    existed_before = gt_root.exists()
    initialized_before = is_initialized(gt_root)

    print(f"GT_ROOT {gt_root}")
    print(f"EXISTED_BEFORE {str(existed_before).lower()}")
    print(f"INITIALIZED_BEFORE {str(initialized_before).lower()}")

    if args.apply and not initialized_before:
        rc, out = run(["gt", "install", str(gt_root)])
        print("CMD gt install")
        print(out)
        if rc != 0:
            print("ERROR gt install failed")
            return rc

    initialized_after = is_initialized(gt_root)
    rigs_before = list_rigs(gt_root)
    print(f"INITIALIZED_AFTER {str(initialized_after).lower()}")
    print(f"RIGS_BEFORE {','.join(rigs_before)}")

    if args.repo:
        for spec in args.repo:
            name, url = derive_name(spec)
            print(f"PLAN_RIG {name} {url}")
            if args.apply:
                rc, out = run(["gt", "rig", "add", name, url], cwd=gt_root)
                print(f"CMD gt rig add {name} {url}")
                print(out)
                if rc != 0:
                    print(f"ERROR failed to add rig {name}")
                    return rc

    rigs_after = list_rigs(gt_root)
    print(f"RIGS_AFTER {','.join(rigs_after)}")
    print(f"RIGS_COUNT {len(rigs_after)}")
    print(f"NEEDS_RIG_INPUT {str(len(rigs_after) == 0 and len(args.repo) == 0).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
