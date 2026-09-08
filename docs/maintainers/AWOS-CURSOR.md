# AWOS on Cursor (and Claude)

Maintainer guide for running [provectus/awos](https://github.com/provectus/awos) in this repo from **Cursor Agent** as well as Claude Code. Product runtime for end users is unchanged — this is contributor / maintainer agent workflow only ([#114](https://github.com/AlexanderMakarov/llm-wiki/issues/114)).

## Which harness loads what (and why a command looks "Cursor-only")

| Path | Claude Code | Cursor Agent |
|---|---|---|
| `.claude/commands/*.md` (top level) | loads | **loads** |
| `.claude/commands/<ns>/*.md` (nested) | loads, slash `/<ns>:<name>` | **does NOT load** |
| `.cursor/commands/*.md` (top level) | ignores | loads |
| `.claude/skills/`, `.claude/agents/` | loads | loads |

The split is **flat vs nested**, not Claude vs Cursor. A **top-level** `.claude/commands/<name>.md` is invocable from both harnesses out of that one file — it needs no duplicate anywhere. Only a **nested** namespace, `.claude/commands/<ns>/<name>.md`, is invisible to Cursor, and that is the single case that earns a flat `.cursor/commands/<ns>-<name>.md` wrapper.

### Symptom → cause

- **"a command works in Claude Code but not in Cursor"** → it is nested under `.claude/commands/<ns>/`. Add (or regenerate) the flat `.cursor/commands/<ns>-<name>.md` wrapper. Living under `.claude/` is not the problem.
- **"the slash does not appear in Cursor's `/` menu"** → check the file is top-level (`.claude/commands/<name>.md` or `.cursor/commands/<name>.md`, never a subdirectory), then reload the Cursor window so the command list is re-scanned.
- **"duplicating a top-level command into `.cursor/commands/` to make it work"** → unnecessary, because Cursor already loaded the original; the copy is only a second body to keep in sync, and `tests/test_command_surface_parity.py` fails on it.
- **"the Cursor slash name is wrong or collides"** → a converted plugin command kept its bare source filename (`flow.md` → `/flow`); prefix it with its source (`awos-flow.md` → `/awos-flow`).

### How to re-verify this

The table is empirical and **version-dependent** — measured against `cursor-agent` 2026.09.02 at time of writing. Anyone who suspects the model changed should re-run the probe rather than trust this page.

Drop a probe command file at the path under test inside a scratch repo (`<scratch-dir>`, e.g. `/tmp/probe`), invoke its slash, and **count `tool_call` events** in the stream:

```bash
cursor-agent --trust --mode ask -p "/<probe>" --output-format stream-json
```

- **Zero `tool_call` events** → the harness loaded the command and expanded it client-side. That location is a real command root.
- **Many `tool_call` events**, with the model narrating that it is looking up what the slash refers to → the harness did not load it. The model is merely searching the filesystem and happening to find the file.

A **negative control is mandatory**: put an identical probe file in a plain directory no harness could treat as a command root (say `<scratch-dir>/randomdir/`) and run the same probe. Without it, a naive probe "confirms" discovery from any location, because the agent finds and reads the file either way. Measuring the **outcome** (did the right token come back) is confounded; measuring the **mechanism** (tool-call count) is not.

[`tests/test_command_surface_parity.py`](../../tests/test_command_surface_parity.py) is the executable form of this rule: every nested namespace must keep its flat wrapper, and no top-level command may grow a redundant Cursor copy.

## Installer ≠ plugin

`bunx @provectusinc/awos` (or `npx @provectusinc/awos`) does **not** install the `awos` Claude plugin. The installer:

1. Inits the working tree
2. Creates `.awos/`, `context/`, …
3. Runs migrations
4. Copies `.awos/commands|templates|scripts` and thin `.claude/commands/awos/` wrappers
5. Adds `awos-recruitment` to project `.mcp.json`
6. Registers `awos-marketplace` → `provectus/awos` under `extraKnownMarketplaces` in `.claude/settings.json`

Enabling the optional plugin is a **separate** Claude Code step:

```text
/plugin install awos@awos-marketplace
```

That plugin ships audit + delivery-flow extras (`/awos:ai-readiness-audit`, `/awos:flow`), not the core `/awos:product|spec|tech|tasks|implement|verify` loop (those come from the file copy).

**Prefer `bunx` in this repo.** Fall back to `npx` only when bun is unavailable.

## Three layers

```mermaid
flowchart TB
  subgraph layerA [Layer A - Framework file copy]
    Installer["bunx @provectusinc/awos"]
    AwosDir[".awos/commands templates scripts"]
    ClaudeWrappers[".claude/commands/awos/"]
    Context["context/product + context/spec"]
    Installer --> AwosDir
    Installer --> ClaudeWrappers
    Installer --> Context
  end

  subgraph layerB [Layer B - Recruitment]
    Mcp["awos-recruitment MCP"]
    Cli["bunx @provectusinc/awos-recruitment skill|agent|mcp"]
    Hired[".claude/skills + .claude/agents"]
    Mcp --> HireCmd["/awos-hire"]
    HireCmd --> Cli
    Cli --> Hired
  end

  subgraph layerC [Layer C - Claude plugins]
    AwosPlugin["awos@awos-marketplace"]
    Official["superpowers / skill-creator / code-review"]
  end

  ClaudeWrappers -->|"thin ref + Cursor mapping"| CursorCmds[".cursor/commands/awos-*.md"]
  Hired -->|"Cursor native read"| CursorNative[".claude/skills and .claude/agents"]
  AwosPlugin -->|"Claude /plugin or acplugin"| CursorPluginPath["Cursor skills/commands/agents"]
  Official -->|"harness-native or Claude dual"| CursorPluginPath
```

### Slash names differ by harness

| Claude Code | Cursor Agent |
|---|---|
| `/awos:product` | `/awos-product` |
| `/awos:hire` | `/awos-hire` |
| `/awos:flow` (plugin) | `/awos-flow` (after Layer C sync) |
| `/awos:spec` … | `/awos-spec` … |

Cursor has **no** `/awos:` namespace. Project commands are the basename of a **top-level** file under `.cursor/commands/` (e.g. `awos-product.md` → `/awos-product`). Nested `.cursor/commands/awos/*.md` works in some IDE builds but **not** in Cursor Agent CLI — keep wrappers flat. **Always prefix** converted plugin commands with `awos-` (or another source prefix) so slash names show where they came from — raw acplugin leaves `flow.md` → `/flow`, which is easy to miss and collide with.

The same flat-only rule holds across harnesses — see [Which harness loads what](#which-harness-loads-what-and-why-a-command-looks-cursor-only): Cursor reads top-level `.claude/commands/*.md` but never descends into `.claude/commands/<ns>/`, which is why the AWOS commands need these flat wrappers.

### What is committed vs local

| Path | Commit? | Why |
|---|---|---|
| `.awos/` | **yes** | Shared Layer A prompts/templates/scripts for the team |
| `.claude/commands/awos/` | **yes** | Claude thin wrappers (installer preserve-on-update) |
| `.cursor/commands/awos-*.md` | **yes** | Flat Cursor wrappers + Layer C commands (e.g. `awos-flow.md`) |
| `.cursor/skills/awos-*/` | **yes** (optional) | Prefixed plugin skills; regenerate with `--plugin` if omitted from git |
| `.cursor/agents/awos-*.md` | **yes** (optional) | Prefixed plugin agents |
| `.cursor/rules/awos-cursor-runtime.mdc` | **yes** | Always-on Claude→Cursor tool map |
| `.mcp.json` | **yes** | Claude Code recruitment MCP entry |
| `.cursor/mcp.json` | **yes** | Cursor project MCP (Cursor does not load root `.mcp.json`) |
| `.claude/settings.json` | **yes** | Marketplace registration only |
| `context/` | **yes** | AWOS product/spec working docs (`product-definition.md`, roadmap, specs, …) — team source of truth for the loop |
| Repo-root `commands/` `skills/` `agents/` `.cursor-plugin/` | **no** | Transient acplugin dumps — gitignored; relocated by sync script |

## Layer A — framework file copy

### First install / update

```bash
./scripts/update-awos.sh              # Layer A only
./scripts/update-awos.sh --plugin     # Layer A + Layer C (marketplace plugin → prefixed .cursor/)
./scripts/update-awos.sh --plugin-only
# or:
#   bunx @provectusinc/awos && ./scripts/sync-awos-cursor-commands.sh
#   ./scripts/sync-awos-plugin-cursor.sh
```

- Source of truth for prompts: `.awos/commands/*.md` (always overwritten on update — do not hand-edit).
- Claude wrappers: `.claude/commands/awos/*.md` — customize here; installer preserves them on update. Slash stays `/awos:product`.
- Cursor Layer A wrappers: **generated** flat `.cursor/commands/awos-*.md` by `scripts/sync-awos-cursor-commands.sh`.
- Cursor Layer C (plugin): **generated** by `scripts/sync-awos-plugin-cursor.sh` — acplugin into a temp dir, then relocate to `.cursor/commands/awos-flow.md`, `.cursor/skills/awos-*/`, `.cursor/agents/awos-*.md` (drops `dist/`). Never leave bare `/flow`.


### Runtime mapping (Cursor)

See [`.cursor/rules/awos-cursor-runtime.mdc`](../../.cursor/rules/awos-cursor-runtime.mdc):

| Claude | Cursor |
|---|---|
| `AskUserQuestion` | Native `AskQuestion` when it is already a first-class tool this turn (invoke by name, same as `Read` / `Shell`). **Never** `CallDynamicTool` with `namespace: cursor` and `toolName: AskQuestion` — the `cursor` namespace is only `CreateGoal`, `GenerateImage`, `UpdateGoal`. If native `AskQuestion` is not injected (Auto / some models), use a numbered list in chat |
| `Agent(subagent_type=…)` | `Task(subagent_type=…)` |
| `general-purpose` | `generalPurpose` |
| Project `.claude/agents/*.md` | Keep kebab-case `subagent_type` |
| `awos-recruitment` tool `search` | Real tool name: `search_capabilities` |
| `/awos:product` | `/awos-product` |

Flat Cursor wrappers repeat that rule so slash-command context does not probe `CallDynamicTool` `cursor`/`AskQuestion` (that call fails with `Tool "AskQuestion" not found in namespace "cursor"`). Native `AskQuestion` is still the structured picker when the host injects it; Cursor's on-demand `cursor` MCP namespace is a different bag of tools and does not include it. Working notes: [`context/spec/011-awos-cursor-askquestion-dispatch/functional-spec.md`](../../context/spec/011-awos-cursor-askquestion-dispatch/functional-spec.md).

## How to install into Cursor

### `awos-recruitment` (MCP — Layer B)

This is an **HTTP MCP server**, not a Cursor `/add-plugin` package. The project already ships the config:

[`/.cursor/mcp.json`](../../.cursor/mcp.json) → `url`: `https://recruitment.awos.provectus.pro/mcp`

1. Open this repo in Cursor (project MCP is loaded from `.cursor/mcp.json`).
2. **Cursor Settings → Tools & MCP** (wording may vary slightly by version).
3. Find **`awos-recruitment`**, enable/approve it if prompted.
4. Reload the window if it does not appear after a fresh clone.
5. Smoke: in Agent, tools for that server should include `search_capabilities` (not `search`).

Claude Code uses the sibling root [`.mcp.json`](../../.mcp.json) instead; if recruitment is disabled there under `disabledMcpjsonServers`, remove that disable entry.

Optional CLI (no MCP UI required for install of hired skills once you know names):

```text
bunx @provectusinc/awos-recruitment skill|agent|mcp <names...>
```

### `awos` plugin (Layer C — audit / flow extras)

The Claude marketplace plugin (`awos@awos-marketplace`) is **not** Cursor-native and is **not** an MCP server (`agent mcp enable awos` will fail — that is expected).

**Claude Code (native):**

```text
# after ./scripts/update-awos.sh (registers awos-marketplace in .claude/settings.json)
/plugin install awos@awos-marketplace
# then /awos:flow , /awos:ai-readiness-audit (skill)
```

**Cursor (harness — preferred):**

```bash
./scripts/update-awos.sh --plugin-only
# or full: ./scripts/update-awos.sh --plugin
```

This runs acplugin, then **prefixes and relocates** into paths Agent actually loads:

| Claude | Cursor path | Slash / skill |
|---|---|---|
| `/awos:flow` | `.cursor/commands/awos-flow.md` | **`/awos-flow`** |
| ai-readiness-audit skill | `.cursor/skills/awos-ai-readiness-audit/` | skill name prefixed |
| repo-auditor agent | `.cursor/agents/awos-repo-auditor.md` | prefixed |

Do **not** stop at a bare `bunx @disdjj/acplugin … --to cursor` in the repo root — that leaves `commands/flow.md` (→ `/flow` if moved raw) outside `.cursor/` so Agent never sees it. If you already dumped to the repo root, `./scripts/sync-awos-plugin-cursor.sh --relocate-only` fixes it.

Reload Agent after sync. Keep the runtime tool-map rule — **acplugin does not rewrite** tool names in bodies.

There is no `/add-plugin awos` for Cursor. Core product→verify loop does **not** require this plugin (Layer A + B are enough).

### Prefix policy for other Claude plugins (skill-creator, etc.)

acplugin always uses the **source filename / skill dirname** with **no marketplace prefix**. After convert you should rename the same way we do for AWOS (`skill-creator-…`, `code-review-…`) before committing under `.cursor/`, or wrap the convert in a small script modeled on `sync-awos-plugin-cursor.sh` (`PREFIX=skill-creator`). Otherwise slash names collide and lose provenance.
## Layer B — recruitment MCP / CLI

### MCP

- Claude Code: root [`.mcp.json`](../../.mcp.json) (`type: http` + URL).
- Cursor: [`.cursor/mcp.json`](../../.cursor/mcp.json) (`url` only — Cursor auto-detects remote transport).

See [How to install into Cursor](#how-to-install-into-cursor) above for the enable steps.

Verified smoke (HTTP): `initialize` returns server `AWOS Recruitment`; `tools/list` exposes `search_capabilities`; a sample `tools/call` with query like `python testing pytest` returns ranked skills (e.g. `pytest-best-practices`).

### CLI hire path

```text
bunx @provectusinc/awos-recruitment skill <name1> [name2 ...]
bunx @provectusinc/awos-recruitment agent <name1> [name2 ...]
bunx @provectusinc/awos-recruitment mcp <name1> [name2 ...]
```

Outputs land in `.claude/skills/`, `.claude/agents/`, and `.mcp.json`. Cursor already reads skills and agents from `.claude/`. Prefer discovering names via MCP `search_capabilities`, then installing with the CLI (or letting `/awos-hire` drive both).

## Layer C — `awos@awos-marketplace` plugin

| Harness | Path |
|---|---|
| Claude Code | `/plugin install awos@awos-marketplace` → `/awos:flow` |
| Cursor | `./scripts/update-awos.sh --plugin` (or `--plugin-only`) → **`/awos-flow`** under `.cursor/commands/` |

## Companion plugins (per harness)

Do **not** assume Claude `/plugin` works inside Cursor.

| Plugin | Claude Code | Cursor |
|---|---|---|
| [Superpowers](https://github.com/obra/superpowers) | `/plugin install superpowers@claude-plugins-official` | First-class: `/add-plugin superpowers` |
| Skill Creator (Anthropic official) | `/plugin install skill-creator@claude-plugins-official` | acplugin + **manual/source prefix** (same idea as `awos-`); or keep Claude for authoring |
| Code Review (Anthropic official `code-review`) | `/plugin install code-review@claude-plugins-official` | Same as skill-creator, or use this repo's review surfaces |

## Update story

```bash
./scripts/update-awos.sh              # Layer A
./scripts/update-awos.sh --plugin     # Layer A + Layer C plugin refresh
./scripts/sync-awos-plugin-cursor.sh  # Layer C only
```

Do **not** rely on a one-off flatten or a raw acplugin dump at the repo root. Layer A: installer never writes `.cursor/`. Layer C: acplugin must be followed by prefix relocate (the sync script).

Details:

1. `bunx @provectusinc/awos` (or `npx`) refreshes `.awos/**`. Claude wrappers under `.claude/commands/awos/` are preserve-on-update.
2. `./scripts/sync-awos-cursor-commands.sh` writes flat Layer A `awos-<name>.md` → `/awos-<name>`.
3. `./scripts/sync-awos-plugin-cursor.sh` runs acplugin and relocates to prefixed `.cursor/commands|skills|agents` (excludes skill `dist/`).
4. Re-run Layer C after AWOS **plugin** version bumps; Layer A after installer package bumps.
## Smoke checklist

- [ ] `./scripts/update-awos.sh` completes without error on a clean or existing tree.
- [ ] Cursor slash **`/awos-flow`** appears after `./scripts/update-awos.sh --plugin` (not `/flow`, not `/awos:flow`).
- [ ] Cursor slash `/awos-product` appears in the `/` menu and loads `.awos/commands/product.md`; when native `AskQuestion` is in the first-class tool list, the agent **calls it by name** (not `CallDynamicTool` `cursor`/`AskQuestion`, not a prose numbered list first). If it is not injected, the agent uses a numbered list in chat. Typing Claude's `/awos:` must not be expected to resolve.
- [ ] `awos-recruitment` appears under Cursor Tools & MCP; `search_capabilities` returns results.
- [ ] `/awos-hire` (or CLI) can install one skill; the skill directory is visible under `.claude/skills/` to Cursor.
- [ ] No personal vault paths or usernames in committed AWOS docs or PR text.
- [ ] After a second `./scripts/update-awos.sh`, wrappers still resolve (sync is idempotent).
- [ ] A top-level `.claude/commands/*.md` command (e.g. `/release`) resolves in Cursor with no `.cursor/` duplicate of it present.

## Out of scope (still)

- Changing AWOS upstream to be Cursor-native
- Replacing this repo's wiki slash commands (`/wiki-*`) with AWOS
- Auto-syncing Claude plugin updates into Cursor without a manual refresh
