# Stacked PRs with `gt-stack`

Concierge ships a thin helper, `gt-stack`, that coordinates stacked pull
requests on GitHub. It leans on plain `git` and `gh` — the stack state
lives in `.git/gt-stack/parents` inside each repo and in the PR's base
branch on GitHub, nowhere else.

This page is the contract. Follow the three rules below and the tool
stays out of your way.

## Why stacked PRs, and why this helper

A stack lets you split a large piece of work into a chain of small,
reviewable PRs that depend on each other: PR B is based on PR A, PR C is
based on PR B, and so on. Each PR shows only its own diff, reviewers can
approve them independently, and the chain merges bottom-up.

Every stacking tool has to solve three problems:

1. Track which branch is parented on which.
2. Rebase descendants after a parent branch rewrites (amend, reorder,
   merge-into-trunk).
3. Keep the GitHub PR base-branch pointer aligned with the local parent.

Existing tools (Graphite, ghstack, spr, Sapling) solve these, but every
option carries a cost:

- **Graphite** conflicts with the `gt` CLI name used by Gastown, and
  couples you to its hosted service and PR-body metadata that conflicts
  with our "no internal identifiers in PR text" rule
  (Change-Workflow §6).
- **ghstack / spr** treat each commit on a long branch as a PR. Every
  `git commit --amend` rewrites SHAs across the whole stack, and our
  Change-Workflow §5 asks replies to be anchored by file + symbol for
  exactly that reason — but the commit-per-PR model churns in other
  ways that make the mental model harder for agents driving the stack.

`gt-stack` is deliberately thin. It knows about branches, parent
pointers, and PR base branches — nothing else. You can stop using it at
any time and nothing in git or GitHub changes.

## The three rules

### Rule 1 — One commit per branch

Every stacked branch carries **exactly one commit** ahead of its
parent. Iterate on review feedback with `git commit --amend` +
`git push --force-with-lease`, not with new commits.

Why this matters:

- `gt-stack restack` assumes the single-commit invariant to compute the
  fork point (`<branch>^`). A branch with two commits will silently
  drop the older one during a restack.
- "Fixed in `abc1234`" replies break the moment you amend — the SHA is
  gone. Anchor replies by file + symbol instead (Change-Workflow §5).
- One commit per PR keeps each PR's diff == the commit. Reviewers see
  one logical change; CodeRabbit re-reviews stay quiet.

If you realise mid-review that you need a second commit, either squash
into the existing commit (`git commit --amend`) or lift the change into
a new stacked branch on top.

### Rule 2 — Merge strictly bottom-up

The stack has an order: the branch whose base is `main` is the bottom.
Land that one first. Only once it is merged can the next branch be
merged.

Trying to merge a middle-of-stack branch will either be blocked by the
base-branch mismatch or will silently include the bottom branch's
commits in the merge commit — both bad outcomes. GitHub's "merge when
ready" and auto-merge both respect the base branch, so configuring the
bottom branch to auto-merge and letting it cascade is safe.

After a merge, run `gt-stack sync` to cascade (see Rule 3).

### Rule 3 — Restack after every amend or merge

Two events invalidate the stack:

- **Amend + force-push of a branch**: every descendant is now parented
  on a stale SHA. Run `gt-stack restack` from the amended branch — the
  helper walks its descendants and rebases each onto its new parent.
- **Merge of a stack branch into `main`**: every descendant whose
  parent was the merged branch now needs to be reparented onto `main`
  (or onto the next non-merged ancestor). Run `gt-stack sync` — the
  helper detects merged PRs via `gh`, reparents in the metadata, and
  cascades rebases bottom-up (parents first, then descendants).

After a restack or sync, run `gt-stack submit` from any branch in the
stack: with no arguments it walks the current branch + all descendants
in parent-first order, force-with-lease-pushes each one, and updates
each PR's base branch to match the recorded parent. To operate on a
single branch, pass it explicitly: `gt-stack submit <branch>`.

The `--draft` flag flips PR draft state to draft (and its absence flips
to ready) for every branch processed. For mixed-state stacks where the
bottom should be ready and descendants stay draft (the bottom-up merge
convention), use single-branch `gt-stack submit <branch>` calls so each
PR's draft state is preserved.

## Commands

| Command | What it does |
|:--|:--|
| `gt-stack new <name>` | Create `<name>` off the current branch; record parent. |
| `gt-stack list` | Show the chain from the current branch back to `main`. |
| `gt-stack parent` | Print the recorded parent of the current branch. |
| `gt-stack children` | Print branches whose parent is the current branch. |
| `gt-stack restack` | Rebase the current branch + its descendants onto their parents. |
| `gt-stack push` | Force-with-lease push (safer than `--force`). |
| `gt-stack submit [--draft]` | Push + open or update the PR with base = recorded parent. |
| `gt-stack sync [--prune]` | After merges: detect, reparent, cascade-rebase. |

Environment: `GT_STACK_TRUNK` overrides the trunk branch name (default `main`).

State: `.git/gt-stack/parents` — one `branch=parent` line per recorded branch.

## Typical flow

Phase 1 of a plan has three PRs that ship in order:

```bash
# Start the stack
git checkout main && git pull --ff-only
gt-stack new phase1-observability
# ... edit, test ...
git add -A && git commit -m "phase 1: OTel baseline"
gt-stack submit              # bottom of the stack — opens ready for review

# Second PR, draft because phase 1 isn't approved yet
gt-stack new phase1-dashboards
# ... edit, test ...
git add -A && git commit -m "phase 1: dashboards"
gt-stack submit --draft

# Third PR, draft
gt-stack new phase1-runbook
git add -A && git commit -m "phase 1: runbook"
gt-stack submit --draft
```

When the bottom PR receives review feedback:

```bash
# Fix the code, then amend + restack
git commit --amend
gt-stack restack    # rebases descendants onto the new parent SHA
gt-stack submit     # from the bottom branch — pushes current + all descendants
                    # use `gt-stack submit <branch>` to limit to one PR
```

When it merges:

```bash
gt-stack sync           # detects the merge, reparents descendants onto main,
                        # rebases the stack, leaves descendants ready to submit
gt-stack submit phase1-dashboards   # retargets PR base to main, pushes
```

## What `gt-stack` deliberately does NOT do

- It does not submit PRs to merge. Use `gh pr merge` or GitHub UI.
- It does not write anything to PR titles, descriptions, or bodies
  (keeps Change-Workflow §6 clean — no internal identifiers leak).
- It does not manage review assignments or approvals.
- It does not lock branches or prevent direct git operations. If you
  reorder commits or break the single-commit rule, you own the mess.

## Interaction with other concierge skills

- **`/concierge:plan`** asks whether the phases in a plan ship as a
  stack. When the answer is yes, the plan records stack-aware guidance
  for `/concierge:go`.
- **`/concierge:go`** respects the plan's stack declaration: it
  dispatches work items in stack order, suggests `gt-stack new` for
  each new tier, and reminds you to `gt-stack sync` after a merge.
- **`/concierge:setup`** audits for `gt-stack` presence via
  `audit_env.py` and installs it via `ensure_gt_stack.py`.
