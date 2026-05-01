---
name: plan
description: interactive planning skill that interviews the user about a feature, change, or improvement, records decisions, explores the codebase via graphify, and produces a structured plan in obsidian with phases, milestones, dependencies, and technology decisions. use when the user wants to plan work before starting it. also supports listing all plans across all rigs to view their completion status.
allowed-tools:
  - Bash(gt *)
  - Bash(gt-stack *)
  - Bash(bd *)
  - Bash(graphify *)
  - Bash(rtk *)
  - Bash(git *)
  - Bash(gh *)
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
metadata:
  default_gt_root: ~/gt
  default_obsidian_vault: ~/notes/work
  default_gt_envs: MAIN_GT_ROOT, GT_TOWN_ROOT
  default_obsidian_envs: MAIN_OBSIDIAN_ROOT, OBSIDIAN_VAULT
  graphify_policy: scan_on_rig_mention_then_on_demand
  plan_output: User/Plans/{project}/{yyyy-mm-dd}-{slug}.md
  transcript_output: User/Plans/{project}/{yyyy-mm-dd}-{slug}-interview.md
---

# Concierge Plan

Use this skill when the user wants to plan work before starting it. The skill interviews the user, explores the codebase, records decisions, and produces a structured plan in Obsidian.

The plan is a snapshot reference document. Gastown is authoritative on execution state. After approval the skill offers to hand off to `/concierge:go` to begin Phase 1.

When invoked as `/concierge:plan list`, the skill lists all plans across all rigs with their completion status (complete/incomplete phases, complete/incomplete milestones, and progress percentage).

## Path Resolution

Resolve paths in this order:

- GT root: `MAIN_GT_ROOT`, then `GT_TOWN_ROOT`, then `~/gt`
- Obsidian vault: `MAIN_OBSIDIAN_ROOT`, then `OBSIDIAN_VAULT`, then `~/notes/work`

## List Plans Mode

When the user invokes `/concierge:plan list`, the skill scans all rigs in the GT town for their `Plans/` directories and displays a summary table with:

- Rig name
- Plan title
- Status (Draft/Approved)
- Project name
- Complete/Total phases
- Complete/Total milestones
- Progress percentage

### Implementation Steps:

1. **Discover all rigs**: Use `gt rig list` to get all rig names in the town
2. **Scan Plans directories**: For each rig, check `$GT_ROOT/$rig/Plans/` and `$GT_ROOT/$rig/.beads/Plans/`
3. **Parse plan files**: Read each `.md` file in Plans directories
4. **Extract metadata**: Parse frontmatter and markdown to get:
   - Plan title (from `# Title`)
   - Status (from Status field)
   - Project name (from Project field)
   - Phases section (count complete/incomplete phases)
   - Milestones (count complete/incomplete from `- [ ]` vs `- [X]`)
5. **Display table**: Show all plans in a formatted table
6. **Offer next steps**: Ask user what they want to do next

### Example Output:

```
| Rig         | Plan Title                              | Status | Project | Phases       | Milestones         | Progress |
|-------------|-----------------------------------------|--------|---------|--------------|--------------------|----------|
| flutter_code| flutter-code Phase 9                    | Draft  | fc      | 8/9 phases   | 42/50 milestones   | 84%      |
| flags       | Feature flag rollout                    | Draft  | flags   | 0/3 phases   | 0/15 milestones    | 0%       |
```

### Completeness Tracking:

- **Complete phase**: All milestones are checked (`- [X] `)
- **Incomplete phase**: At least one milestone is unchecked (`- [ ] `)
- **Complete milestone**: Line starts with `- [X] `
- **Incomplete milestone**: Line starts with `- [ ] ` (not in verification section)

After the list, prompt the user: "What would you like to do next: plan new work, review a specific plan, or continue with something else?"

## Work Types

Ask the user what type of work this is. Use the type to tailor the interview questions and plan depth.

| Type | Focus areas |
|:--|:--|
| New Feature | scope, user impact, API surface, data model, UI/UX, rollout |
| Refactor | motivation, boundaries, risk areas, migration path, backwards compatibility |
| Test Improvement | coverage goals, test architecture, fixtures, CI impact |
| Migration | source/target, data integrity, rollback strategy, downtime tolerance |
| Bug Fix | reproduction, root cause, blast radius, regression prevention |
| Infrastructure | reliability, observability, scaling, cost, security |
| Documentation Update | audience, scope, format, maintenance plan |
| Performance Improvement | bottleneck, measurement, targets, tradeoff tolerance |
| Dependency Updates | motivation, breaking changes, testing strategy, rollback |
| Security Analysis | threat model, attack surface, compliance requirements, remediation priority |
| Other | use a generic question set adapted to what the user describes |

## Interview Flow

### Phase 1: Discovery (open-ended)

Start with 2-3 open-ended questions to understand intent:

- What are you trying to achieve and why?
- Who or what is affected?
- What does success look like?

Use these answers to identify the work type (confirm with the user), the project, and the likely rigs involved.

### Phase 2: Codebase scan

When a rig is first identified, do a lightweight Graphify scan:

- Run `graphify query` to understand top-level structure, key patterns, and dependencies.
- Note existing patterns, conventions, and potential constraints.
- Use findings to inform subsequent questions and recommendations.

Do not narrate the scan in detail. Mention relevant findings only when they affect a recommendation.

### Phase 3: Structured interview (bulk of the interview)

Ask questions one at a time. For each question:

1. State the question clearly.
2. Present three options with tradeoffs for each.
3. Mark one as your recommendation with a short rationale.
4. Remind the user they can type a different answer if none of the options fit.

Example format:

```
**Database strategy for user preferences**

1. **Add columns to the existing users table** -- simplest, no migration complexity, but couples preferences to the user schema
2. **New preferences table with foreign key** -- clean separation, easy to extend, requires a join on read
3. **Document store (JSON column)** -- flexible schema, no migrations for new preference types, harder to query and index

Recommendation: **Option 2**. The shop rig already uses this pattern for user_settings, and preferences will likely grow new fields over time. A dedicated table keeps the users table stable.

Pick 1-3 or type your own approach.
```

**Question routing by type:**

- For architectural forks that depend on codebase state, run a targeted Graphify query before presenting options. Say "Let me check the codebase" briefly.
- For major architectural decisions (language, service boundaries, database, primary patterns), ask these early -- they shape phases.
- For tooling and library decisions, ask when they come up naturally or capture them in Technology Decisions at the end.

**Stacked-PR discovery:**

For any plan with more than one milestone per phase, or more than one phase that touches the same rig, ask whether the PRs will ship as a stack. Use the structured question format:

```
**PR shipping strategy for this phase**

1. **Independent PRs** -- each milestone lands as its own PR against main; no ordering required between PRs
2. **Stacked PRs** -- milestones land as a dependency chain (PR B is based on PR A, etc.); lands bottom-up after each merge
3. **One big PR for the whole phase** -- single reviewable unit; only viable for small phases

Recommendation: **{depends on phase size and rig count}**. For multi-step phases that read cleanly as a dependency chain, Option 2 keeps each PR small and reviewable while preserving reviewer flow.

Pick 1-3 or type your own approach.
```

If the answer is **Stacked PRs**:
- Record it in the plan's Technology Decisions (`Stacking = gt-stack`) and in the per-phase notes.
- The plan's phase description should include a short "Stack order" section listing the milestone order (which maps to bottom-to-top in the stack).
- `/concierge:go` will read this and dispatch milestones using `gt-stack new` for each branch.
- See `CONCIERGE_STACK.md` at the plugin root for the single-commit-per-branch convention and the three rules.

If the answer is **Independent PRs** or **One big PR**, skip the stack-specific output and proceed normally.

**Lint/format discovery:**

For each rig involved, check if lint and format commands are documented in Obsidian (`User/Projects/{project}/Notes/rig-tooling.md`). If not, ask the user:

- How do you run linting for this rig? (e.g. `npm run lint`, `ruff check .`, `golangci-lint run`)
- How do you run formatting? (e.g. `npm run format`, `ruff format .`, `gofmt -w .`)

Record the answers in the plan's Technology Decisions section AND write them to `User/Projects/{project}/Notes/rig-tooling.md` in the vault so future plans don't need to ask again.

### Phase 4: Plan generation

Once all decisions are made, generate the plan and interview transcript (see Output Format below). Write both files to the vault. Create the `User/Plans/{project}/` directory if it does not exist.

### Phase 5: Handoff offer

After writing the plan, tell the user:

- The plan file path in Obsidian.
- The interview transcript path.
- The plan status is `Draft`.

Then ask: "Want me to start Phase 1 now, or would you like to review the plan in Obsidian first?"

If the user wants changes, update the plan and stay in `Draft`. When the user approves, update the Status to `Approved` with a timestamp, then hand off to `/concierge:go` if requested.

## Output Format: Plan

Path: `User/Plans/{project}/{yyyy-mm-dd}-{slug}.md`

```md
# {Title}

## Status

| Field | Value |
|:--|:--|
| Status | Draft |
| Type | {work type} |
| Project | {project} |
| Rigs | {rig-1}, {rig-2} |
| Created | {yyyy-mm-dd} |
| Approved | -- |
| Phases | {count} |
| Total milestones | {count} |

## Overview

{2-3 paragraphs summarizing what we are trying to achieve, why it matters, and what success looks like.}

## Decisions

{Numbered list of every decision made during the interview. Each entry records the question, the chosen option, and the rationale.}

1. **{Decision topic}**: {Chosen option}. {Rationale}.
2. **{Decision topic}**: {Chosen option}. {Rationale}.
...

## Phases

### Phase 1: {Phase title}

**Goal:** {One sentence describing what this phase achieves.}

**Dependencies:** None (first phase)

**Acceptance criteria:**
- {criterion 1}
- {criterion 2}

#### {rig-name}

- [ ] `[rig: {rig-name}]` {Milestone 1 description}
- [ ] `[rig: {rig-name}]` {Milestone 2 description}
- ...

#### {other-rig-name}

- [ ] `[rig: {other-rig-name}]` {Milestone description}
- ...

#### Verification

- [ ] `[rig: {rig-name}]` **Style**: Linting and formatting pass with zero errors (`{lint command}`, `{format command}`)
- [ ] `[rig: {rig-name}]` **Unit**: All unit tests pass for code written in this phase
- [ ] `[rig: {rig-name}]` **Integration**: {Specific integration check relevant to this phase}
- [ ] `[rig: {rig-name}]` **Demo**: {Human-verifiable scenario, if applicable to this phase}

---

### Phase 2: {Phase title}

**Goal:** {One sentence.}

**Dependencies:**
- Phase 1 ({rationale why this phase depends on Phase 1})

**Acceptance criteria:**
- {criterion}

#### {rig-name}

- [ ] `[rig: {rig-name}]` {Milestone description}
- ...

#### Verification

- [ ] ...

---

{Continue for all phases...}

## Technology Decisions

| Category | Decision | Rationale |
|:--|:--|:--|
| Language | {e.g. Python 3.12} | {why} |
| Framework | {e.g. FastAPI} | {why} |
| Database | {e.g. PostgreSQL 16} | {why} |
| Testing | {e.g. pytest + factory_boy} | {why} |
| Linting ({rig}) | {command} | {tool and config} |
| Formatting ({rig}) | {command} | {tool and config} |
| Stacking | {none / gt-stack} | {why stacking or not; if stacked, list the stack order} |
| {other category} | {decision} | {rationale} |
```

### Verification tier guidelines

Not every phase needs all four tiers. Apply what is appropriate:

- **Style**: Always. Every phase, every rig. Zero lint/format errors in the entire rig, not just changed files.
- **Unit**: When the phase produces testable code.
- **Integration**: When the phase's output must work with previous phases or external systems.
- **Demo**: When the phase produces something a human can verify visually or interactively. Typically for user-facing phases.

### Phase and milestone count guidance

Target 5-15 phases and 10-30 milestones per phase, but the actual count should match the work. A 3-phase plan or a 40-milestone phase is fine if the scope justifies it. Never pad milestones to hit a minimum or cut real work to stay under a maximum.

## Output Format: Interview Transcript

Path: `User/Plans/{project}/{yyyy-mm-dd}-{slug}-interview.md`

```md
# Interview: {Title}

**Date:** {yyyy-mm-dd}
**Project:** {project}
**Type:** {work type}
**Plan:** [[{yyyy-mm-dd}-{slug}]]

## Discovery

{Record the open-ended questions and the user's answers verbatim.}

**Q:** {question}
**A:** {user's answer}

## Codebase Findings

{Summary of what Graphify scans revealed, organized by rig.}

### {rig-name}
- {finding}
- {finding}

## Structured Decisions

{For each structured question, record the options presented, the recommendation, and what the user chose.}

### {Decision topic}

**Options:**
1. {option 1} -- {tradeoff}
2. {option 2} -- {tradeoff}
3. {option 3} -- {tradeoff}

**Recommendation:** {which and why}
**Decided:** {what the user chose and any custom rationale}
```

## Plan-to-Gastown Mapping

When handing off to `/concierge:go`:

- Each **Phase** becomes a **convoy**.
- Each **Milestone** becomes a **bead** dispatched to the rig specified in its `[rig: ...]` tag.
- **Phase dependencies** map to convoy ordering.
- **Milestone order** within a rig group determines bead sequence.
- The verification milestones become the final beads in each convoy.

`/concierge:go` should read the plan from Obsidian and use this mapping to create convoys and beads. The plan's inline `[rig: ...]` tags are the authoritative source for rig assignment.

## Conversation Rules

1. Ask one question at a time. Wait for the user's answer before moving on.
2. After the initial discovery questions, always use the structured format (3 options + custom + recommendation).
3. Record every decision as you go. Do not wait until the end to reconstruct them.
4. Keep the conversation at the user's level. Do not expose Gastown internals unless the user asks.
5. If a question's answer depends on codebase state, explore with Graphify first, then present informed options.
6. Never ask questions that can be answered by reading the code. Use Graphify and file reads instead.
7. If the user wants to change a previous decision, update the running decision list and adjust any dependent decisions.

## Examples

- `/concierge:plan`
- `/concierge:plan list` - list all plans across all rigs
- `/concierge:plan new feature for the shop checkout flow`
- `/concierge:plan refactor the authentication middleware in api`
- `/concierge:plan improve test coverage for the payments module`
- `/concierge:plan migrate the user service from REST to gRPC`
- `/concierge:plan security analysis of the public API surface`
