# Default local layout

Resolve defaults in this order:

- GT root: `MAIN_GT_ROOT`, then `GT_TOWN_ROOT`, then `~/gt`
- Obsidian vault: `MAIN_OBSIDIAN_ROOT`, then `OBSIDIAN_VAULT`, then `~/notes/work`

Use this structure unless the user says otherwise.

```text
<gt-root>/                  # Gas Town root
<obsidian-root>/            # Obsidian vault

<obsidian-root>/
  Shared/
    Standards/
    Security/
    Reliability/
  Projects/
    <Project>/
      Convoys/
      Decisions/
      Notes/
```

Use rig names to seed project folders when the user has not named a broader project theme yet.
