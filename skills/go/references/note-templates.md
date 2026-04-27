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
---
pr: <number>
repo: <owner>/<repo>
title: "<PR title>"
author: <github-handle>
reviewer: <your-github-handle> (via Claude Code)
date: <YYYY-MM-DD>
verdict: <APPROVE | REQUEST_CHANGES | COMMENT>
grade: <A-F>
review_id: <github-review-id, filled after posting>
review_url: <https://github.com/...#pullrequestreview-...>
---

# Review #<review-number> — <owner>/<repo> PR <number>

## PR

- **Title:** <PR title>
- **Branch:** `<head>` → `<base>`
- **Author:** @<author>
- **Stats:** +<adds> / -<dels> across <n> files

### What it changes
<2-3 sentences on what this PR does, including any motivating bug or feature.>

## Verdict

**<APPROVE | REQUEST_CHANGES | COMMENT>** — <one sentence justifying the verdict and grade>.

**Grade: <A-F>**

## What this PR does well
- <thing-1>
- <thing-2>

## Findings

| # | Severity | File                  | Line | Title                                |
|---|----------|-----------------------|------|--------------------------------------|
| 1 | CRITICAL | `<path>`              | <n>  | <short title>                        |
| 2 | HIGH     | `<path>`              | <n>  | <short title>                        |
| 3 | MEDIUM   | `<path>`              | <n>  | <short title>                        |
| 4 | LOW      | `<path>`              | <n>  | <short title>                        |

### Finding 1 (<SEVERITY>) — <title>
<Problem explanation. Suggested fix.>

### Finding 2 (<SEVERITY>) — <title>
<…>

## Posted

- Review URL: <fill after posting>
- Inline comments: <count> (resolved against commit `<sha>`)
- Disclosure footer added to each comment + summary noting Claude Code posted on behalf of @<user>.
```

The frontmatter is the source of truth for tooling that aggregates reviews; keep it accurate even if the body drifts.

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
