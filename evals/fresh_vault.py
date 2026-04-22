#!/usr/bin/env python3
"""Scenario: empty machine — no concierge config, no GT root, empty vault.

Expected behavior when the user runs `/concierge:setup`:
  - The agent invokes `skills/setup/scripts/audit_env.py`.
  - The audit surfaces that the concierge config is missing.
  - The agent enters the first-run flow and asks the user for their `user:`
    repo URL.
  - The agent does NOT clone anything and does NOT write `~/.concierge.json`
    before the user provides values.
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
)


NAME = "fresh_vault"


def run() -> int:
    sandbox = make_sandbox()
    try:
        _, messages = run_agent(
            user_prompt="/concierge:setup",
            skill_name="setup",
            sandbox=sandbox,
        )
    except Exception as exc:  # harness error; not a scenario failure
        print(f"HARNESS_ERROR {NAME}: {exc}")
        cleanup(sandbox)
        return 2

    text_raw = final_text(messages)
    text = text_raw.lower()
    calls = call_log(sandbox)
    commands = agent_commands(sandbox)
    ran_audit, script_used = audit_happened(calls, commands)

    clones = [c for c in calls if c.startswith("git ") and "clone" in c]
    config_written = (sandbox.home / ".concierge.json").exists()

    asked_for_config = any(
        kw in text
        for kw in ["user:", "user repo", "concierge config", "repo url", ".concierge.json"]
    )

    failures: list[str] = []
    if not ran_audit:
        failures.append(f"no audit signals seen. Calls: {calls}")
    if clones:
        failures.append(f"unexpected git clone calls: {clones}")
    if config_written:
        failures.append("~/.concierge.json was written before the user provided values")
    if not asked_for_config:
        failures.append(
            f"final response does not ask for concierge config. Full text:\n{text_raw}"
        )

    if not script_used and ran_audit:
        print(
            f"NOTE {NAME}: audit happened inline rather than via audit_env.py. "
            f"Agent commands: {commands}"
        )

    exit_code = report(NAME, failures)
    cleanup(sandbox)
    return exit_code


if __name__ == "__main__":
    sys.exit(run())
