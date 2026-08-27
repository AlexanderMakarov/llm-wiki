#!/usr/bin/env bash
# Regenerate flat Cursor AWOS slash commands from .awos/commands/*.md.
#
# Why: Cursor Agent resolves only top-level `.cursor/commands/*.md`
# (not nested `commands/awos/`). Claude's `/awos:name` namespace does not
# exist in Cursor — the slash name is `/awos-<name>` from the filename.
#
# After every AWOS install/update:
#   bunx @provectusinc/awos
#   ./scripts/sync-awos-cursor-commands.sh
#
# Safe to re-run; overwrites generated wrappers only.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/.awos/commands"
DST="$ROOT/.cursor/commands"

if [[ ! -d "$SRC" ]]; then
  echo "error: missing $SRC — run: bunx @provectusinc/awos" >&2
  exit 1
fi

mkdir -p "$DST"

# Remove previously generated wrappers (and any leftover nested tree).
rm -rf "$DST/awos"
shopt -s nullglob
for stale in "$DST"/awos-*.md; do
  rm -f "$stale"
done

written=0
for src in "$SRC"/*.md; do
  name="$(basename "$src" .md)"
  out="$DST/awos-${name}.md"

  # Prefer description from the AWOS command frontmatter.
  desc="$(
    python3 - "$src" <<'PY'
import re, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text(encoding="utf-8")
m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
if not m:
    print(f"AWOS command: {Path(sys.argv[1]).stem}")
    raise SystemExit(0)
block = m.group(1)
dm = re.search(r'^description:\s*(.+)$', block, re.M)
if not dm:
    print(f"AWOS command: {Path(sys.argv[1]).stem}")
    raise SystemExit(0)
val = dm.group(1).strip()
if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
    val = val[1:-1]
print(val)
PY
  )"

  hire_extra=""
  if [[ "$name" == "hire" ]]; then
    hire_extra="$(cat <<'EOF'

Recruitment specifics for this repo:

- Call the `awos-recruitment` MCP tool `search_capabilities` (not a tool named `search`).
- Prefer `bunx` for installs; fall back to `npx` only if `bun`/`bunx` is unavailable:

```text
bunx @provectusinc/awos-recruitment skill <names...>
bunx @provectusinc/awos-recruitment agent <names...>
bunx @provectusinc/awos-recruitment mcp <names...>
```

Hired skills/agents land under `.claude/skills/` and `.claude/agents/` — Cursor already reads those trees.

EOF
)"
  fi

  cat >"$out" <<EOF
---
description: ${desc}
---

# /awos-${name} (Cursor)

Follow \`.awos/commands/${name}.md\` as the source of truth (do not edit that file — the AWOS installer overwrites it).

Apply the tool mapping in \`.cursor/rules/awos-cursor-runtime.mdc\`.

**Multiple-choice interaction (strict):** when the AWOS prompt says \`AskUserQuestion\`, call native \`AskQuestion\` if it is already listed as a first-class tool this turn (invoke by name). Do **not** \`CallDynamicTool\` with \`namespace: cursor\` and \`toolName: AskQuestion\` — that tool is not in the cursor namespace. Use prose numbered choices **only** if native \`AskQuestion\` is missing. Never call \`AskUserQuestion\` (Claude-only name).
${hire_extra}
Optional user hint (if provided after the slash command): treat it as \`\$ARGUMENTS\` / the \`<user_prompt>\` in that command file.
EOF

  echo "wrote .cursor/commands/awos-${name}.md  →  /awos-${name}"
  written=$((written + 1))
done

echo "synced ${written} Cursor AWOS command(s) from .awos/commands/"
echo "Tip: in Agent, type /awos- (not /awos:) — reload the window if the menu is stale."
