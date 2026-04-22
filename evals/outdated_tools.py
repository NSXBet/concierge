#!/usr/bin/env python3
"""Scenario: tools are installed but behind their latest upstream release.

Expected behavior when the user runs `/concierge:setup` (without `upgrade`):
  - Audit runs.
  - Final response reports outdated tools (at least names a version or the
    word "outdated").
  - No upgrade commands run — outdated is never auto-fixed by the default
    setup action.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import (
    agent_commands,
    audit_happened,
    call_log,
    cleanup,
    final_text,
    make_sandbox,
    report,
    run_agent,
    seed_git_repo,
    seed_gt_root,
    write_concierge_config,
)


NAME = "outdated_tools"

USER_REMOTE = "git@github.com:acme/obsidian-user-test.git"


def run() -> int:
    sandbox = make_sandbox(
        extra_env={
            "CONCIERGE_EVAL_RTK_VERSION": "rtk 0.36.0",
            "CONCIERGE_EVAL_GH_VERSION": "gh version 2.90.0 (2026-04-16)",
            "CONCIERGE_EVAL_PIPX_LIST": "graphifyy 0.4.14",
        }
    )
    write_concierge_config(sandbox, {"user": USER_REMOTE})
    seed_gt_root(sandbox.gt_root, rigs=["shop"])
    seed_git_repo(sandbox.vault_root / "User", USER_REMOTE)

    try:
        _, messages = run_agent(
            user_prompt="/concierge:setup",
            skill_name="setup",
            sandbox=sandbox,
        )
    except Exception as exc:
        print(f"HARNESS_ERROR {NAME}: {exc}")
        cleanup(sandbox)
        return 2

    text_raw = final_text(messages)
    text = text_raw.lower()
    calls = call_log(sandbox)
    commands = agent_commands(sandbox)
    ran_audit, script_used = audit_happened(calls, commands)

    failures: list[str] = []
    if not ran_audit:
        failures.append(f"no audit signals seen. Calls: {calls}")
    # No upgrade commands must have been invoked.
    upgrades = [
        c
        for c in calls
        if c.startswith(("brew upgrade", "pipx upgrade"))
    ]
    if upgrades:
        failures.append(f"unexpected upgrade commands: {upgrades}")
    # Final response must communicate that tools are behind.
    outdated_words = ["outdated", "0.36", "0.4.14", "2.90", "behind", "newer version"]
    if not any(kw in text for kw in outdated_words):
        failures.append(
            f"final response does not mention outdated tools. Full text:\n{text_raw}"
        )

    if ran_audit and not script_used:
        print(f"NOTE {NAME}: audit happened inline rather than via audit_env.py.")

    exit_code = report(NAME, failures)
    cleanup(sandbox)
    return exit_code


if __name__ == "__main__":
    sys.exit(run())
