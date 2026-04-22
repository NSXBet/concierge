---
name: setup
description: initialize or repair the local foundation for gastown, obsidian, graphify, and rtk. use when the gt root may not exist yet, you want to add rigs from repo urls, create or repair the obsidian vault layout, install rtk and its claude hook, install graphify when missing, or refresh graphify on existing rigs.
allowed-tools:
  - Bash(gt *)
  - Bash(bd *)
  - Bash(obsidian *)
  - Bash(graphify *)
  - Bash(rtk *)
  - Bash(git *)
  - Bash(python3 *)
  - Bash(pip *)
  - Bash(ls *)
  - Bash(find *)
  - Bash(cat *)
  - Bash(test *)
  - Bash(mkdir *)
  - Bash(echo *)
  - Bash(command -v *)
  - Bash(grep *)
  - Bash(brew *)
  - Bash(curl *)
  - Bash(sh *)
  - Bash(chmod *)
metadata:
  default_gt_root: ~/gt
  default_obsidian_vault: ~/notes/work
  default_gt_envs: MAIN_GT_ROOT, GT_TOWN_ROOT
  default_obsidian_envs: MAIN_OBSIDIAN_ROOT, OBSIDIAN_VAULT
  graphify_policy: install_if_missing_refresh
  default_scope: canonical_mayor_clone_per_rig
---

# Concierge Setup

Use this skill to prepare or repair the local environment so `concierge` can operate smoothly.

The user should not need to remember how GT is initialized, how Obsidian folders are named, how RTK is enabled, or which Graphify commands to run. Handle the setup and report what changed.

## Defaults

Resolve paths in this order unless the user says otherwise:

- GT root: `MAIN_GT_ROOT`, then `GT_TOWN_ROOT`, then `~/gt`
- Obsidian vault: `MAIN_OBSIDIAN_ROOT`, then `OBSIDIAN_VAULT`, then `~/notes/work`

Obsidian vault layout is composition-based: the vault root is an unversioned container holding one git repo per top-level folder.

- `Shared/<Name>/` — one directory per entry in `shared:` from the concierge config, each cloned from its configured git URL.
- `User/` — cloned from `user:` in the concierge config. All skill-managed folders (`Projects/`, `Plans/`, `PR-Reviews/`, `Analysis/`, etc.) live under `User/`.
- Graphify scope: each rig's canonical repo clone at `<gt-root>/<rig>/mayor/rig`.
- Graphify policy: install if missing, refresh if present.

Concierge config resolution order:

1. `$CONCIERGE_CONFIG` — inline JSON with the full config (`{"shared": {...}, "user": "<url>"}`). Takes precedence when set.
2. `~/.concierge.json` — persistent config file with the same shape.
3. Neither set — first-run flow: collect `user` URL and any `shared` entries conversationally, write `~/.concierge.json`, then proceed.

`user` is required. `shared` is optional (empty object or omitted key is fine). Folder names under `Shared/` come from each key with its first character capitalized (`engineering` -> `Engineering`; `SecurityPlatform` stays `SecurityPlatform`).

Use the helper scripts in `scripts/` for deterministic filesystem work.

## If Arguments Are Missing

If `$ARGUMENTS` is empty or vague, ask one concise question:

- “Do you want me to audit everything, initialize the workspace, add rigs, or just refresh Graphify?”

## Concierge Setup Workflow

1. Resolve paths.
   - Use `MAIN_GT_ROOT`, then `GT_TOWN_ROOT`, then `~/gt`.
   - Use `MAIN_OBSIDIAN_ROOT`, then `OBSIDIAN_VAULT`, then `~/notes/work`.

2. Audit the environment.
   - Check `gt`, `bd`, `git`, `graphify`, and `rtk`.
   - Check whether the GT root exists and is initialized.
   - Check which rigs exist with `gt rig list` or by inspecting the town root.
   - Check whether the Obsidian MCP server is available.

3. Initialize or repair GT if needed.
   - Use `scripts/ensure_gt.py --apply`.
   - If the GT root is missing or not initialized, this should run `gt install <gt-root>`.
   - If the town has no rigs and the user did not already provide repo URLs, ask whether they want to add rigs now.
   - Accept repo inputs as raw URLs or `name=url` pairs.
   - Prefer `gt rig add <name> <url>` for remote repos.
   - Use `gt init` only when the user explicitly points at an existing local git repo that should be initialized in place.

4. Create or repair the Obsidian vault structure.
   - Resolve the concierge config:
     a. If `$CONCIERGE_CONFIG` is set, treat its value as inline JSON and use that.
     b. Else if `~/.concierge.json` exists, read it.
     c. Else enter first-run flow: ask the user for their `user:` git URL (required) and any `shared:` entries they want (name + git URL, repeatable; blank to finish). Write the collected map to `~/.concierge.json` as valid JSON.
   - Validate the config before running the script:
     - `user` must be present and a string URL.
     - `shared` (if present) must be an object mapping display name to git URL.
   - Invoke `scripts/bootstrap_obsidian.py --apply`. The script will:
     - Clone each `shared.<Name>` entry to `Shared/<Name>/` (first-char-capitalized key).
     - Clone `user:` to `User/`.
     - For any target that already exists and matches the expected remote, skip it (no `git pull`).
     - For any target that exists but is not a git repo or has a different origin, fail with a clear message. Do not mutate or delete anything.
     - On full success, write the vault-root `README.md` from `references/vault-root-readme.md.tmpl`.
   - If the script exits nonzero, surface the error verbatim to the user and stop. Setup is all-or-nothing for the vault.
   - Do not overwrite user-authored notes. The script only writes the vault-root `README.md`; everything else is owned by the individual repos.

5. Ensure the Obsidian MCP server is connected.
   - Check whether `mcp-obsidian` (or `mcp__mcp-obsidian__obsidian_list_files_in_vault`) is available as an MCP tool.
   - If it is not available, walk the user through setting it up:
     a. Obsidian must be installed and running.
     b. The **Local REST API** community plugin must be enabled in Obsidian (Settings > Community plugins > Browse > "Local REST API"). See https://github.com/coddingtonbear/obsidian-local-rest-api.
     c. The user needs the API key from the Local REST API plugin settings.
     d. Add the MCP server to `~/.claude/.mcp.json` (or the project `.mcp.json`):
        ```json
        {
          "mcpServers": {
            "mcp-obsidian": {
              "command": "uvx",
              "args": ["mcp-obsidian"],
              "env": {
                "OBSIDIAN_API_KEY": "<api-key>"
              }
            }
          }
        }
        ```
     e. After editing the config, tell the user to restart Claude Code or run `/reload-plugins`.
   - If the MCP server is already available, confirm it is working by listing files in the vault.

6. Ensure RTK is active.
   - Use `scripts/setup_rtk.sh --apply`.
   - If `rtk` is missing, prefer Homebrew when available; otherwise use the official installer.
   - Run `rtk init --global` so Claude's shell commands can be rewritten through RTK.
   - If RTK is already present, verify the hook is installed and repair it if needed.

7. Install or refresh Graphify.
   - If `graphify` is missing, install the package first, then run `graphify install`.
   - For each target rig, use `scripts/refresh_graphify.py --apply`.
   - Default to the canonical clone under `<rig>/mayor/rig`.
   - If the user is currently working in a crew clone and asks for immediate deep work there, you may also refresh that active clone.

8. Report remaining manual steps.
   - If you asked for repo URLs and are waiting on them, say that clearly.
   - If the Obsidian MCP server could not be verified, say so clearly.
   - If a rig has no repo clone yet, explain what is missing.
   - If RTK or Graphify installation fails, show the command and error.

## Policy

- Prefer idempotent changes.
- Create missing directories and starter notes; do not rewrite existing notes unless the user asks.
- Refresh existing graphs with `graphify . --update`.
- Install Claude integration and git hooks for Graphify on each target repo.
- Ask for rig URLs only when they are actually missing.
- Keep the user-facing summary short and concrete.

## Reply Format

Always report in this structure:

### Checked
What paths, rigs, and tools you audited.

### GT and RTK
What you initialized, added, or enabled for Gastown and RTK.

### Obsidian and MCP
Whether the vault exists, the MCP server is connected, and any setup steps taken or remaining.

### Created or repaired
What vault folders, notes, or repo integrations you created.

### Graphify status
Which rigs were installed, refreshed, skipped, or failed.

### Manual follow-up
Only the actions the user still needs to take.

## Examples

- `/concierge:setup`
- `/concierge:setup audit everything`
- `/concierge:setup initialize the workspace and ask me for rig urls`
- `/concierge:setup set up shop and growth`
- `/concierge:setup refresh graphify on all rigs`
