#!/usr/bin/env python3
"""Layer-2 scenario: /concierge:go dispatches stacked work via gt-stack.

Sandbox has:
  - Concierge config and vault repos present
  - GT root initialized with a `shop` rig
  - gt-stack shimmed on PATH (logs every invocation)

User prompt explicitly requests a stacked dispatch. We assert that the
agent invokes `gt-stack new` at least once — the skill's new A.1
section says this is the right dispatch path for stacked work.

We do NOT assert on exact verbs beyond `new`, because which of
`submit --draft` / `restack` the agent chooses depends on how much of
the flow it runs before deciding to stop and ask the user. `new` is
the unambiguous signal that the agent recognised the stacked plan and
picked up the helper.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import (
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


NAME = "stack_dispatch"

USER_REMOTE = "git@github.com:acme/obsidian-user-test.git"


def run() -> int:
    sandbox = make_sandbox()

    write_concierge_config(sandbox, {"shared": {}, "user": USER_REMOTE})
    seed_gt_root(sandbox.gt_root, rigs=["shop"])
    seed_git_repo(sandbox.vault_root / "User", USER_REMOTE)

    # Give the shop rig a real-ish repo so the agent can cd into it and run
    # gt-stack without fighting the filesystem.
    shop_repo = sandbox.gt_root / "shop" / "mayor" / "rig"
    seed_git_repo(shop_repo, "git@github.com:acme/shop.git")

    prompt = (
        "/concierge:go I want to ship three stacked PRs for the shop rig: "
        "one for the api changes (base of the stack), one for the ui on top, "
        "and one for the docs on top of the ui. The plan declares "
        "Stacking = gt-stack. Use the gt-stack helper for dispatch — start "
        "with the bottom branch."
    )

    try:
        _, messages = run_agent(
            user_prompt=prompt,
            skill_name="go",
            sandbox=sandbox,
        )
    except Exception as exc:
        print(f"HARNESS_ERROR {NAME}: {exc}")
        cleanup(sandbox)
        return 2

    from harness import agent_commands

    text = final_text(messages)
    calls = call_log(sandbox)
    commands = agent_commands(sandbox)

    failures: list[str] = []

    # Behavioral assertion: the agent must actually invoke the helper.
    # The text of the final reply is intentionally NOT asserted on — the
    # agent sometimes ends with a tool_use block and no text, which is fine
    # as long as the right tools were called.
    new_calls = [c for c in calls if c.startswith("gt-stack new")]
    if not new_calls:
        stack_calls = [c for c in calls if c.startswith("gt-stack")]
        failures.append(
            "agent did not invoke `gt-stack new`. "
            f"All gt-stack calls: {stack_calls or 'none'}\n"
            f"All shim calls (first 40):\n  " + "\n  ".join(calls[:40])
            + "\nAgent Bash commands (first 40):\n  " + "\n  ".join(commands[:40])
            + f"\nFinal text:\n{text[:2000]}"
        )
    elif not any(
        kw in text.lower()
        for kw in ["gt-stack", "stack", "bottom", "base branch", "first pr"]
    ):
        # Soft note — the agent did the behaviour but didn't narrate it.
        print(f"NOTE {NAME}: agent invoked gt-stack but final text didn't mention the stack.")

    exit_code = report(NAME, failures)
    cleanup(sandbox)
    return exit_code


if __name__ == "__main__":
    sys.exit(run())
