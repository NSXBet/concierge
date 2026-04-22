"""Eval harness for concierge skills.

Each scenario builds a `Sandbox`, calls `run_agent` with the skill name and
user prompt, then inspects `final_text(messages)`, `call_log(sandbox)`, and
the filesystem under `sandbox.root` to make assertions.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from anthropic import Anthropic
except ImportError as exc:
    raise SystemExit(
        "evals require `pip install -r evals/requirements.txt`"
    ) from exc


MODEL = "claude-sonnet-4-6"
MAX_TURNS = 25
MAX_TOKENS = 4096
BASH_TIMEOUT = 60

REPO_ROOT = Path(__file__).resolve().parent.parent
EVALS_DIR = Path(__file__).resolve().parent
SHIMS_DIR = EVALS_DIR / "shims"


BASH_TOOL = {
    "name": "bash",
    "description": "Run a bash command. Returns combined stdout and stderr.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute.",
            }
        },
        "required": ["command"],
    },
}


@dataclass
class Sandbox:
    root: Path
    home: Path
    gt_root: Path
    vault_root: Path
    call_log_path: Path
    agent_log_path: Path
    env: dict[str, str]


def make_sandbox(extra_env: dict[str, str] | None = None) -> Sandbox:
    """Create a fresh sandbox directory with stubbed HOME and env vars.

    The scenario is responsible for pre-populating the sandbox (writing a
    concierge config, cloning fake repos, etc.) before calling `run_agent`.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set")

    root = Path(tempfile.mkdtemp(prefix="concierge-eval-"))
    home = root / "home"
    (home / ".claude").mkdir(parents=True)
    gt_root = root / "gt"
    vault_root = root / "vault"
    vault_root.mkdir()
    call_log_path = root / "calls.log"
    call_log_path.touch()
    agent_log_path = root / "agent_commands.log"
    agent_log_path.touch()

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["MAIN_GT_ROOT"] = str(gt_root)
    env["MAIN_OBSIDIAN_ROOT"] = str(vault_root)
    env["PATH"] = f"{SHIMS_DIR}:{env['PATH']}"
    env["CONCIERGE_EVAL_CALL_LOG"] = str(call_log_path)
    env.pop("CONCIERGE_CONFIG", None)
    env.pop("GT_TOWN_ROOT", None)
    env.pop("OBSIDIAN_VAULT", None)

    if extra_env:
        env.update(extra_env)

    return Sandbox(
        root=root,
        home=home,
        gt_root=gt_root,
        vault_root=vault_root,
        call_log_path=call_log_path,
        agent_log_path=agent_log_path,
        env=env,
    )


def _load_skill_md(skill_name: str) -> str:
    return (REPO_ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")


def _build_system_prompt(skill_name: str) -> str:
    skill = _load_skill_md(skill_name)
    return (
        f"You are running the /concierge:{skill_name} skill in an evaluation "
        f"harness. Follow the skill instructions exactly as written below.\n\n"
        f"Your shell's current working directory is the plugin root: "
        f"{REPO_ROOT}. Scripts referenced in the skill as `scripts/<name>` "
        f"are located at `skills/{skill_name}/scripts/<name>` relative to "
        f"that root — invoke them with that path.\n\n"
        f"You have ONE tool: `bash`. Use it for every action the skill "
        f"instructs you to take. Keep your responses concise. When the "
        f"skill calls for asking the user a question, ask it and stop — "
        f"do not guess values the user must provide.\n\n"
        f"--- BEGIN SKILL.md ---\n{skill}\n--- END SKILL.md ---\n"
    )


def run_agent(
    user_prompt: str,
    skill_name: str,
    sandbox: Sandbox,
    max_turns: int = MAX_TURNS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run the agent loop until end_turn or max_turns.

    Returns (transcript, messages) where messages is the full conversation
    (suitable for passing to `final_text`).
    """
    client = Anthropic()
    system = _build_system_prompt(skill_name)
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    transcript: list[dict[str, Any]] = []

    for turn in range(max_turns):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=[BASH_TOOL],
            messages=messages,
        )
        transcript.append(
            {
                "turn": turn,
                "stop_reason": response.stop_reason,
                "content": [
                    {"type": b.type, **({"text": b.text} if b.type == "text" else {"name": b.name, "input": b.input})}
                    for b in response.content
                ],
            }
        )

        assistant_content: list[Any] = []
        tool_results: list[dict[str, Any]] = []
        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
                if block.name == "bash":
                    cmd = str(block.input.get("command", ""))
                    output = _run_bash(cmd, sandbox)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": output,
                        }
                    )
        if assistant_content:
            messages.append({"role": "assistant", "content": assistant_content})

        if response.stop_reason == "end_turn" or not tool_results:
            break
        messages.append({"role": "user", "content": tool_results})

    return transcript, messages


def _run_bash(command: str, sandbox: Sandbox) -> str:
    try:
        with sandbox.agent_log_path.open("a", encoding="utf-8") as f:
            f.write(command.replace("\n", " \\n ") + "\n")
    except OSError:
        pass
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(REPO_ROOT),
            env=sandbox.env,
            capture_output=True,
            text=True,
            timeout=BASH_TIMEOUT,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return output[:8000] if output else f"(exit={proc.returncode}, no output)"
    except subprocess.TimeoutExpired:
        return f"TIMEOUT after {BASH_TIMEOUT}s"


def final_text(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg["role"] != "assistant":
            continue
        chunks: list[str] = []
        for block in msg["content"]:
            if isinstance(block, dict) and block.get("type") == "text":
                chunks.append(block["text"])
        if chunks:
            return "\n".join(chunks)
    return ""


def call_log(sandbox: Sandbox) -> list[str]:
    if not sandbox.call_log_path.exists():
        return []
    return [
        line.strip()
        for line in sandbox.call_log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def agent_commands(sandbox: Sandbox) -> list[str]:
    """Commands the agent itself ran via the Bash tool (outermost layer)."""
    if not sandbox.agent_log_path.exists():
        return []
    return [
        line.strip()
        for line in sandbox.agent_log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def cleanup(sandbox: Sandbox) -> None:
    shutil.rmtree(sandbox.root, ignore_errors=True)


def report(name: str, failures: list[str]) -> int:
    if not failures:
        print(f"PASS {name}")
        return 0
    print(f"FAIL {name}")
    for f in failures:
        print(f"  - {f}")
    return 1


def seed_git_repo(path: Path, remote_url: str) -> None:
    """Create a valid git repo at `path` with `origin` set to `remote_url`.

    Uses the real `git` binary (not the shim) so origin is actually set.
    """
    path.mkdir(parents=True, exist_ok=True)
    real_git_env = os.environ.copy()
    real_git_env.pop("CONCIERGE_EVAL_CALL_LOG", None)
    subprocess.run(
        ["git", "init", "--quiet", str(path)],
        check=True,
        env=real_git_env,
    )
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", "origin", remote_url],
        check=True,
        env=real_git_env,
    )


def seed_gt_root(gt_root: Path, rigs: list[str] | None = None) -> None:
    """Create a fake initialized GT root with optional rig stubs."""
    (gt_root / "mayor").mkdir(parents=True, exist_ok=True)
    (gt_root / ".beads").mkdir(exist_ok=True)
    for rig in rigs or []:
        (gt_root / rig / "mayor" / "rig").mkdir(parents=True, exist_ok=True)
        (gt_root / rig / "config.json").write_text("{}\n", encoding="utf-8")


def write_concierge_config(sandbox: Sandbox, config: dict[str, Any]) -> Path:
    """Write `~/.concierge.json` inside the sandbox and return its path."""
    path = sandbox.home / ".concierge.json"
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path


def audit_happened(
    calls: list[str], commands: list[str] | None = None
) -> tuple[bool, bool]:
    """Return (audit_happened, script_was_used).

    `calls` is the shim call log — it includes tool invocations made both
    by the agent directly AND by scripts the agent ran (because the script
    also goes through the shims). That means the shim log alone cannot tell
    you whether audit_env.py was the caller.

    `commands` is the agent's own Bash-tool command list (from
    `agent_commands(sandbox)`). Check that to tell direct use of the script
    apart from inline re-implementation.
    """
    audit_signals = sum(
        1
        for c in calls
        if c.startswith(("gh release view", "gt --version", "rtk --version", "pipx list"))
    )
    script_used = False
    if commands is not None:
        script_used = any("audit_env.py" in c for c in commands)
    return (audit_signals >= 3 or script_used), script_used


def get_origin(path: Path) -> str | None:
    """Read the origin remote URL from a git repo without triggering shims."""
    real_git_env = os.environ.copy()
    real_git_env.pop("CONCIERGE_EVAL_CALL_LOG", None)
    proc = subprocess.run(
        ["git", "-C", str(path), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        env=real_git_env,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()
