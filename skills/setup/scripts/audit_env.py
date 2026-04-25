#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


SEMVER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


@dataclass
class ToolResult:
    name: str
    present: bool
    installed_version: str | None = None
    latest_version: str | None = None
    status: str = "unknown"  # ok | outdated | missing | unknown
    note: str = ""
    upgrade_cmd: list[str] | None = None


def run(cmd: list[str], timeout: float = 20.0) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout.strip()
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, ""


def parse_semver(raw: str) -> tuple[int, int, int] | None:
    if not raw:
        return None
    m = SEMVER_RE.search(raw)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def compare_semver(installed: str | None, latest: str | None) -> str:
    i = parse_semver(installed or "")
    l = parse_semver(latest or "")
    if not i or not l:
        return "unknown"
    if i >= l:
        return "ok"
    return "outdated"


def latest_release(repo: str) -> str | None:
    if shutil.which("gh") is None:
        return None
    rc, out = run(["gh", "release", "view", "--repo", repo, "--json", "tagName"])
    if rc != 0:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    return (data.get("tagName") or "").lstrip("v") or None


def check_gt() -> ToolResult:
    result = ToolResult(name="gt", present=shutil.which("gt") is not None)
    if not result.present:
        result.status = "missing"
        result.note = "not installed"
        return result
    _, out = run(["gt", "--version"])
    result.installed_version = out.strip()
    result.latest_version = latest_release("gastownhall/gastown")
    if result.installed_version and "HEAD-" in result.installed_version:
        result.status = "unknown"
        result.note = "built from source; version comparison not available"
    else:
        result.status = compare_semver(result.installed_version, result.latest_version)
    return result


def check_graphify() -> ToolResult:
    result = ToolResult(name="graphify", present=shutil.which("graphify") is not None)
    result.upgrade_cmd = ["pipx", "upgrade", "graphifyy"]
    if not result.present:
        result.status = "missing"
        result.note = "install with: pipx install graphifyy"
        return result
    if shutil.which("pipx"):
        _, out = run(["pipx", "list", "--short"])
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0] == "graphifyy":
                result.installed_version = parts[1]
                break
    result.latest_version = latest_release("safishamsi/graphify")
    result.status = compare_semver(result.installed_version, result.latest_version)
    if not result.installed_version:
        result.note = "present on PATH but pipx package 'graphifyy' not found"
    return result


def check_rtk() -> ToolResult:
    result = ToolResult(name="rtk", present=shutil.which("rtk") is not None)
    result.upgrade_cmd = ["brew", "upgrade", "rtk"] if shutil.which("brew") else None
    if not result.present:
        result.status = "missing"
        return result
    _, out = run(["rtk", "--version"])
    m = SEMVER_RE.search(out)
    if m:
        result.installed_version = m.group(0)
    result.latest_version = latest_release("rtk-ai/rtk")
    result.status = compare_semver(result.installed_version, result.latest_version)
    return result


def check_gh() -> ToolResult:
    result = ToolResult(name="gh", present=shutil.which("gh") is not None)
    result.upgrade_cmd = ["brew", "upgrade", "gh"] if shutil.which("brew") else None
    if not result.present:
        result.status = "missing"
        return result
    _, out = run(["gh", "--version"])
    first = out.splitlines()[0] if out else ""
    m = SEMVER_RE.search(first)
    if m:
        result.installed_version = m.group(0)
    result.latest_version = latest_release("cli/cli")
    result.status = compare_semver(result.installed_version, result.latest_version)
    return result


def check_git() -> ToolResult:
    result = ToolResult(name="git", present=shutil.which("git") is not None)
    if not result.present:
        result.status = "missing"
        return result
    _, out = run(["git", "--version"])
    m = SEMVER_RE.search(out)
    if m:
        result.installed_version = m.group(0)
    result.status = "ok"
    result.note = "system-managed; no upstream check"
    return result


def check_gt_stack() -> ToolResult:
    result = ToolResult(name="gt-stack", present=shutil.which("gt-stack") is not None)
    if not result.present:
        result.status = "missing"
        result.note = "install with: python3 skills/setup/scripts/ensure_gt_stack.py --apply"
        return result
    # Shipped as a Bash script inside this plugin; no upstream release to compare.
    # Probe the binary instead — a broken symlink or missing-execute-bit install
    # would otherwise be reported as healthy by a presence-only check.
    rc, _ = run(["gt-stack", "help"])
    if rc != 0:
        result.status = "missing"
        result.note = (
            "found on PATH but failed to execute; reinstall with: "
            "python3 skills/setup/scripts/ensure_gt_stack.py --apply"
        )
        return result
    result.installed_version = "plugin-local"
    result.status = "ok"
    result.note = "shipped by concierge; symlinked into $PATH"
    return result


def check_python() -> ToolResult:
    result = ToolResult(name="python3", present=shutil.which("python3") is not None)
    if not result.present:
        result.status = "missing"
        return result
    _, out = run(["python3", "--version"])
    m = SEMVER_RE.search(out)
    if m:
        result.installed_version = m.group(0)
    installed = parse_semver(result.installed_version or "")
    if installed and installed < (3, 9, 0):
        result.status = "outdated"
        result.note = f"Python 3.9+ required; found {result.installed_version}"
    else:
        result.status = "ok"
        result.note = "system-managed; no upstream check"
    return result


@dataclass
class EnvChecks:
    gt_root: Path
    gt_initialized: bool
    rigs_count: int
    vault_root: Path
    concierge_config_source: str
    concierge_config_present: bool
    mcp_obsidian_present: bool
    rtk_hook_installed: bool


def env_checks() -> EnvChecks:
    gt_root = Path(os.environ.get("MAIN_GT_ROOT") or os.environ.get("GT_TOWN_ROOT") or "~/gt").expanduser()
    gt_initialized = (gt_root / "mayor").exists() and (gt_root / ".beads").exists()
    rigs_count = 0
    if gt_root.exists():
        for child in gt_root.iterdir():
            if child.is_dir() and not child.name.startswith(".") and (child / "config.json").exists():
                rigs_count += 1

    vault_root = Path(os.environ.get("MAIN_OBSIDIAN_ROOT") or os.environ.get("OBSIDIAN_VAULT") or "~/notes/work").expanduser()

    if os.environ.get("CONCIERGE_CONFIG"):
        concierge_config_source = "env $CONCIERGE_CONFIG"
        concierge_config_present = True
    else:
        cfg_path = Path("~/.concierge.json").expanduser()
        concierge_config_source = str(cfg_path)
        concierge_config_present = cfg_path.exists()

    mcp_path = Path("~/.claude/.mcp.json").expanduser()
    mcp_obsidian_present = False
    if mcp_path.exists():
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8"))
            mcp_obsidian_present = "mcp-obsidian" in (data.get("mcpServers") or {})
        except json.JSONDecodeError:
            pass

    settings_path = Path("~/.claude/settings.json").expanduser()
    rtk_hook_installed = False
    if settings_path.exists():
        try:
            text = settings_path.read_text(encoding="utf-8")
            rtk_hook_installed = "rtk" in text.lower()
        except OSError:
            pass

    return EnvChecks(
        gt_root=gt_root,
        gt_initialized=gt_initialized,
        rigs_count=rigs_count,
        vault_root=vault_root,
        concierge_config_source=concierge_config_source,
        concierge_config_present=concierge_config_present,
        mcp_obsidian_present=mcp_obsidian_present,
        rtk_hook_installed=rtk_hook_installed,
    )


def render(tools: list[ToolResult], env: EnvChecks) -> str:
    lines: list[str] = []
    lines.append("=== tools ===")
    for t in tools:
        inst = t.installed_version or "-"
        latest = t.latest_version or "-"
        note = f"  ({t.note})" if t.note else ""
        lines.append(f"{t.name:<10} status={t.status:<8} installed={inst:<16} latest={latest}{note}")
    lines.append("")
    lines.append("=== environment ===")
    lines.append(f"gt_root           {env.gt_root} (initialized={str(env.gt_initialized).lower()})")
    lines.append(f"rigs_count        {env.rigs_count}")
    lines.append(f"vault_root        {env.vault_root}")
    lines.append(f"concierge_config  source={env.concierge_config_source} present={str(env.concierge_config_present).lower()}")
    lines.append(f"mcp_obsidian      present={str(env.mcp_obsidian_present).lower()}")
    lines.append(f"rtk_hook          installed={str(env.rtk_hook_installed).lower()}")
    return "\n".join(lines)


def run_upgrades(tools: list[ToolResult]) -> int:
    rc = 0
    for t in tools:
        if t.status != "outdated" or not t.upgrade_cmd:
            continue
        print(f"UPGRADE {t.name}: {' '.join(t.upgrade_cmd)}")
        code, out = run(t.upgrade_cmd, timeout=300)
        if code != 0:
            print(f"ERROR upgrade failed for {t.name}: {out}", file=sys.stderr)
            rc = max(rc, 1)
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit concierge-dependent tools and environment; optionally upgrade outdated tools.")
    parser.add_argument("--upgrade", action="store_true", help="Run known upgrade commands for outdated tools.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of the text report.")
    args = parser.parse_args()

    tools = [
        check_gt(),
        check_gt_stack(),
        check_graphify(),
        check_rtk(),
        check_gh(),
        check_git(),
        check_python(),
    ]
    env = env_checks()

    if args.json:
        payload = {
            "tools": [
                {
                    "name": t.name,
                    "present": t.present,
                    "installed": t.installed_version,
                    "latest": t.latest_version,
                    "status": t.status,
                    "note": t.note,
                    "upgrade_cmd": t.upgrade_cmd,
                }
                for t in tools
            ],
            "env": {
                "gt_root": str(env.gt_root),
                "gt_initialized": env.gt_initialized,
                "rigs_count": env.rigs_count,
                "vault_root": str(env.vault_root),
                "concierge_config_source": env.concierge_config_source,
                "concierge_config_present": env.concierge_config_present,
                "mcp_obsidian_present": env.mcp_obsidian_present,
                "rtk_hook_installed": env.rtk_hook_installed,
            },
        }
        print(json.dumps(payload, indent=2))
    else:
        print(render(tools, env))

    if args.upgrade:
        return run_upgrades(tools)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
