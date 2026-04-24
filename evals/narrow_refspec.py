#!/usr/bin/env python3
"""Scenario: a rig canonical clone still has the narrow `main`-only refspec
shipped by `gt rig add`. Running `/concierge:setup upgrade` should detect
and widen it.

Expected behavior:
  - The agent invokes `skills/setup/scripts/audit_env.py` with `--upgrade`.
  - Audit surfaces the rig under `narrow_refspec_rigs`.
  - The refspec on disk becomes the standard wildcard form.

The scenario seeds a real git repo under the rig's `mayor/rig` folder with
an unreachable `origin` — the widen script's `git fetch` step will fail,
but the preceding `git config` step still applies, so the refspec on disk
flips to wildcard and the scenario can assert that.
"""
from __future__ import annotations

import json
import subprocess
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
    read_rig_refspec,
    report,
    run_agent,
    seed_gt_root,
    seed_rig_clone,
    write_concierge_config,
)


NAME = "narrow_refspec"
RIG = "example_rig"
WILDCARD = "+refs/heads/*:refs/remotes/origin/*"
NARROW = "+refs/heads/main:refs/remotes/origin/main"
REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_SCRIPT = REPO_ROOT / "skills" / "setup" / "scripts" / "audit_env.py"


def _audit_narrow_rigs(sandbox) -> tuple[list[str], str]:
    """Run audit_env.py --json in the sandbox and return the narrow-refspec
    list plus the full stdout for debugging. Surfaces audit-contract
    regressions independently of the agent's behavior.
    """
    proc = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT), "--json"],
        env=sandbox.env,
        capture_output=True,
        text=True,
    )
    stdout = proc.stdout or ""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return [], stdout
    return list(payload.get("env", {}).get("narrow_refspec_rigs", [])), stdout


def run() -> int:
    sandbox = make_sandbox()
    failures: list[str] = []
    try:
        seed_gt_root(sandbox.gt_root, rigs=[RIG])
        clone = seed_rig_clone(
            sandbox.gt_root,
            RIG,
            remote_url="git@example.invalid:org/example.git",
            refspec=NARROW,
        )
        # Pre-populate a concierge config so the vault flow does not derail
        # the upgrade path with a first-run prompt.
        write_concierge_config(
            sandbox,
            {
                "user": "git@example.invalid:org/user.git",
                "shared": {},
            },
        )

        # Pre-check: audit must surface the seeded rig under
        # `narrow_refspec_rigs`. Runs before the agent so we assert the
        # audit contract independently of whatever widening path the
        # agent picks.
        pre_narrow, pre_stdout = _audit_narrow_rigs(sandbox)
        if RIG not in pre_narrow:
            failures.append(
                "audit --json did not report "
                f"{RIG!r} under env.narrow_refspec_rigs. "
                f"Got: {pre_narrow}. Raw stdout: {pre_stdout[:500]!r}"
            )

        _, messages = run_agent(
            user_prompt="/concierge:setup upgrade",
            skill_name="setup",
            sandbox=sandbox,
        )

        text_raw = final_text(messages)
        commands = agent_commands(sandbox)
        calls = call_log(sandbox)
        ran_audit, _ = audit_happened(calls, commands)

        refspec_after = read_rig_refspec(clone)

        widen_invoked = any(
            "widen_rig_refspec" in c for c in commands
        ) or any(
            "audit_env.py" in c and "--upgrade" in c for c in commands
        )

        mentioned_narrow = any(
            kw in text_raw.lower()
            for kw in ["refspec", "widen", "narrow"]
        )

        if not ran_audit:
            failures.append(f"no audit signals seen. Calls: {calls}")
        if not widen_invoked:
            failures.append(
                "agent did not invoke widen_rig_refspec.py or "
                f"audit_env.py --upgrade. Commands: {commands}"
            )
        if WILDCARD not in refspec_after:
            failures.append(
                f"refspec was not widened. Still: {refspec_after!r}"
            )
        if not mentioned_narrow:
            failures.append(
                "final response does not mention refspec/widen. "
                f"Full text:\n{text_raw}"
            )

        return report(NAME, failures)
    except Exception as exc:
        print(f"HARNESS_ERROR {NAME}: {exc}")
        return 2
    finally:
        cleanup(sandbox)


if __name__ == "__main__":
    sys.exit(run())
