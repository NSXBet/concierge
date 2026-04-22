# Note templates

Use these templates when creating or updating notes in the default vault.

## Project root

Path:

`User/Projects/<Project>/README.md`

Suggested content:

```md
# <Project>

## Purpose
[one paragraph]

## Rigs
- <rig-1>
- <rig-2>

## Active work
- [[Convoys/<feature-slug>]]

## Key docs
- [[Notes/README]]
- [[Decisions/README]]
```

## Feature or convoy note

Path:

`User/Projects/<Project>/Convoys/<feature-slug>.md`

Suggested content:

```md
# <Feature title>

## Goal
[what success looks like]

## Scope
- included
- excluded

## Rigs involved
- <rig-1>
- <rig-2>

## Current status
[one short paragraph]

## Open questions
- [ ] question

## Decisions
- date: decision

## Next actions
- [ ] action
```

## Decisions index

Path:

`User/Projects/<Project>/Decisions/README.md`

Suggested content:

```md
# Decisions

## Durable decisions
- YYYY-MM-DD: [decision title](./decision-slug.md)
```

## PR review note

Path:

`User/PR-Reviews/<project>/<PR-number>/<review-number>.md`

Suggested content:

```md
# PR #<number>: <title>

**Author:** <author>
**Branch:** <head> → <base>
**Date:** <YYYY-MM-DD>
**Review:** #<review-number>

## Summary
[2-3 sentences on what this PR does]

## Grade: <A-F>
[One sentence justification]

## Findings

### CRITICAL
- **<file>:<lines>** — <description>
  > <suggested fix or explanation>

### HIGH
- **<file>:<lines>** — <description>

### MEDIUM
- **<file>:<lines>** — <description>

### LOW
- **<file>:<lines>** — <description>

### NIT
- **<file>:<lines>** — <description>

## Verdict: <APPROVE | REQUEST_CHANGES | COMMENT>
[One sentence on what needs to happen next]
```

## Analysis note

Path:

`User/Analysis/<project>/<YYYY-MM-DD>-<headline-slug>.md`

Suggested content:

```md
# <Headline>

**Date:** <YYYY-MM-DD>
**Rigs:** <rig-1>, <rig-2>
**Purpose:** <one sentence>

---

## 1. <Area>
[findings with file paths and line numbers]
**Severity:** <CRITICAL|HIGH|MEDIUM|LOW>

## Recommended Jobs (Priority Order)

### P0 — Do Now
| # | Job | Why |
|---|-----|-----|

### P1 — Do Soon
| # | Job | Why |
|---|-----|-----|

### P2 — Do When Convenient
| # | Job | Why |
|---|-----|-----|
```

## Vault structure

The vault is composed of independent git repositories — do not create or rename top-level folders. `Shared/<Name>/` repos are owned by whoever publishes each standards vault; `User/` is the personal vault from the concierge config.

Skill-managed folders all live under `User/` and are created on demand:

- `User/Projects/`
- `User/Plans/`
- `User/Analysis/`
- `User/PR-Reviews/`
- `User/Decisions/`
- `User/Operations/`
