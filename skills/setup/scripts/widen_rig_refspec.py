#!/usr/bin/env python3
"""Widen the fetch refspec on a rig's canonical clone.

`gt rig add` ships each canonical clone at `<gt-root>/<rig>/mayor/rig` with a
fetch refspec restricted to `main`:

    remote.origin.fetch = +refs/heads/main:refs/remotes/origin/main

The restriction hides every other branch on origin — including `develop`,
feature branches, and release branches — which matters any time the rig's
work actually lives outside `main`. This script widens the refspec to the
standard wildcard form and re-fetches so those branches become visible.

Idempotent: a rig already on the wildcard refspec is counted as `ok` and its
fetch still runs so any newly-pushed branches on origin are pulled down.

Dry-run by default. Pass `--apply` to mutate.

Usage:
    # all rigs under $MAIN_GT_ROOT (or $GT_TOWN_ROOT, or ~/gt)
    python3 skills/setup/scripts/widen_rig_refspec.py --apply

    # one specific rig
    python3 skills/setup/scripts/widen_rig_refspec.py --rig <name> --apply

    # machine-readable
    python3 skills/setup/scripts/widen_rig_refspec.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


WILDCARD_REFSPEC = "+refs/heads/*:refs/remotes/origin/*"


@dataclass
class RigReport:
    name: str
    clone_path: str
    status: str              # ok | widened | skipped | error
    refspec_before: str | None
    refspec_after: str | None
    branches_before: int
    branches_after: int
    error: str | None = None


def resolve_gt_root() -> Path:
    return Path(
        os.environ.get("MAIN_GT_ROOT")
        or os.environ.get("GT_TOWN_ROOT")
        or "~/gt"
    ).expanduser()


def discover_rigs(gt_root: Path) -> list[str]:
    if not gt_root.is_dir():
        return []
    rigs: list[str] = []
    for child in sorted(gt_root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        # A rig directory has a canonical clone at mayor/rig/.git.
        if (child / "mayor" / "rig" / ".git").exists():
            rigs.append(child.name)
    return rigs


def run_git(args: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.returncode, proc.stdout.strip()


def current_refspec(clone: Path) -> str | None:
    rc, out = run_git(["config", "--get-all", "remote.origin.fetch"], clone)
    if rc != 0:
        return None
    # Normalize multi-value config to a single string; multiple lines join with "\n".
    return out or None


def count_remote_branches(clone: Path) -> int:
    rc, out = run_git(["branch", "-r"], clone)
    if rc != 0:
        return 0
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    # Skip "HEAD -> origin/main" style pointer lines.
    return sum(1 for line in lines if "->" not in line)


def widen_rig(gt_root: Path, name: str, apply: bool) -> RigReport:
    clone = gt_root / name / "mayor" / "rig"
    report = RigReport(
        name=name,
        clone_path=str(clone),
        status="skipped",
        refspec_before=None,
        refspec_after=None,
        branches_before=0,
        branches_after=0,
    )

    if not (clone / ".git").exists():
        report.status = "skipped"
        report.error = "no canonical clone at mayor/rig"
        return report

    refspec_before = current_refspec(clone)
    report.refspec_before = refspec_before
    report.branches_before = count_remote_branches(clone)

    already_wide = refspec_before is not None and WILDCARD_REFSPEC in refspec_before

    if not apply:
        report.status = "ok" if already_wide else "narrow"
        report.refspec_after = refspec_before
        report.branches_after = report.branches_before
        return report

    if not already_wide:
        rc, out = run_git(
            ["config", "remote.origin.fetch", WILDCARD_REFSPEC], clone
        )
        if rc != 0:
            report.status = "error"
            report.error = f"git config failed: {out}"
            return report

    # Always fetch — widening without fetch would leave the branches
    # invisible until the next fetch, and fetching on an already-wide repo
    # just pulls any newly-pushed branches.
    rc, out = run_git(["fetch", "origin", "--prune", "--quiet"], clone)
    if rc != 0:
        report.status = "error"
        report.error = f"git fetch failed: {out}"
        return report

    report.refspec_after = current_refspec(clone)
    report.branches_after = count_remote_branches(clone)
    report.status = "ok" if already_wide else "widened"
    return report


def render_text(reports: list[RigReport], apply: bool) -> str:
    if not reports:
        return "no rigs found"
    lines: list[str] = []
    mode = "apply" if apply else "dry-run"
    lines.append(f"=== widen_rig_refspec ({mode}) ===")
    header = f"{'rig':<44} {'status':<10} {'before':>7} {'after':>7}"
    lines.append(header)
    lines.append("-" * len(header))
    for r in reports:
        before = str(r.branches_before) if r.branches_before else "-"
        after = str(r.branches_after) if r.branches_after else "-"
        lines.append(f"{r.name:<44} {r.status:<10} {before:>7} {after:>7}")
        if r.error:
            lines.append(f"    error: {r.error}")
    widened = sum(1 for r in reports if r.status == "widened")
    narrow = sum(1 for r in reports if r.status == "narrow")
    errors = sum(1 for r in reports if r.status == "error")
    lines.append("")
    if apply:
        lines.append(f"widened={widened} errors={errors}")
    else:
        lines.append(f"narrow={narrow} (run with --apply to widen)")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Widen fetch refspec on gt rig canonical clones."
    )
    parser.add_argument(
        "--rig",
        help="Operate on a single rig by name. Default: all rigs under the GT root.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the widen+fetch. Default is dry-run.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON.",
    )
    args = parser.parse_args()

    gt_root = resolve_gt_root()
    if args.rig:
        rigs = [args.rig]
    else:
        rigs = discover_rigs(gt_root)

    reports = [widen_rig(gt_root, name, args.apply) for name in rigs]

    if args.json:
        payload = {
            "gt_root": str(gt_root),
            "apply": args.apply,
            "rigs": [asdict(r) for r in reports],
        }
        print(json.dumps(payload, indent=2))
    else:
        print(render_text(reports, args.apply))

    if any(r.status == "error" for r in reports):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
