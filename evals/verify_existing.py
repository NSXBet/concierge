#!/usr/bin/env python3
"""Scenario: already-configured machine with matching remotes.

Expected behavior when the user runs `/concierge:setup`:
  - Audit runs.
  - Vault verification passes — all configured repos are present with the
    expected `origin` remote, no mutations.
  - GT is already initialized; no `gt install` is called.
  - Agent's final response indicates nothing needed to change.
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


NAME = "verify_existing"

USER_REMOTE = "git@github.com:acme/obsidian-user-test.git"
ENG_REMOTE = "git@github.com:acme/obsidian-engineering.git"


def run() -> int:
    sandbox = make_sandbox()

    write_concierge_config(
        sandbox,
        {"shared": {"Engineering": ENG_REMOTE}, "user": USER_REMOTE},
    )
    seed_gt_root(sandbox.gt_root, rigs=["shop"])
    seed_git_repo(sandbox.vault_root / "Shared" / "Engineering", ENG_REMOTE)
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

    text = final_text(messages).lower()
    calls = call_log(sandbox)
    commands = agent_commands(sandbox)
    ran_audit, script_used = audit_happened(calls, commands)

    failures: list[str] = []
    if not ran_audit:
        failures.append(f"no audit signals seen. Calls: {calls}")
    # No cloning — repos already present.
    clones = [c for c in calls if c.startswith("git ") and "clone" in c]
    if clones:
        failures.append(f"unexpected git clone calls: {clones}")
    # No GT init — GT already initialized.
    gt_installs = [c for c in calls if c.startswith("gt install")]
    if gt_installs:
        failures.append(f"unexpected gt install calls: {gt_installs}")
    # Remotes unchanged.
    user_origin = get_origin(sandbox.vault_root / "User")
    if user_origin != USER_REMOTE:
        failures.append(f"User/ origin changed: {user_origin!r}")
    eng_origin = get_origin(sandbox.vault_root / "Shared" / "Engineering")
    if eng_origin != ENG_REMOTE:
        failures.append(f"Shared/Engineering origin changed: {eng_origin!r}")
    # Report should indicate a clean / already-set-up state.
    if not any(
        kw in text
        for kw in ["no changes", "already", "up to date", "verified", "nothing to do", "all good", "in place"]
    ):
        failures.append(
            f"final response does not indicate a clean state. Full text:\n{final_text(messages)}"
        )

    if ran_audit and not script_used:
        print(f"NOTE {NAME}: audit happened inline rather than via audit_env.py.")

    exit_code = report(NAME, failures)
    cleanup(sandbox)
    return exit_code


if __name__ == "__main__":
    sys.exit(run())
