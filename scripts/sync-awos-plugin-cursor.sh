#!/usr/bin/env bash
# Layer C: convert the AWOS marketplace plugin to Cursor paths with an `awos-` prefix.
#
# Why: acplugin drops Claude's `/awos:` namespace and often writes to repo-root
# `commands/`, `skills/`, `agents/` — Cursor Agent only loads `.cursor/commands/*.md`
# (and `.cursor/skills/`, `.cursor/agents/`). We want slash names like `/awos-flow`
# so AWOS plugin surfaces are obvious next to Layer A `/awos-product`, etc.
#
# Usage:
#   ./scripts/sync-awos-plugin-cursor.sh              # acplugin + relocate
#   ./scripts/sync-awos-plugin-cursor.sh --relocate-only
#       # relocate from repo-root dump or $AWOS_PLUGIN_STAGING
#
# Prefer bunx; fall back to npx.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PREFIX="${AWOS_CURSOR_PREFIX:-awos}"
RELOCATE_ONLY=0
if [[ "${1:-}" == "--relocate-only" ]]; then
  RELOCATE_ONLY=1
fi

run_acplugin() {
  local out="$1"
  mkdir -p "$out"
  if command -v bunx >/dev/null 2>&1; then
    bunx @disdjj/acplugin convert provectus/awos --path plugins/awos --to cursor -a -o "$out"
  elif command -v npx >/dev/null 2>&1; then
    npx @disdjj/acplugin convert provectus/awos --path plugins/awos --to cursor -a -o "$out"
  else
    echo "error: need bunx or npx to run @disdjj/acplugin" >&2
    exit 1
  fi
}

# Find a directory that contains converted plugin commands/skills/agents.
resolve_staging() {
  if [[ -n "${AWOS_PLUGIN_STAGING:-}" && -d "$AWOS_PLUGIN_STAGING" ]]; then
    echo "$AWOS_PLUGIN_STAGING"
    return
  fi
  # Fresh acplugin -o layout
  if [[ -d "$1/commands" || -d "$1/skills" || -d "$1/agents" ]]; then
    echo "$1"
    return
  fi
  # Nested .cursor/ under output
  if [[ -d "$1/.cursor/commands" || -d "$1/.cursor/skills" ]]; then
    echo "$1/.cursor"
    return
  fi
  # In-repo dump from a bare `acplugin convert … --to cursor` (cwd = ROOT)
  if [[ -f "$ROOT/commands/flow.md" || -d "$ROOT/skills/ai-readiness-audit" ]]; then
    echo "$ROOT"
    return
  fi
  echo "error: no acplugin staging found (pass --relocate-only after convert, or omit flag to convert)" >&2
  exit 1
}

inject_cursor_banner() {
  # $1 = file path; $2 = slash name e.g. awos-flow
  local file="$1"
  local slash="$2"
  python3 - "$file" "$slash" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
slash = sys.argv[2]
text = path.read_text(encoding="utf-8")
banner = (
    f"\n<!-- Cursor slash: /{slash}. "
    f"When the body says AskUserQuestion, call AskQuestion if available "
    f"(see .cursor/rules/awos-cursor-runtime.mdc). "
    f"Agent(…) → Task(…). -->\n"
)
if f"Cursor slash: /{slash}" in text:
    raise SystemExit(0)
if text.startswith("---"):
    end = text.find("\n---", 3)
    if end != -1:
        end += len("\n---")
        text = text[:end] + banner + text[end:]
    else:
        text = banner + text
else:
    text = banner + text
path.write_text(text, encoding="utf-8")
PY
}

relocate() {
  local staging="$1"
  local cmd_src skill_src agent_src

  if [[ -d "$staging/commands" ]]; then
    cmd_src="$staging/commands"
  elif [[ -d "$staging/.cursor/commands" ]]; then
    cmd_src="$staging/.cursor/commands"
  else
    cmd_src=""
  fi

  if [[ -d "$staging/skills" ]]; then
    skill_src="$staging/skills"
  elif [[ -d "$staging/.cursor/skills" ]]; then
    skill_src="$staging/.cursor/skills"
  else
    skill_src=""
  fi

  if [[ -d "$staging/agents" ]]; then
    agent_src="$staging/agents"
  elif [[ -d "$staging/.cursor/agents" ]]; then
    agent_src="$staging/.cursor/agents"
  else
    agent_src=""
  fi

  mkdir -p "$ROOT/.cursor/commands" "$ROOT/.cursor/skills" "$ROOT/.cursor/agents"

  local n_cmd=0 n_skill=0 n_agent=0

  if [[ -n "$cmd_src" ]]; then
    shopt -s nullglob
    for src in "$cmd_src"/*.md; do
      local base stem dest
      base="$(basename "$src")"
      stem="${base%.md}"
      # Avoid double prefix if already awos-flow.md
      if [[ "$stem" == "${PREFIX}-"* ]]; then
        dest="$ROOT/.cursor/commands/${stem}.md"
      else
        dest="$ROOT/.cursor/commands/${PREFIX}-${stem}.md"
      fi
      cp -f "$src" "$dest"
      inject_cursor_banner "$dest" "$(basename "$dest" .md)"
      echo "command  $(basename "$dest")  →  /$(basename "$dest" .md)"
      n_cmd=$((n_cmd + 1))
    done
    shopt -u nullglob
  fi

  if [[ -n "$skill_src" ]]; then
    shopt -s nullglob
    for src in "$skill_src"/*/; do
      local name dest
      name="$(basename "$src")"
      if [[ "$name" == "${PREFIX}-"* ]]; then
        dest="$ROOT/.cursor/skills/${name}"
      else
        dest="$ROOT/.cursor/skills/${PREFIX}-${name}"
      fi
      rm -rf "$dest"
      mkdir -p "$(dirname "$dest")"
      if command -v rsync >/dev/null 2>&1; then
        rsync -a --delete \
          --exclude dist/ \
          --exclude node_modules/ \
          --exclude .git/ \
          "$src" "$dest"
      else
        cp -a "$src" "$dest"
        rm -rf "$dest/dist" "$dest/node_modules"
      fi
      echo "skill    $(basename "$dest")/  →  .cursor/skills/$(basename "$dest")/"
      n_skill=$((n_skill + 1))
    done
    shopt -u nullglob
  fi

  if [[ -n "$agent_src" ]]; then
    shopt -s nullglob
    for src in "$agent_src"/*.md; do
      local base stem dest
      base="$(basename "$src")"
      stem="${base%.md}"
      if [[ "$stem" == "${PREFIX}-"* ]]; then
        dest="$ROOT/.cursor/agents/${stem}.md"
      else
        dest="$ROOT/.cursor/agents/${PREFIX}-${stem}.md"
      fi
      cp -f "$src" "$dest"
      inject_cursor_banner "$dest" "$(basename "$dest" .md)"
      echo "agent    $(basename "$dest")"
      n_agent=$((n_agent + 1))
    done
    shopt -u nullglob
  fi

  # Drop acplugin staging junk at repo root when we consumed it from ROOT.
  if [[ "$staging" == "$ROOT" ]]; then
    rm -rf "$ROOT/commands" "$ROOT/skills" "$ROOT/agents" "$ROOT/.cursor-plugin"
    echo "cleaned repo-root acplugin dump (commands/ skills/ agents/ .cursor-plugin/)"
  fi

  echo "Layer C relocate: ${n_cmd} command(s), ${n_skill} skill(s), ${n_agent} agent(s) under .cursor/ (prefix=${PREFIX}-)"
  if [[ "$n_cmd" -eq 0 && "$n_skill" -eq 0 ]]; then
    echo "warning: nothing relocated — check staging layout" >&2
    exit 1
  fi
}

STAGING_TMP=""
cleanup() {
  if [[ -n "$STAGING_TMP" && -d "$STAGING_TMP" ]]; then
    rm -rf "$STAGING_TMP"
  fi
}
trap cleanup EXIT

if [[ "$RELOCATE_ONLY" -eq 1 ]]; then
  STAGING="$(resolve_staging "$ROOT")"
else
  STAGING_TMP="$(mktemp -d "${TMPDIR:-/tmp}/awos-plugin-cursor.XXXXXX")"
  echo "acplugin → $STAGING_TMP"
  run_acplugin "$STAGING_TMP"
  STAGING="$(resolve_staging "$STAGING_TMP")"
fi

echo "staging: $STAGING"
relocate "$STAGING"
echo "Tip: reload Agent; slash /${PREFIX}-flow (not /flow, not /awos:flow)."
