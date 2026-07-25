#!/usr/bin/env bash
# llmwiki — one-click installer for macOS / Linux.
#
# Usage: ./setup.sh
# Idempotent — safe to re-run.

set -eu
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> llmwiki setup"
echo "    root: $SCRIPT_DIR"

# 1. Python check
if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required but was not found in PATH" >&2
  exit 1
fi
PY_VER=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "    python: $PY_VER"

# 2. Check for markdown package
# #sec-18 (#562): pin to the same version floor as pyproject.toml so a
# fresh setup never installs a markdown wheel older than llmwiki's
# tested baseline. Bump both files together when the floor moves.
if ! python3 -c "import markdown" 2>/dev/null; then
  echo "==> installing python 'markdown' (required)"
  python3 -m pip install --user --quiet 'markdown>=3.9' 2>&1 | tail -2 || true
fi

# 3. Syntax highlighting (v0.5): highlight.js loads from CDN at view time,
#    so there is no longer an optional Python dep to install here.

# 4. Scaffold raw/ wiki/ site/ — but only into a configured vault.
# #29: never grow personal data (raw/ wiki/ site/) inside the git clone.
# `llmwiki init` honors config.json vault.default_path; if none is set it
# would scaffold into this repo, so we warn and skip instead.
VAULT_PATH=$(python3 - <<'PY'
import json
from pathlib import Path
path = ""
cfg = Path("config.json")
if cfg.exists():
    try:
        path = ((json.loads(cfg.read_text(encoding="utf-8")).get("vault") or {})
                .get("default_path") or "")
    except Exception:
        path = ""
print(path)
PY
)
if [ -n "$VAULT_PATH" ]; then
  echo "==> scaffolding into vault: $VAULT_PATH"
  # Don't let a scaffold failure (e.g. an unreachable/unmounted vault path)
  # abort the rest of setup under `set -e` — the adapters/status diagnostics
  # below are what the user needs to diagnose it.
  python3 -m llmwiki init || \
    echo "    (init did not complete — run 'llmwiki init' once the vault path is reachable)"
else
  echo
  echo "==> no vault configured (config.json vault.default_path is unset)."
  echo "    Skipping scaffold so raw/ wiki/ site/ do NOT grow inside this git clone."
  echo "    Create a vault directory, point config.json at it, then run 'llmwiki init':"
  echo "    docs/getting-started.md#2-create-a-vault-and-point-configjson-at-it"
fi

# 5. Show available adapters
python3 -m llmwiki adapters

# 6. First sync (status probe so users see how many sessions exist
#    without actually converting them yet)
echo
echo "==> sync status:"
python3 -m llmwiki sync --status || true

# 7. Git hooks — ruff on pushed Python files only
if git rev-parse --git-dir >/dev/null 2>&1; then
  echo
  echo "==> wiring git hooks (.githooks)"
  git config core.hooksPath .githooks
else
  echo
  echo "    (not a git checkout — skipping hook wiring)"
fi

echo
echo "================================================================"
echo "  Setup complete."
echo "================================================================"
echo
echo "Next steps:"
echo "  ./sync.sh                   # convert new sessions to markdown"
echo "  ./build.sh                  # generate the static HTML site"
echo "  ./serve.sh                  # browse at http://127.0.0.1:8765/"
echo
echo "Manual queue (no auto-sync on agent launch):"
echo "  python3 -m llmwiki queue status"
echo "  python3 -m llmwiki queue run --limit 20"
echo "  python3 scripts/migrate_state_v1_4_0.py   # one-time legacy state migration"
echo "  # or: python3 -m llmwiki migrate-state"
