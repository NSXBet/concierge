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
    status: str              # ok | widened | narrow | skipped | error
    refspec_before: str | None
    refspec_after: str | None
    branches_before: int
    branches_after: int
    error: str | None = None
    fetch_error: str | None = None


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
        # A rig directory has config.json plus a canonical clone at
        # mayor/rig/.git. Matches the discovery predicate in
        # skills/setup/scripts/ensure_gt.py and audit_env.py.
        if (child / "config.json").exists() and (
            child / "mayor" / "rig" / ".git"
        ).exists():
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
        # --replace-all normalises multi-value `remote.origin.fetch` configs.
        # A bare `git config <key> <value>` errors (exit 5) when the key
        # already has more than one entry, which `current_refspec()` reads
        # via --get-all precisely because that state is possible.
        rc, out = run_git(
            ["config", "--replace-all", "remote.origin.fetch", WILDCARD_REFSPEC],
            clone,
        )
        if rc != 0:
            report.status = "error"
            report.error = f"git config failed: {out}"
            return report

    # Refspec is now correct on disk. Fetch is best-effort — a fetch
    # failure (network, auth, unreachable origin) must not mask the fact
    # that the config change landed, so we record it separately and keep
    # status tied to the refspec outcome.
    rc, out = run_git(["fetch", "origin", "--prune", "--quiet"], clone)
    if rc != 0:
        report.fetch_error = out
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
        if r.fetch_error:
            lines.append(f"    fetch failed (config widened): {r.fetch_error}")
    widened = sum(1 for r in reports if r.status == "widened")
    narrow = sum(1 for r in reports if r.status == "narrow")
    errors = sum(1 for r in reports if r.status == "error")
    fetch_errors = sum(1 for r in reports if r.fetch_error)
    lines.append("")
    if apply:
        summary = f"widened={widened} errors={errors}"
        if fetch_errors:
            summary += f" fetch_errors={fetch_errors}"
        lines.append(summary)
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
    known_rigs = discover_rigs(gt_root)
    if args.rig:
        if args.rig not in known_rigs:
            print(
                f"error: rig {args.rig!r} not found under {gt_root}. "
                f"Known rigs: {', '.join(known_rigs) or '(none)'}",
                file=sys.stderr,
            )
            return 2
        rigs = [args.rig]
    else:
        rigs = known_rigs

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

    # fetch_error counts as exit 1 so callers (audit_env.py --upgrade) can
    # surface partial success — the refspec on disk is correct, but the
    # subsequent fetch did not land the new branches.
    if any(r.status == "error" or r.error or r.fetch_error for r in reports):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
