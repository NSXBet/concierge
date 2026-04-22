#!/usr/bin/env python3
"""Scenario: vault repo exists but its `origin` does not match the config.

Expected behavior:
  - Audit runs.
  - Bootstrap verification fails loudly with the mismatch; no destructive
    action is taken.
  - Final response names the mismatch so the user can resolve it manually.
  - The existing repo's origin remains unchanged.
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
    get_origin,
    make_sandbox,
    report,
    run_agent,
    seed_git_repo,
    seed_gt_root,
    write_concierge_config,
)


NAME = "wrong_remote"

EXPECTED_USER = "git@github.com:acme/obsidian-user-test.git"
ACTUAL_USER = "git@github.com:acme/obsidian-user-WRONG.git"


def run() -> int:
    sandbox = make_sandbox()
    write_concierge_config(sandbox, {"user": EXPECTED_USER})
    seed_gt_root(sandbox.gt_root, rigs=["shop"])
    seed_git_repo(sandbox.vault_root / "User", ACTUAL_USER)

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
    # Remote must not have changed.
    origin = get_origin(sandbox.vault_root / "User")
    if origin != ACTUAL_USER:
        failures.append(f"User/ origin was mutated: {origin!r}")
    # No clones allowed when there's a conflict.
    clones = [c for c in calls if c.startswith("git ") and "clone" in c]
    if clones:
        failures.append(f"unexpected git clone calls: {clones}")
    # Final response must communicate the conflict.
    conflict_words = ["mismatch", "expected", "origin", "does not match", "wrong", "conflict", "different"]
    if not any(kw in text for kw in conflict_words):
        failures.append(
            f"final response does not name the origin mismatch. Full text:\n{text_raw}"
        )

    if ran_audit and not script_used:
        print(f"NOTE {NAME}: audit happened inline rather than via audit_env.py.")

    exit_code = report(NAME, failures)
    cleanup(sandbox)
    return exit_code


if __name__ == "__main__":
    sys.exit(run())
