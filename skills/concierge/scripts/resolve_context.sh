#!/usr/bin/env bash
set -euo pipefail

resolve_path() {
  local raw="$1"
  python3 - "$raw" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).expanduser().resolve())
PY
}

GT_ROOT_RAW="${MAIN_GT_ROOT:-${GT_TOWN_ROOT:-$HOME/gt}}"
OBSIDIAN_RAW="${MAIN_OBSIDIAN_ROOT:-${OBSIDIAN_VAULT:-$HOME/notes/work}}"
GT_ROOT="$(resolve_path "$GT_ROOT_RAW")"
OBSIDIAN_VAULT="$(resolve_path "$OBSIDIAN_RAW")"
CWD="${1:-$PWD}"
RIG=""
IN_GT=0
GT_INITIALIZED=0
RIGS_COUNT=0
RTK_INITIALIZED=0
CLAUDE_SETTINGS="${HOME}/.claude/settings.json"

if [ -d "$GT_ROOT" ]; then
  if [ -d "$GT_ROOT/mayor" ] && [ -d "$GT_ROOT/.beads" ]; then
    GT_INITIALIZED=1
  fi
  while IFS= read -r _; do
    RIGS_COUNT=$((RIGS_COUNT + 1))
  done < <(find "$GT_ROOT" -mindepth 1 -maxdepth 1 -type d ! -name '.*' -exec test -f '{}/config.json' ';' -print 2>/dev/null || true)
  case "$CWD" in
    "$GT_ROOT"|"$GT_ROOT"/*)
      IN_GT=1
      REL="${CWD#"$GT_ROOT"/}"
      FIRST="${REL%%/*}"
      case "$FIRST" in
        ""|"."|"mayor"|"deacon"|".beads"|"settings")
          RIG=""
          ;;
        *)
          if [ -d "$GT_ROOT/$FIRST" ]; then
            RIG="$FIRST"
          fi
          ;;
      esac
      ;;
  esac
fi

have_cmd() {
  if command -v "$1" >/dev/null 2>&1; then
    printf 'yes'
  else
    printf 'no'
  fi
}

if [ -f "$CLAUDE_SETTINGS" ] && grep -qi '"rtk\|rtk ' "$CLAUDE_SETTINGS"; then
  RTK_INITIALIZED=1
fi

printf 'gt_root=%s\n' "$GT_ROOT"
printf 'obsidian_vault=%s\n' "$OBSIDIAN_VAULT"
printf 'cwd=%s\n' "$CWD"
printf 'in_gt=%s\n' "$IN_GT"
printf 'gt_initialized=%s\n' "$GT_INITIALIZED"
printf 'rig=%s\n' "$RIG"
printf 'rigs_count=%s\n' "$RIGS_COUNT"
printf 'has_gt=%s\n' "$(have_cmd gt)"
printf 'has_bd=%s\n' "$(have_cmd bd)"
printf 'has_obsidian=%s\n' "$(have_cmd obsidian)"
printf 'has_graphify=%s\n' "$(have_cmd graphify)"
printf 'has_rtk=%s\n' "$(have_cmd rtk)"
printf 'rtk_initialized=%s\n' "$RTK_INITIALIZED"
printf 'has_git=%s\n' "$(have_cmd git)"
printf 'has_brew=%s\n' "$(have_cmd brew)"
printf 'has_curl=%s\n' "$(have_cmd curl)"
