# Concierge

A Claude Code plugin that lets you describe work in plain language and have the agent handle [Gastown](https://github.com/gastownhall/gastown), [Obsidian](https://obsidian.md), [Graphify](https://github.com/safishamsi/graphify), and [RTK](https://github.com/rtk-ai/rtk) behind the scenes.

Start features, continue previous work, review pull requests, check status, or bootstrap entire projects -- all without thinking about bead IDs, convoy commands, or tool-specific syntax.

## Getting started

### Prerequisites

- [Claude Code](https://code.claude.com/docs/en/quickstart) installed and authenticated
- [Gastown (`gt`)](https://github.com/gastownhall/gastown) installed
- [Obsidian](https://obsidian.md) installed with the [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) community plugin enabled (see [Setting up Obsidian](#setting-up-obsidian))
- [Graphify](https://github.com/safishamsi/graphify) installed
- [RTK](https://github.com/rtk-ai/rtk) installed
- [Git](https://git-scm.com/) and [GitHub CLI (`gh`)](https://cli.github.com/) installed

> `/concierge:setup` can install RTK and Graphify for you if they are missing, but all four tools are required for the full concierge experience.

### Install the plugin

Add the marketplace and install the plugin:

```
/plugin marketplace add NSXBet/concierge
/plugin install concierge@NSXBet-concierge
```

### Set up your environment

After installing, run:

```
/concierge:setup
```

This audits your machine and walks you through setting up everything concierge needs -- Gastown, Obsidian (including the MCP server connection), Graphify, and RTK. Once setup is complete, you're ready to go:

```
/concierge:go
```

## Skills

Concierge provides three skills:

### `/concierge:go` -- Conversational intake and dispatch

> **Run `/concierge:setup` first** to make sure your environment is properly configured. Setup detects and fixes missing tools, broken connections, and vault issues before they cause problems during work.

The main entry point. Describe what you want in plain language and concierge figures out the rest.

```
/concierge:go start the checkout coupon feature for shop
/concierge:go continue previous work on onboarding
/concierge:go start a new project from https://github.com/acme/analytics-api
/concierge:go what is blocked in shop right now?
/concierge:go review PR 142 on flags
/concierge:go review PR 142 on flags and post it
```

What it handles:

| Intent | What concierge does |
|:--|:--|
| **New feature** | Resolves rigs, creates project and feature notes in Obsidian, ensures Graphify is fresh, dispatches work via `gt sling` |
| **Continue work** | Recovers context from the working directory, `gt hook`, `gt convoy list`, `gt trail`, and Obsidian notes, then resumes |
| **New project** | Initializes GT if needed, adds rigs, creates vault structure, installs Graphify, kicks off the first task |
| **Status/blockers** | Queries `gt convoy status`, `gt rig status`, or `gt peek` and summarizes in plain language |
| **PR review** | Fetches the diff via `gh`, grades the PR (A-F), writes a structured review note to Obsidian, and optionally posts it to GitHub |

### `/concierge:plan` -- Interactive planning

> **Run `/concierge:setup` first** to make sure your environment is properly configured. Planning relies on Graphify and Obsidian -- setup ensures both are connected and working.

Interviews you about a piece of work, explores the codebase, and produces a structured plan in Obsidian before any code is written.

```
/concierge:plan
/concierge:plan new feature for the shop checkout flow
/concierge:plan refactor the authentication middleware in api
/concierge:plan improve test coverage for the payments module
/concierge:plan security analysis of the public API surface
```

How it works:

1. **Discovery** -- open-ended questions to understand what you want and why
2. **Type detection** -- identifies the work type (New Feature, Refactor, Migration, Bug Fix, Test Improvement, Performance Improvement, Security Analysis, Infrastructure, Documentation Update, Dependency Updates, or custom) and tailors the interview
3. **Codebase scan** -- uses Graphify to understand each involved rig's structure, patterns, and constraints
4. **Structured interview** -- asks questions one at a time with three options, tradeoffs, and a recommendation (you can always type your own answer)
5. **Plan generation** -- writes the plan to `Plans/{project}/{date}-{slug}.md` with phases, milestones, dependencies, and technology decisions
6. **Handoff** -- offers to start Phase 1 via `/concierge:go`, or you can review and edit the plan in Obsidian first

Each plan includes:

- **Status** with metadata (type, rigs, phase count)
- **Overview** of what you're trying to achieve
- **Decisions** recorded during the interview with rationale
- **Phases** (target 5-15) with dependencies and acceptance criteria
- **Milestones** per phase (target 10-30), each assigned to a single rig, with a verification milestone at the end of every phase (style, unit, integration, demo)
- **Technology Decisions** table with rationale

Plans map directly to Gastown: each phase becomes a convoy, each milestone becomes a bead dispatched to its tagged rig.

### `/concierge:setup` -- Environment initialization and repair

Audits and fixes your local foundation so `/concierge:go` can operate smoothly.

```
/concierge:setup
/concierge:setup audit everything
/concierge:setup initialize the workspace and ask me for rig urls
/concierge:setup set up shop and growth
/concierge:setup refresh graphify on all rigs
```

What it checks and repairs:

- **Gastown** -- initializes the GT root if missing, adds rigs from repo URLs
- **Obsidian vault** -- creates the folder structure (`Projects/`, `Plans/`, `Shared/`, `PR-Reviews/`, `Analysis/`)
- **RTK** -- installs via Homebrew or the official installer, runs `rtk init --global`
- **Graphify** -- installs the package, runs `graphify install`, builds or refreshes graphs on each rig

## Configuration

Concierge uses environment variables to locate your workspace. Set these in your shell profile (e.g. `~/.zshrc`) or in your Claude Code settings.

### Environment variables

| Variable | Purpose | Default |
|:--|:--|:--|
| `MAIN_GT_ROOT` | Primary Gastown root directory | `~/gt` |
| `GT_TOWN_ROOT` | Fallback GT root (checked if `MAIN_GT_ROOT` is unset) | `~/gt` |
| `MAIN_OBSIDIAN_ROOT` | Primary Obsidian vault path | `~/notes/work` |
| `OBSIDIAN_VAULT` | Fallback vault path (checked if `MAIN_OBSIDIAN_ROOT` is unset) | `~/notes/work` |

Resolution order: concierge checks the primary variable first, then the fallback, then uses the default.

Example shell configuration:

```bash
# ~/.zshrc
export MAIN_GT_ROOT="$HOME/gt"
export MAIN_OBSIDIAN_ROOT="$HOME/notes/work"
```

### Concierge config

The Obsidian vault is composed of independent git repositories — one per shared knowledge source plus one personal vault. Concierge reads the list of repositories from a JSON config.

Resolution order:

1. `CONCIERGE_CONFIG` environment variable (inline JSON). Takes precedence when set.
2. `~/.concierge.json` file.
3. If neither is present, `/concierge:setup` will collect the values conversationally on first run and write `~/.concierge.json` for you.

Config shape:

```json
{
  "shared": {
    "Engineering": "git@github.com:your-org/obsidian-engineering.git",
    "Team": "git@github.com:your-org/obsidian-<team>.git"
  },
  "user": "git@github.com:your-org/obsidian-user-<you>.git"
}
```

- `user` is required. Everything concierge writes (project notes, plans, PR reviews, analyses) lives under `User/`.
- `shared` is optional. Each entry becomes a subfolder under `Shared/` whose name is the key with its first character capitalized (`engineering` -> `Engineering`; `SecurityPlatform` stays `SecurityPlatform`).
- URLs are cloned verbatim — use whichever form (SSH or HTTPS) has the right access for the repo.

Inline JSON via env var (useful for CI or ephemeral environments):

```bash
export CONCIERGE_CONFIG='{"shared":{"Engineering":"git@github.com:acme/obsidian-engineering.git"},"user":"git@github.com:acme/obsidian-user-alice.git"}'
```

### Vault structure

Concierge builds the vault by cloning each configured repository into the vault root:

```
<vault>/                     # not a git repo itself; just a container
  README.md                  # generated map of the vault
  Shared/
    <Name>/                  # one cloned repo per entry in config shared:
  User/                      # cloned from config user:
    Projects/<Project>/
      Convoys/               # feature/work-tracking notes
      Decisions/             # durable architectural decisions
      Notes/                 # working notes and research
    Plans/<Project>/
      <date>-<slug>.md              # structured plans
      <date>-<slug>-interview.md    # interview transcripts
    PR-Reviews/<project>/<PR-number>/
      <review-number>.md
    Analysis/<project>/
      <date>-<slug>.md
```

Clone behavior is idempotent and fail-closed: missing folders are cloned fresh; folders already present with the matching origin are left alone; folders present with a different origin (or that are not git repos) cause setup to fail so nothing is silently overwritten.

## Setting up Obsidian

Obsidian is where concierge keeps all project context -- feature notes, PR reviews, architectural decisions, and analysis documents. Concierge reads and writes these as plain Markdown files, but Obsidian gives you a rich UI for browsing, linking, and editing them.

### 1. Install Obsidian

Download from [obsidian.md](https://obsidian.md) and open your vault directory (the path from `MAIN_OBSIDIAN_ROOT` or `~/notes/work` by default) as a vault.

### 2. Enable the Local REST API plugin

The REST API lets Claude Code interact with Obsidian for searching notes, reading rendered content, and appending updates through the app.

1. In Obsidian, go to **Settings > Community plugins > Browse**
2. Search for **Local REST API** and install it ([plugin page](https://github.com/coddingtonbear/obsidian-local-rest-api))
3. Enable the plugin and note the API key it generates
4. The API runs on `https://localhost:27124` by default

### 3. Connect Claude Code to Obsidian via MCP

The [Obsidian MCP server](https://github.com/MarkusPfundstein/mcp-obsidian) connects Claude Code to your vault through the Model Context Protocol, enabling full-text search, reading, and appending to notes.

1. Make sure the Local REST API plugin is enabled (step 2 above)
2. Add the server to your Claude Code MCP configuration (in `~/.claude/.mcp.json` or your project's `.mcp.json`):

```json
{
  "mcpServers": {
    "mcp-obsidian": {
      "command": "uvx",
      "args": ["mcp-obsidian"],
      "env": {
        "OBSIDIAN_API_KEY": "<your-api-key-from-local-rest-api>"
      }
    }
  }
}
```

3. Restart Claude Code or run `/reload-plugins` to pick up the new MCP server

> Concierge can also read and write vault files directly when Obsidian is not running. The MCP connection adds full-text search and rendered content access on top of that.

## How it works

Concierge sits on top of four tools and translates plain-language intent into the right sequence of commands:

```
  You: "start the checkout coupon feature for shop"
   |
   v
 concierge:go
   |
   +-- resolves GT root, finds the "shop" rig
   +-- creates/updates Obsidian notes (project + feature)
   +-- refreshes Graphify on the rig
   +-- dispatches work via gt sling
   |
   v
 "I'm starting the Shop coupon feature on the shop rig.
  Created Projects/Shop/Convoys/checkout-coupon.md.
  Dispatched bead to shop."
```

The four pillars:

- **Gastown** manages repos (rigs), work items (beads), cross-repo features (convoys), and agent sessions
- **Obsidian** holds project notes, feature tracking, PR reviews, decisions, and analysis documents
- **Graphify** builds a code graph so the agent understands repo structure and can query code paths
- **RTK** compresses noisy shell output (git status, ls, grep, test runs) to save tokens

## License

MIT
