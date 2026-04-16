#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


def default_gt_root() -> Path:
    raw = os.environ.get("MAIN_GT_ROOT") or os.environ.get("GT_TOWN_ROOT") or "~/gt"
    return Path(raw).expanduser().resolve()


@dataclass
class RepoPlan:
    rig: str
    repo_path: Path
    has_graph: bool
    mode: str


def list_rigs(gt_root: Path) -> list[str]:
    rigs: list[str] = []
    if not gt_root.exists():
        return rigs
    for child in sorted(gt_root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("."):
            continue
        if (child / "config.json").exists() and (child / "mayor/rig").exists():
            rigs.append(child.name)
    return rigs


def iter_target_repos(gt_root: Path, rig_names: Iterable[str]) -> list[RepoPlan]:
    plans: list[RepoPlan] = []
    for rig in rig_names:
        repo_path = gt_root / rig / "mayor" / "rig"
        if not repo_path.exists():
            continue
        if not (repo_path / ".git").exists() and not (repo_path / ".repo.git").exists():
            git_ok = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=repo_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if git_ok.returncode != 0:
                continue
        graph_json = repo_path / "graphify-out" / "graph.json"
        has_graph = graph_json.exists()
        mode = "update" if has_graph else "build"
        plans.append(RepoPlan(rig=rig, repo_path=repo_path, has_graph=has_graph, mode=mode))
    return plans


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=os.environ.copy(),
    )
    return proc.returncode, proc.stdout.strip()


def apply(plans: list[RepoPlan]) -> int:
    if shutil.which("graphify") is None:
        print("ERROR graphify command not found")
        return 2

    rc, out = run(["graphify", "install"], Path.cwd())
    if rc != 0:
        print("ERROR graphify install failed")
        print(out)
        return rc

    for plan in plans:
        print(f"RIG {plan.rig}")
        print(f"PATH {plan.repo_path}")
        for cmd in (["graphify", "claude", "install"], ["graphify", "hook", "install"]):
            rc, out = run(cmd, plan.repo_path)
            print(f"CMD {' '.join(cmd)}")
            print(out)
            if rc != 0:
                print(f"ERROR command failed for {plan.rig}")
                return rc
        build_cmd = ["graphify", ".", "--update"] if plan.mode == "update" else ["graphify", "."]
        rc, out = run(build_cmd, plan.repo_path)
        print(f"CMD {' '.join(build_cmd)}")
        print(out)
        if rc != 0:
            print(f"ERROR build failed for {plan.rig}")
            return rc
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan or refresh Graphify across GT rigs.")
    parser.add_argument("gt_root", nargs="?", help="Path to the GT root. Defaults to MAIN_GT_ROOT or GT_TOWN_ROOT.")
    parser.add_argument("--rigs", help="Comma-separated rig names", default="")
    parser.add_argument("--apply", action="store_true", help="Run the changes instead of printing the plan")
    args = parser.parse_args()

    gt_root = Path(args.gt_root).expanduser().resolve() if args.gt_root else default_gt_root()
    if args.rigs:
        rig_names = [item.strip() for item in args.rigs.split(",") if item.strip()]
    else:
        rig_names = list_rigs(gt_root)

    plans = iter_target_repos(gt_root, rig_names)
    for plan in plans:
        print(f"PLAN rig={plan.rig} path={plan.repo_path} mode={plan.mode} has_graph={str(plan.has_graph).lower()}")

    if not args.apply:
        return 0
    return apply(plans)


if __name__ == "__main__":
    raise SystemExit(main())
