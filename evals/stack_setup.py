#!/usr/bin/env python3
"""Layer-2 scenario: /concierge:setup installs gt-stack.

Sandbox is already mostly set up (concierge config present, GT root
initialized, vault repos cloned) so the agent's only remaining gap is
that gt-stack has not been installed yet. Expected behaviour:

  - Audit runs (via audit_env.py) and reports gt-stack as missing.
  - Agent invokes `skills/setup/scripts/ensure_gt_stack.py --apply`.

We deliberately do not assert on the final filesystem state (whether
`~/.local/bin/gt-stack` actually exists after the run) because the
sandbox's effective PATH may still include a system-installed gt-stack
from the developer's real machine. Instead we assert on the agent's
own Bash-tool invocations: did the agent call the install script?
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


NAME = "stack_setup"

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
    ran_audit, _ = audit_happened(calls, commands)

    failures: list[str] = []
    if not ran_audit:
        failures.append("no audit signals seen")

    # Primary assertion: agent invoked ensure_gt_stack.py.
    ensure_calls = [c for c in commands if "ensure_gt_stack.py" in c]
    if not ensure_calls:
        failures.append(
            "agent did not invoke ensure_gt_stack.py. Commands run:\n  "
            + "\n  ".join(commands)
        )

    # Secondary signal: the final text should mention the helper being
    # installed or available.
    if "gt-stack" not in text and "gt_stack" not in text:
        failures.append(
            f"final response does not mention gt-stack. Full text:\n{final_text(messages)}"
        )

    exit_code = report(NAME, failures)
    cleanup(sandbox)
    return exit_code


if __name__ == "__main__":
    sys.exit(run())
