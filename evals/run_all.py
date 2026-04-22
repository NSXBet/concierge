#!/usr/bin/env python3
"""Run every eval scenario in this directory in parallel and report results.

Exits non-zero if any scenario fails or errors.
"""
from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


SKIP = {"harness.py", "run_all.py"}


def scenario_files() -> list[Path]:
    evals_dir = Path(__file__).resolve().parent
    return sorted(
        p for p in evals_dir.glob("*.py") if p.name not in SKIP
    )


def run_one(path: Path) -> tuple[str, int, str]:
    proc = subprocess.run(
        [sys.executable, str(path)],
        capture_output=True,
        text=True,
    )
    return path.name, proc.returncode, (proc.stdout + proc.stderr).strip()


def main() -> int:
    scenarios = scenario_files()
    if not scenarios:
        print("no scenarios found")
        return 2

    results: list[tuple[str, int, str]] = []
    with ThreadPoolExecutor(max_workers=len(scenarios)) as pool:
        futures = {pool.submit(run_one, p): p for p in scenarios}
        for fut in as_completed(futures):
            name, rc, output = fut.result()
            status = "PASS" if rc == 0 else ("FAIL" if rc == 1 else "ERROR")
            print(f"=== {name} [{status}] ===")
            print(output)
            print()
            results.append((name, rc, output))

    fails = [r for r in results if r[1] != 0]
    total = len(results)
    print(f"Summary: {total - len(fails)}/{total} passed")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
