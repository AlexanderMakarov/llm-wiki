#!/usr/bin/env bash
# Install or update AWOS for this repo (Cursor + Claude).
#
#   ./scripts/update-awos.sh              # Layer A only (installer + flat /awos-* wrappers)
#   ./scripts/update-awos.sh --plugin     # Layer A + Layer C (acplugin AWOS plugin → .cursor/ with awos- prefix)
#   ./scripts/update-awos.sh --plugin-only
#
# Prefer bunx; fall back to npx.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DO_A=1
DO_C=0
for arg in "$@"; do
  case "$arg" in
    --plugin) DO_C=1 ;;
    --plugin-only) DO_A=0; DO_C=1 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "unknown option: $arg (try --plugin or --plugin-only)" >&2
      exit 1
      ;;
  esac
done

run_installer() {
  if command -v bunx >/dev/null 2>&1; then
    bunx @provectusinc/awos
  elif command -v npx >/dev/null 2>&1; then
    npx @provectusinc/awos
  else
    echo "error: need bunx or npx to run @provectusinc/awos" >&2
    exit 1
  fi
}

if [[ "$DO_A" -eq 1 ]]; then
  run_installer
  "$ROOT/scripts/sync-awos-cursor-commands.sh"
fi

if [[ "$DO_C" -eq 1 ]]; then
  "$ROOT/scripts/sync-awos-plugin-cursor.sh"
fi
