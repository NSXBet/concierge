# Evals

Local-only end-to-end evaluations for concierge skills. Each scenario runs
the skill in a sandbox (temp `HOME`, `MAIN_GT_ROOT`, `MAIN_OBSIDIAN_ROOT`, and
`PATH`) with shimmed external tools, lets the agent execute bash commands
against that sandbox, and asserts on the agent's final response, the tool
call log, and the resulting filesystem state.

Scenarios are intentionally run locally for now — CI wiring is a later
concern. Running a scenario costs a small amount in Anthropic API tokens
(one short agent session per run; typically a few cents).

## Prerequisites

Homebrew Python is externally-managed, so use a local virtualenv:

```bash
python3 -m venv evals/.venv
evals/.venv/bin/pip install -r evals/requirements.txt
export ANTHROPIC_API_KEY=sk-...
```

## Run a scenario

```bash
evals/.venv/bin/python evals/fresh_vault.py
```

Exit codes:

- `0` — pass
- `1` — assertion failure
- `2` — harness error (missing API key, unexpected exception, etc.)

## Layout

- `harness.py` — sandbox setup, agent loop, bash execution, call-log and final-text helpers.
- `shims/` — executable stubs that replace external tools (`gt`, `gh`, `rtk`, `graphify`, `pipx`, `git`). Each shim logs every invocation to `$CONCIERGE_EVAL_CALL_LOG` and returns canned output; a few accept env-var overrides so scenarios can control what a tool reports (see the shim sources).
- `<scenario>.py` — one file per scenario. Each is standalone and runnable.

## Adding a scenario

Copy `fresh_vault.py`, change the sandbox setup, the user prompt, and the
assertions. Keep assertions to substring or regex checks against the final
response — exact-match on model output is flaky.
