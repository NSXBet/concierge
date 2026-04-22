"""Eval harness for concierge skills.

Each scenario builds a `Sandbox`, calls `run_agent` with the skill name and
user prompt, then inspects `final_text(messages)`, `call_log(sandbox)`, and
the filesystem under `sandbox.root` to make assertions.
"""
from __future__ import annotations

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
