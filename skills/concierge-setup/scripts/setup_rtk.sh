#!/usr/bin/env bash
set -euo pipefail

MODE="plan"
while [ $# -gt 0 ]; do
  case "$1" in
    --apply)
      MODE="apply"
      ;;
    --plan)
      MODE="plan"
      ;;
    *)
      echo "usage: setup_rtk.sh [--plan|--apply]" >&2
      exit 2
      ;;
  esac
  shift
done

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

CLAUDE_SETTINGS="${HOME}/.claude/settings.json"
RTK_PRESENT="false"
RTK_INITIALIZED="false"
INSTALL_METHOD="none"

if have_cmd rtk; then
  RTK_PRESENT="true"
fi

if [ -f "$CLAUDE_SETTINGS" ] && grep -qi '"rtk\|rtk ' "$CLAUDE_SETTINGS"; then
  RTK_INITIALIZED="true"
fi

echo "RTK_PRESENT ${RTK_PRESENT}"
echo "RTK_INITIALIZED ${RTK_INITIALIZED}"

if [ "$MODE" != "apply" ]; then
  if [ "$RTK_PRESENT" = "false" ]; then
    if have_cmd brew; then
      echo "PLAN_INSTALL brew"
    elif have_cmd curl; then
      echo "PLAN_INSTALL curl"
    else
      echo "PLAN_INSTALL unavailable"
    fi
  else
    echo "PLAN_INSTALL none"
  fi
  if [ "$RTK_INITIALIZED" = "false" ]; then
    echo "PLAN_INIT global"
  fi
  exit 0
fi

if [ "$RTK_PRESENT" = "false" ]; then
  if have_cmd brew; then
    INSTALL_METHOD="brew"
    brew install rtk
  elif have_cmd curl; then
    INSTALL_METHOD="curl"
    curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
  else
    echo "ERROR neither brew nor curl is available to install rtk" >&2
    exit 3
  fi
fi

echo "INSTALL_METHOD ${INSTALL_METHOD}"

if ! have_cmd rtk; then
  echo "ERROR rtk command still not found after install attempt" >&2
  exit 4
fi

if [ "$RTK_INITIALIZED" = "false" ]; then
  rtk init --global
fi

if [ -f "$CLAUDE_SETTINGS" ] && grep -qi '"rtk\|rtk ' "$CLAUDE_SETTINGS"; then
  RTK_INITIALIZED="true"
fi

echo "RTK_PRESENT true"
echo "RTK_INITIALIZED ${RTK_INITIALIZED}"
rtk gain || true
