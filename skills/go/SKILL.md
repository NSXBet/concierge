---
name: go
description: conversational intake and dispatch for gastown workspaces that use obsidian for notes, graphify for repo understanding, and rtk for shell-noise reduction. use when you want to describe work in plain language, continue previous work, start a new project, ask for status, or review a pull request, and want the agent to set up or repair gt, obsidian, graphify, and rtk as needed before dispatching work.
allowed-tools:
  - Bash(gt *)
  - Bash(gt-stack *)
  - Bash(bd *)
  - Bash(obsidian *)
  - Bash(graphify *)
  - Bash(rtk *)
  - Bash(git *)
  - Bash(ls *)
  - Bash(find *)
  - Bash(cat *)
  - Bash(pwd)
  - Bash(test *)
  - Bash(mkdir *)
  - Bash(printf *)
  - Bash(echo *)
  - Bash(command -v *)
  - Bash(grep *)
  - Bash(brew *)
  - Bash(curl *)
  - Bash(sh *)
  - Bash(gh *)
metadata:
  default_gt_root: ~/gt
  default_obsidian_vault: ~/notes/work
  default_gt_envs: MAIN_GT_ROOT, GT_TOWN_ROOT
  default_obsidian_envs: MAIN_OBSIDIAN_ROOT, OBSIDIAN_VAULT
  graphify_policy: install_if_missing_refresh
  shell_noise_policy: prefer_rtk
---

# Concierge

Use this skill when the user wants to stay in plain language and have the agent handle GT, Obsidian, Graphify, and RTK behind the scenes.

The user should not need to think in terms of beads, convoys, or exact commands. Translate intent into the right steps, ask only the minimum blocking questions, and start the work as soon as you have enough information.

## Path Resolution

Resolve paths in this order:

- GT root: `MAIN_GT_ROOT`, then `GT_TOWN_ROOT`, then `~/gt`
- Obsidian vault: `MAIN_OBSIDIAN_ROOT`, then `OBSIDIAN_VAULT`, then `~/notes/work`

Use `scripts/resolve_context.sh` before taking action.

## Conversation Rules

1. Keep the conversation at the user's level.
   - Say “I’m starting the Shop coupon feature across api and web.”
   - Do not lead with bead IDs, convoy IDs, or raw GT internals.

2. If `$ARGUMENTS` is empty, vague, or missing, ask one concise question:
   - “What do you want to do right now: start a feature, continue previous work, start a project, or check status/blockers?”

3. Ask only the questions that block action.
   - Good: project or rigs, desired outcome, must-have constraints.
   - Avoid asking for IDs or command choices unless the user explicitly wants them.

4. Hide GT mechanics unless they help.
   - Use beads and convoys behind the scenes.
   - Mention them only for status tracking, ambiguity resolution, or when the user asks.

5. Prefer starting work over explaining theory.
   - Once scope is clear enough, create or update notes, set up missing context, and dispatch work.

6. Never use raw `tmux send-keys` to message Claude sessions.
   - Use `gt nudge` for synchronous messages.

## Minimal Foundation Policy

If the work cannot proceed because the local foundation is missing, do the minimum setup needed to keep momentum.

1. If the GT root is missing or not initialized, initialize it with `gt install <gt-root>`.
2. If the target rig does not exist and the user is working from remote repos, ask for repo URLs only if they are missing.
   - Prefer `gt rig add <name> <url>`.
   - Use `gt init` only when the user explicitly wants to initialize an existing local git repo in place.
3. If RTK is missing or not initialized, install or initialize it so shell-heavy commands stay compressed.
4. If the Obsidian vault layout is missing, create the minimum project structure.
5. If Graphify is missing in the target repo, install and build it; if present, refresh it.

If broad foundation work is needed across multiple rigs or projects, switch to the setup workflow described in `references/setup-handoff.md`.

## RTK Policy

- Prefer RTK-backed shell behavior for noisy commands such as `ls`, `find`, `grep`, `git status`, `git diff`, and test runs.
- If RTK is already installed and the Claude user hook is active, use normal shell commands and let RTK rewrite them.
- If `rtk` exists but is not initialized, run `rtk init --global` before heavy shell work.
- If `rtk` is missing and setup is allowed, install it first. Prefer Homebrew when available; otherwise use the official installer.
- Fall back to plain shell commands only when RTK setup is blocked or fails.

## Decision Tree

### A. New feature

Use this path when the user wants new work started in an existing project.

1. Resolve the project or theme and likely rigs.
2. If rigs are unclear, infer from the current directory, repo names, `gt rig list`, or the user’s wording.
3. If GT or the needed rig is missing, do the minimum foundation work first.
4. Create or update the project note and a feature note using the templates in `references/note-templates.md`.
5. Ensure Graphify exists on the affected rig clone or clones that will be used immediately.
   - If missing on the active working clone, install and build.
   - If already present, refresh with `--update`.
6. Create the necessary work items behind the scenes.
   - One rig: create one issue and let `gt sling` auto-create the convoy.
   - Multiple rigs: create one issue per rig and create an explicit convoy.
7. Dispatch the work.
   - Use `gt sling <bead> <rig>` for polecat work.
   - Use `gt sling <bead>` only when already inside the target agent session.
   - Use `gt worktree <rig>` only for a quick supporting touch from an existing crew session.
   - If the plan declares stacking (Technology Decisions row `Stacking = gt-stack`), apply the stack-aware dispatch below before sling-ing work.
8. Tell the user what was started, what notes were created or updated, and any remaining blockers.

### A.1. Stacked-PR dispatch

When the plan declares `Stacking = gt-stack`:

1. The plan's phase section lists a stack order (bottom-to-top). Each entry in the order maps to one PR and therefore one stacked branch.
2. For each milestone in stack order, instruct the polecat session to use `gt-stack new <branch-name>` off the previous stacked branch (or off `main` for the bottom branch). Branch names should describe the slice in plain language (e.g. `phase1-observability`, `phase1-dashboards`).
3. Enforce the single-commit-per-branch convention: the polecat must iterate with `git commit --amend` + `gt-stack submit`, not by adding new commits.
4. The first branch in the stack becomes **ready-for-review** (`gt-stack submit`, no `--draft`); all branches above it open as **draft** (`gt-stack submit --draft`) until the one below them merges.
5. After any merge, run `gt-stack sync` to detect the merge, reparent descendants onto `main`, cascade-rebase, and retarget the PR base via `gt-stack submit` on each remaining branch.
6. Never use raw `git push --force` — `gt-stack push` and `gt-stack submit` already use `--force-with-lease=<ref>:<sha>` to avoid clobbering a collaborator's work.
7. Communicate the stack state to the user in plain language: "Phase 1 is three stacked PRs; #293 is ready for review and #294 / #295 are drafts on top."

For the full convention and the three rules (one commit per branch, merge bottom-up, restack after every amend or merge), see `CONCIERGE_STACK.md` at the plugin root.

### B. Continue previous work

Use this path when the user wants to resume something already in flight.

1. Recover context in this priority order:
   - current working directory and active repo
   - `gt hook`
   - `gt convoy list`
   - `gt trail --since 3d --limit 10`
   - relevant Obsidian notes
2. If there is a single strong candidate, summarize it and continue.
3. If there are multiple plausible candidates, show up to three choices in plain language and ask the user to pick one.
4. Refresh Graphify for the active repo if it exists and looks stale.
5. If the work is part of a stack (parent file `.git/gt-stack/parents` has entries, or the plan declares stacking), check stack state: run `gt-stack list` from the working repo to recover branch order, then use `gh pr list --json number,headRefName,isDraft,state` (or `gh pr view <branch> --json isDraft,state` per branch) to report which PRs are ready vs. draft, and call out any that need a `gt-stack sync` (e.g. the bottom PR has merged since the last session).
6. Update the feature note with current status and next steps.
7. Dispatch follow-on work or nudge the right agent.

### C. New project

Use this path when the user wants to start a brand new project or add a repo to the town.

1. If the GT root does not exist, initialize it.
2. Ask for the repo URL or local repo path only if missing.
3. Ask for the desired rig name only if it is not obvious.
4. Use `gt rig add <name> <url>` for remote repos.
5. Use `gt init` only when the user explicitly wants to initialize the current local git repo in place.
6. Create the project folders and starter notes in Obsidian.
7. Install or refresh Graphify in the canonical repo clone.
8. Start the first slice of work:
   - ask one targeted scoping question if needed, or
   - create and dispatch the kickoff task immediately if scope is already clear.

### E. Review a pull request

Use this path when the user wants a code review on a PR. The review is saved to Obsidian and optionally posted to GitHub. Posting a review is a visible, multi-author-affecting action — confirm intent before publishing if the user wasn't explicit.

1. Identify the PR.
   - The user may give a PR number, URL, or repo name.
   - If only a number is given, infer the repo from the current rig or ask.
   - Fetch metadata: `gh pr view <number> --repo <owner/repo> --json title,author,baseRefName,headRefName,number,body,files,state,additions,deletions`.

2. Fetch the diff (with a fallback for truncated output).
   - Try `gh pr diff <number> --repo <owner/repo>` first.
   - If output is truncated (RTK or terminal limits) or you need to grep around context the diff strips, fall back to fetching the PR ref into a local clone and reading the file at HEAD:
     ```bash
     cd <local-clone-of-the-rig>
     git fetch origin pull/<number>/head:pr-<number>
     git show pr-<number>:<path-to-file> > /tmp/<file>.pr
     # Use baseRefName from step 1's `gh pr view --json` output — not a hardcoded "main".
     git diff <baseRefName>..pr-<number> -- <path>
     ```
   - For large PRs, list files first with `gh pr view <number> --repo <owner/repo> --json files`.

3. Determine the review number.
   - Check `User/PR-Reviews/<project>/<PR-number>/` in the Obsidian vault.
   - Next number is `max(existing) + 1`. First review is `1`.

4. Read relevant project context.
   - Skim `User/Projects/<project>/` notes for architecture context.
   - If Graphify is built on the rig, use `graphify query` to understand affected code paths.

5. Perform the review.
   - Read the diff thoroughly. For each file, understand what changed and why.
   - Grade the PR from A to F:
     - **A** — excellent, no issues
     - **B** — good, minor nits only
     - **C** — acceptable, has issues that should be addressed
     - **D** — significant problems, needs rework
     - **F** — critical issues, should not merge
   - Categorize findings:
     - **CRITICAL** — bugs, security issues, data loss risks. Must fix.
     - **HIGH** — logic errors, missing validation, architectural concerns. Should fix.
     - **MEDIUM** — code quality, naming, missing tests. Worth fixing.
     - **LOW** — style, minor improvements. Optional.
     - **NIT** — preferences, formatting. Take it or leave it.
   - For each finding record: severity, file path, line range, description, and suggested fix.

6. Write the Obsidian review note.
   - Path: `User/PR-Reviews/<project>/<PR-number>/<review-number>.md`.
   - Use the review note template from `references/note-templates.md` (frontmatter + findings table + "what this PR does well" section).

7. Inline comment shape (binding when posting).
   Each inline comment must follow this structure so reviewers and authors can scan reviews consistently and humans can hand-off fixes to other AI assistants without re-explaining:

   ```md
   **[SEVERITY] — Short title**

   <One paragraph: why this is a problem, with file/line anchors and any
    relevant code references. Keep it concrete and specific.>

   **Suggestion:** <one paragraph or short bullet list of fix options.>

   <details>
   <summary>🤖 Prompt to AI</summary>

   Before fixing this, please validate it is actually a problem.

   <Self-contained prompt: file paths, symbol names, what to grep for,
    what to verify, and the concrete change to propose. Written so the
    user can paste it into any AI assistant cold.>

   </details>

   <sub>_— I'm Claude Code, posting this comment on behalf of @<user>._</sub>
   ```

   Conventions:
   - The "Prompt to AI" body **must** start with the literal sentence `Before fixing this, please validate it is actually a problem.` — this protects the author from cargo-culted "fixes" to non-issues.
   - The disclosure footer is **mandatory** on every comment and on the top-level review summary. Never post under a human's account without it.
   - Resolve the human's GitHub handle from `gh auth status` before composing the footer; do not guess.

8. Pre-flight before posting.
   - **Account check.** Run `gh auth status` and confirm which account will publish the review. Surface the login to the user if it isn't obvious from context.
   - **Line-numbers-in-hunks check.** Inline comments must target a line that falls inside one of the PR's diff hunks (a changed line or the surrounding context). Lines outside any hunk will silently fail or land on the wrong place. Read the `@@ ... @@` headers and confirm each comment's `line` is in range.
   - **JSON validation.** Validate the review payload before sending: `python3 -c "import json; json.load(open('<file>'))"`. Heredoc / shell quoting bugs are the #1 reason a review submit returns garbage.

9. Post to GitHub (only if the user asks, or confirm before posting).
   - Determine the verdict: `APPROVE`, `REQUEST_CHANGES`, or `COMMENT`.
   - Build a single JSON file with the full review payload — do not mix `-f` flags with `--input`:
     ```json
     {
       "event": "COMMENT",
       "body": "<top-level review summary, including findings table and disclosure footer>",
       "comments": [
         {
           "path": "<file>",
           "line": <line-in-new-file>,
           "side": "RIGHT",
           "body": "<inline comment per the shape in step 7>"
         }
       ]
     }
     ```
   - Post:
     ```bash
     gh api repos/<owner>/<repo>/pulls/<number>/reviews \
       --method POST \
       --input <payload.json>
     ```
   - Verify the inline comments were anchored correctly:
     ```bash
     gh api "repos/<owner>/<repo>/pulls/<number>/comments" \
       --jq '.[] | select(.pull_request_review_id == <review-id>) | {path, line, body: .body[0:80]}'
     ```
   - Update the Obsidian review note's frontmatter with `review_id` and `review_url`.

10. Reply format.
    - Show grade, finding counts by severity, and verdict.
    - Link the review URL.
    - If not posting to GitHub, ask: "Want me to post this as a review on the PR?"

### D. Status, blockers, and routing

Use this path when the user wants to know what is happening, what is blocked, or what to do next.

1. Prefer `gt convoy status` for feature-level questions.
2. Prefer `gt rig status <rig>` for repo-level questions.
3. Prefer `gt peek` or `gt nudge` when you need to inspect or steer a specific session.
4. Summarize in plain language:
   - what is moving
   - what is blocked
   - what should happen next

## Environment Checks

Before doing side-effectful work, verify the basics:

- `gt` and `bd` exist
- the GT root exists, or can be initialized
- the Obsidian vault exists, or can be created safely
- `graphify` exists, or can be installed
- `rtk` exists, or can be installed and initialized
- the target rig exists, or can be added

If the foundation is missing across many rigs or the vault needs a broad bootstrap, switch to the setup workflow and follow `references/setup-handoff.md`.

## Notes Policy

1. Keep one project area under `User/Projects/<Project>/`.
2. Keep one feature note under `User/Projects/<Project>/Convoys/<slug>.md` even if the user never sees the convoy ID.
3. Use the `Decisions` folder for durable choices, not transient status.
4. Append short, factual updates. Do not rewrite the whole note unless structure is broken.
5. If Obsidian CLI is unavailable, edit the markdown files directly. The vault is just a folder of markdown files.

## GT Execution Policy

Use these patterns:

- Initialize or repair GT root: `gt install`
- Add a rig from a repo URL: `gt rig add`
- Initialize an existing local repo in place: `gt init`
- Start or attach GT services: `gt start`, `gt mayor attach`
- Dispatch work: `gt sling`
- Track cross-rig work: `gt convoy create`, `gt convoy status`, `gt convoy list`
- Recover active context: `gt hook`, `gt trail`, `gt ready`
- Communicate with sessions: `gt nudge`, `gt peek`

Use `bd` directly only as the hidden implementation detail for creating or updating work items.

## Reply Format

Always end with this structure:

### What I’m doing
A short statement of the task you started or resumed.

### Rigs involved
The rigs you identified or touched.

### Notes and setup
What note you created or updated, plus any setup work such as GT init, RTK enablement, or Graphify refresh.

### Work started
What you dispatched or what is now ready to dispatch.

### Questions or blockers
Only include the missing pieces that prevent further action.

## Examples

- `/concierge:go`
- `/concierge:go start the checkout coupon feature for shop`
- `/concierge:go continue previous work on onboarding`
- `/concierge:go start a new project from https://github.com/acme/analytics-api`
- `/concierge:go what is blocked in shop right now?`
- `/concierge:go review PR 142 on flags`
- `/concierge:go review https://github.com/acme/flags/pull/142`
- `/concierge:go review PR 142 on flags and post it`
