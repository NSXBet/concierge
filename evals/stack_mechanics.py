#!/usr/bin/env python3
"""Layer-1 mechanics tests for bin/gt-stack.

These exercise the helper directly in temp git repos — no Claude agent
involved. They cover the invariants the helper must uphold regardless
of how the concierge skills invoke it:

  - new: creates branch, records parent
  - list/parent/children: reports the recorded chain
  - restack: cascades after amend of a middle branch
  - restack: cascades after trunk advances
  - restack: is idempotent (second run is a no-op)
  - one-commit-per-branch invariant holds after cascade
  - sync: reparents descendants onto next non-merged ancestor
  - sync --prune: removes merged local branches
  - submit: creates PR with correct base; updates base on second call

`gh` is stubbed via a minimal Python script that mutates a JSON PR
ledger on disk. The stub supports the exact subcommands gt-stack
issues: `pr list --head <b> --state <s> --json ...`, `pr create`,
`pr edit --base`, and `pr ready [--undo]`.

Exit codes match the harness convention: 0 pass, 1 fail, 2 error.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
GT_STACK = REPO_ROOT / "bin" / "gt-stack"
NAME = "stack_mechanics"


# --- gh stub -----------------------------------------------------------------

GH_STUB_SOURCE = r"""#!/usr/bin/env python3
# Minimal gh stub for gt-stack mechanics tests.
# Ledger path: $GT_STACK_TEST_GH_LEDGER (JSON { "prs": [...] }).
import json
import os
import sys
from pathlib import Path

ledger_path = Path(os.environ["GT_STACK_TEST_GH_LEDGER"])
if not ledger_path.exists():
    ledger_path.write_text('{"prs": []}', encoding="utf-8")
data = json.loads(ledger_path.read_text(encoding="utf-8"))
prs = data["prs"]


def save():
    ledger_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


KNOWN_VALUE_FLAGS = {"--head", "--base", "--state", "--json", "-q", "--jq", "--repo"}
KNOWN_BOOL_FLAGS = {"--draft", "--fill", "--undo"}


def parse_flags(argv):
    out = {}
    i = 0
    positional = []
    while i < len(argv):
        a = argv[i]
        if a in KNOWN_BOOL_FLAGS:
            out[a] = True
            i += 1
        elif a in KNOWN_VALUE_FLAGS:
            if i + 1 >= len(argv):
                sys.exit(f"gh-stub: {a} expects a value")
            out[a] = argv[i + 1]
            i += 2
        elif a.startswith("-"):
            # Unknown flag: treat as positional so tests surface the mismatch.
            positional.append(a)
            i += 1
        else:
            positional.append(a)
            i += 1
    return out, positional


args = sys.argv[1:]
if not args:
    sys.exit(0)

if args[0] == "pr":
    sub = args[1] if len(args) > 1 else ""
    rest = args[2:]
    flags, positional = parse_flags(rest)

    if sub == "list":
        head = flags.get("--head")
        state = flags.get("--state")
        jq = flags.get("-q") or flags.get("--jq")
        wanted = []
        for pr in prs:
            if head and pr["head"] != head:
                continue
            if state and pr["state"].upper() != state.upper():
                continue
            wanted.append(pr)
        if jq == ".[0].number":
            print(wanted[0]["number"] if wanted else "")
        elif jq == ".[0].state":
            print(wanted[0]["state"] if wanted else "")
        else:
            print(json.dumps(wanted))
        sys.exit(0)

    if sub == "create":
        head = flags.get("--head")
        base = flags.get("--base")
        draft = "--draft" in flags
        if not head:
            sys.exit("pr create: --head required")
        nxt = max([p["number"] for p in prs] + [100]) + 1
        new_pr = {
            "number": nxt,
            "head": head,
            "base": base or "main",
            "state": "OPEN",
            "draft": bool(draft),
        }
        prs.append(new_pr)
        save()
        print(f"https://github.com/stub/repo/pull/{nxt}")
        sys.exit(0)

    if sub == "edit":
        pr_number = int(positional[0])
        new_base = flags.get("--base")
        for pr in prs:
            if pr["number"] == pr_number:
                if new_base:
                    pr["base"] = new_base
                save()
                sys.exit(0)
        sys.exit(f"pr edit: #{pr_number} not found")

    if sub == "ready":
        pr_number = int(positional[0])
        undo = "--undo" in flags
        for pr in prs:
            if pr["number"] == pr_number:
                pr["draft"] = bool(undo)  # --undo sets back to draft
                save()
                sys.exit(0)
        sys.exit(f"pr ready: #{pr_number} not found")

sys.exit(f"gh-stub: unhandled args: {args}")
"""


# --- test helpers ------------------------------------------------------------


def real_env() -> dict:
    """Env with no CONCIERGE_EVAL_CALL_LOG so git/gh don't route through shims."""
    env = os.environ.copy()
    env.pop("CONCIERGE_EVAL_CALL_LOG", None)
    return env


class TestRepo:
    """A disposable git repo with a gh stub in PATH and a PR ledger."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="gt-stack-test-"))
        self.repo = self.root / "repo"
        self.bin = self.root / "bin"
        self.ledger = self.root / "gh-ledger.json"
        self.bin.mkdir()
        self.repo.mkdir()

        gh_path = self.bin / "gh"
        gh_path.write_text(GH_STUB_SOURCE, encoding="utf-8")
        gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        self.env = real_env()
        self.env["PATH"] = f"{self.bin}:{self.env['PATH']}"
        self.env["GT_STACK_TEST_GH_LEDGER"] = str(self.ledger)
        self.env["GIT_AUTHOR_NAME"] = "test"
        self.env["GIT_AUTHOR_EMAIL"] = "t@t"
        self.env["GIT_COMMITTER_NAME"] = "test"
        self.env["GIT_COMMITTER_EMAIL"] = "t@t"

        self._git("init", "-q", "-b", "main")
        self._git("commit", "--allow-empty", "-q", "-m", "root")

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _git(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=str(self.repo),
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
        )

    def git(self, *args) -> str:
        return self._git(*args).stdout.strip()

    def gt_stack(self, *args, check: bool = True) -> subprocess.CompletedProcess:
        proc = subprocess.run(
            [str(GT_STACK), *args],
            cwd=str(self.repo),
            env=self.env,
            capture_output=True,
            text=True,
        )
        if check and proc.returncode != 0:
            raise AssertionError(
                f"gt-stack {' '.join(args)} failed (rc={proc.returncode}):\n"
                f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
            )
        return proc

    def commit(self, message: str):
        self._git("commit", "--allow-empty", "-q", "-m", message)

    def amend(self, message: str):
        self._git("commit", "--amend", "--allow-empty", "-m", message)

    def checkout(self, branch: str):
        self._git("checkout", "-q", branch)

    def rev(self, ref: str) -> str:
        return self.git("rev-parse", ref)

    def log_oneline(self, branch: str) -> list[str]:
        out = self.git("log", "--oneline", branch)
        return out.splitlines()

    def parents_file(self) -> dict[str, str]:
        path = self.repo / ".git" / "gt-stack" / "parents"
        if not path.exists():
            return {}
        result = {}
        for line in path.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                result[k.strip()] = v.strip()
        return result

    def add_pr(self, *, number: int, head: str, base: str, state: str = "OPEN", draft: bool = False):
        if not self.ledger.exists():
            self.ledger.write_text('{"prs": []}')
        data = json.loads(self.ledger.read_text())
        data["prs"].append({
            "number": number,
            "head": head,
            "base": base,
            "state": state,
            "draft": draft,
        })
        self.ledger.write_text(json.dumps(data, indent=2))

    def pr_ledger(self) -> list[dict]:
        if not self.ledger.exists():
            return []
        return json.loads(self.ledger.read_text())["prs"]


# --- tests -------------------------------------------------------------------

FAILURES: list[str] = []


def fail(msg: str):
    FAILURES.append(msg)


def assert_eq(actual, expected, label: str):
    if actual != expected:
        fail(f"{label}: expected {expected!r}, got {actual!r}")


def assert_contains(haystack, needle, label: str):
    if needle not in haystack:
        fail(f"{label}: {needle!r} not in {haystack!r}")


def assert_single_commit_invariant(repo: TestRepo, branch: str, parent: str):
    parent_tip = repo.rev(parent)
    branch_parent = repo.rev(f"{branch}^")
    if branch_parent != parent_tip:
        fail(
            f"single-commit invariant broken for {branch}: "
            f"{branch}^ = {branch_parent} but {parent} tip = {parent_tip}"
        )


def test_new_records_parent():
    repo = TestRepo()
    try:
        repo.gt_stack("new", "feature-a")
        assert_eq(repo.parents_file().get("feature-a"), "main", "feature-a parent")
        repo.commit("A")
        repo.gt_stack("new", "feature-b")
        assert_eq(repo.parents_file().get("feature-b"), "feature-a", "feature-b parent")
    finally:
        repo.close()


def test_new_with_explicit_base():
    repo = TestRepo()
    try:
        repo.gt_stack("new", "feature-a")
        repo.commit("A")
        repo.gt_stack("new", "feature-b", "--base", "main")
        assert_eq(repo.parents_file().get("feature-b"), "main", "feature-b parent (--base main)")
    finally:
        repo.close()


def test_new_rejects_existing_branch():
    repo = TestRepo()
    try:
        repo.gt_stack("new", "feature-a")
        proc = repo.gt_stack("new", "feature-a", check=False)
        if proc.returncode == 0:
            fail("expected gt-stack new to refuse a duplicate branch name")
    finally:
        repo.close()


def test_list_shows_chain():
    repo = TestRepo()
    try:
        repo.gt_stack("new", "a")
        repo.commit("A")
        repo.gt_stack("new", "b")
        repo.commit("B")
        repo.gt_stack("new", "c")
        repo.commit("C")
        out = repo.gt_stack("list").stdout
        for name in ["main", "a", "b", "c"]:
            assert_contains(out, name, f"list output contains {name}")
    finally:
        repo.close()


def test_parent_and_children():
    repo = TestRepo()
    try:
        repo.gt_stack("new", "a")
        repo.commit("A")
        repo.gt_stack("new", "b")
        repo.commit("B")
        assert_eq(repo.gt_stack("parent", "b").stdout.strip(), "a", "parent of b")
        assert_eq(repo.gt_stack("children", "a").stdout.strip(), "b", "children of a")
        assert_eq(repo.gt_stack("parent", "a").stdout.strip(), "main", "parent of a")
    finally:
        repo.close()


def test_restack_cascades_after_amend():
    repo = TestRepo()
    try:
        repo.gt_stack("new", "a")
        repo.commit("A")
        repo.gt_stack("new", "b")
        repo.commit("B")
        repo.gt_stack("new", "c")
        repo.commit("C")

        repo.checkout("b")
        repo.amend("B-amended")
        repo.gt_stack("restack", "b")

        assert_single_commit_invariant(repo, "b", "a")
        assert_single_commit_invariant(repo, "c", "b")

        c_log = repo.log_oneline("c")
        # c should have exactly: C, B-amended, A, root
        if len(c_log) != 4:
            fail(f"c should have 4 commits after cascade, got {len(c_log)}:\n{c_log}")
        if c_log and "C" not in c_log[0]:
            fail(f"top of c should be C, got {c_log[0]}")
        if len(c_log) > 1 and "B-amended" not in c_log[1]:
            fail(f"second commit on c should be B-amended, got {c_log[1]}")
    finally:
        repo.close()


def test_restack_cascades_after_trunk_advance():
    repo = TestRepo()
    try:
        repo.gt_stack("new", "a")
        repo.commit("A")
        repo.gt_stack("new", "b")
        repo.commit("B")
        repo.gt_stack("new", "c")
        repo.commit("C")

        repo.checkout("main")
        repo.commit("trunk-advance")
        repo.gt_stack("restack", "a")

        assert_single_commit_invariant(repo, "a", "main")
        assert_single_commit_invariant(repo, "b", "a")
        assert_single_commit_invariant(repo, "c", "b")

        c_log = repo.log_oneline("c")
        # c should now have 5 commits: C, B, A, trunk-advance, root
        if len(c_log) != 5:
            fail(f"c should have 5 commits after trunk-advance restack, got {len(c_log)}:\n{c_log}")
        if c_log and "trunk-advance" not in "\n".join(c_log):
            fail("trunk-advance commit not in c's history after restack")
    finally:
        repo.close()


def test_restack_idempotent():
    repo = TestRepo()
    try:
        repo.gt_stack("new", "a")
        repo.commit("A")
        repo.gt_stack("new", "b")
        repo.commit("B")
        repo.gt_stack("new", "c")
        repo.commit("C")

        before = {b: repo.rev(b) for b in ["a", "b", "c"]}
        # First restack of an already-consistent stack should be a no-op.
        repo.gt_stack("restack", "a")
        after = {b: repo.rev(b) for b in ["a", "b", "c"]}
        if before != after:
            fail(f"restack mutated already-consistent stack: before={before} after={after}")
    finally:
        repo.close()


def test_submit_creates_pr_with_parent_as_base():
    repo = TestRepo()
    try:
        # Simulate a remote by adding origin pointing at a local bare repo
        bare = repo.root / "origin.git"
        subprocess.run(["git", "init", "--bare", "-q", str(bare)], env=repo.env, check=True)
        repo._git("remote", "add", "origin", str(bare))

        repo.gt_stack("new", "a")
        repo.commit("A")
        repo.gt_stack("new", "b")
        repo.commit("B")
        repo.gt_stack("submit")
        prs = repo.pr_ledger()
        b_prs = [p for p in prs if p["head"] == "b"]
        if len(b_prs) != 1:
            fail(f"expected exactly one PR for b, got {b_prs}")
        elif b_prs[0]["base"] != "a":
            fail(f"PR for b should have base=a, got base={b_prs[0]['base']!r}")
    finally:
        repo.close()


def test_submit_updates_existing_pr_base():
    repo = TestRepo()
    try:
        bare = repo.root / "origin.git"
        subprocess.run(["git", "init", "--bare", "-q", str(bare)], env=repo.env, check=True)
        repo._git("remote", "add", "origin", str(bare))

        repo.gt_stack("new", "a")
        repo.commit("A")
        repo.gt_stack("new", "b")
        repo.commit("B")
        repo.gt_stack("submit")  # creates PR for b with base=a

        # Pretend the user (or sync) changed b's parent to main.
        parents = repo.repo / ".git" / "gt-stack" / "parents"
        content = parents.read_text().replace("b=a", "b=main")
        parents.write_text(content)

        repo.gt_stack("submit")  # should update existing PR's base to main
        prs = [p for p in repo.pr_ledger() if p["head"] == "b"]
        if not prs or prs[0]["base"] != "main":
            fail(f"PR for b should have base updated to main, got {prs}")
    finally:
        repo.close()


def test_sync_reparents_descendants():
    repo = TestRepo()
    try:
        bare = repo.root / "origin.git"
        subprocess.run(["git", "init", "--bare", "-q", str(bare)], env=repo.env, check=True)
        repo._git("remote", "add", "origin", str(bare))

        repo.gt_stack("new", "a")
        repo.commit("A")
        repo.gt_stack("new", "b")
        repo.commit("B")
        repo.gt_stack("new", "c")
        repo.commit("C")
        repo._git("push", "-q", "origin", "a", "b", "c", "main")

        # Record PRs in the ledger — a is merged, b and c are open.
        repo.add_pr(number=1, head="a", base="main", state="MERGED")
        repo.add_pr(number=2, head="b", base="a", state="OPEN", draft=False)
        repo.add_pr(number=3, head="c", base="b", state="OPEN", draft=True)

        # Simulate a's merge landing on main.
        repo.checkout("main")
        repo._git("merge", "--no-ff", "-q", "a", "-m", "merge a")
        repo._git("push", "-q", "origin", "main")

        repo.gt_stack("sync")
        parents = repo.parents_file()
        assert_eq(parents.get("b"), "main", "b's parent after sync")
        assert_eq(parents.get("c"), "b", "c's parent after sync (unchanged)")
        if "a" in parents:
            fail(f"a should be dropped from parents file after merge, still present: {parents}")
    finally:
        repo.close()


def test_sync_prune_deletes_merged_local_branches():
    repo = TestRepo()
    try:
        bare = repo.root / "origin.git"
        subprocess.run(["git", "init", "--bare", "-q", str(bare)], env=repo.env, check=True)
        repo._git("remote", "add", "origin", str(bare))

        repo.gt_stack("new", "a")
        repo.commit("A")
        repo.gt_stack("new", "b")
        repo.commit("B")
        repo._git("push", "-q", "origin", "a", "b", "main")

        repo.add_pr(number=1, head="a", base="main", state="MERGED")
        repo.add_pr(number=2, head="b", base="a", state="OPEN", draft=False)

        repo.checkout("main")
        repo._git("merge", "--no-ff", "-q", "a", "-m", "merge a")
        repo._git("push", "-q", "origin", "main")

        repo.gt_stack("sync", "--prune")

        branches = repo.git("branch", "--list").splitlines()
        branch_names = [b.strip("* ") for b in branches]
        if "a" in branch_names:
            fail(f"--prune did not delete local branch a. branches: {branch_names}")
        if "b" not in branch_names:
            fail(f"--prune wrongly deleted b. branches: {branch_names}")
    finally:
        repo.close()


def test_sync_without_merges_is_noop():
    repo = TestRepo()
    try:
        bare = repo.root / "origin.git"
        subprocess.run(["git", "init", "--bare", "-q", str(bare)], env=repo.env, check=True)
        repo._git("remote", "add", "origin", str(bare))

        repo.gt_stack("new", "a")
        repo.commit("A")
        repo.gt_stack("new", "b")
        repo.commit("B")
        repo._git("push", "-q", "origin", "a", "b", "main")

        repo.add_pr(number=1, head="a", base="main", state="OPEN", draft=False)
        repo.add_pr(number=2, head="b", base="a", state="OPEN", draft=False)

        before_parents = repo.parents_file()
        before_sha = {"a": repo.rev("a"), "b": repo.rev("b")}

        repo.gt_stack("sync")

        after_parents = repo.parents_file()
        after_sha = {"a": repo.rev("a"), "b": repo.rev("b")}
        if before_parents != after_parents:
            fail(f"sync mutated parents without merges: {before_parents} -> {after_parents}")
        if before_sha != after_sha:
            fail(f"sync mutated SHAs without merges: {before_sha} -> {after_sha}")
    finally:
        repo.close()


def test_submit_draft_vs_ready():
    repo = TestRepo()
    try:
        bare = repo.root / "origin.git"
        subprocess.run(["git", "init", "--bare", "-q", str(bare)], env=repo.env, check=True)
        repo._git("remote", "add", "origin", str(bare))

        repo.gt_stack("new", "a")
        repo.commit("A")
        repo.gt_stack("submit", "--draft")
        prs = [p for p in repo.pr_ledger() if p["head"] == "a"]
        if not prs or not prs[0]["draft"]:
            fail(f"expected a to be draft after --draft submit: {prs}")

        repo.gt_stack("submit")  # promote to ready
        prs = [p for p in repo.pr_ledger() if p["head"] == "a"]
        if not prs or prs[0]["draft"]:
            fail(f"expected a to be ready after plain submit: {prs}")
    finally:
        repo.close()


# --- main --------------------------------------------------------------------

TESTS = [
    test_new_records_parent,
    test_new_with_explicit_base,
    test_new_rejects_existing_branch,
    test_list_shows_chain,
    test_parent_and_children,
    test_restack_cascades_after_amend,
    test_restack_cascades_after_trunk_advance,
    test_restack_idempotent,
    test_submit_creates_pr_with_parent_as_base,
    test_submit_updates_existing_pr_base,
    test_sync_reparents_descendants,
    test_sync_prune_deletes_merged_local_branches,
    test_sync_without_merges_is_noop,
    test_submit_draft_vs_ready,
]


def run() -> int:
    if not GT_STACK.exists():
        print(f"HARNESS_ERROR {NAME}: {GT_STACK} not found")
        return 2
    global FAILURES
    passed = 0
    tests_failed = 0
    for t in TESTS:
        FAILURES = []
        try:
            t()
        except AssertionError as exc:
            FAILURES.append(str(exc))
        except Exception as exc:
            print(f"ERROR {t.__name__}: {type(exc).__name__}: {exc}")
            tests_failed += 1
            continue
        if FAILURES:
            tests_failed += 1
            print(f"FAIL {t.__name__}")
            for f in FAILURES:
                print(f"  - {f}")
        else:
            passed += 1

    total = len(TESTS)
    print(f"{NAME}: {passed}/{total} tests passed")
    if tests_failed == 0:
        print(f"PASS {NAME}")
        return 0
    print(f"FAIL {NAME}")
    return 1


if __name__ == "__main__":
    sys.exit(run())
