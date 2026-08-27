# Agent workflow alternatives (Cursor-ready SDD)

Comparison of frameworks in the same class as [provectus/awos](https://github.com/provectus/awos) that support **Cursor Agent / Cursor CLI** out of the box. Context: [#114](https://github.com/AlexanderMakarov/llm-wiki/issues/114) (Cursor-compatible AWOS install). Product runtime for end users is unchanged — this is contributor / maintainer agent-workflow research only.

AWOS itself is Claude-first (file copy + marketplace + recruitment MCP). This repo adapts it for Cursor via flat `/awos-*` wrappers, a runtime tool-map rule, dual MCP paths, and optional [acplugin](https://github.com/TokenRollAI/acplugin) for non–Cursor-native plugins — see [`AWOS-CURSOR.md`](AWOS-CURSOR.md) and the compatibility section of [#114](https://github.com/AlexanderMakarov/llm-wiki/issues/114). The tools below already treat Cursor as a first-class install target (no Claude shim required for their core loop).

Star counts below are approximate snapshots from 2026-08-02 and drift quickly — use them only as relative popularity signal.

## Why “Cursor-ready” matters (lessons from #114)

A Claude-shaped install is not enough for Cursor Agent:

| Pitfall | Effect |
|---|---|
| Claude slash `/awos:name` | Does **not** resolve in Cursor — Agent uses filename basenames (`/awos-name`) |
| Nested `.cursor/commands/awos/*.md` | Agent CLI often **skips** subfolders; use **flat** `.cursor/commands/awos-*.md` |
| Root `.mcp.json` only | Cursor reads **`.cursor/mcp.json`** for project MCP |
| Prompt bodies saying `AskUserQuestion` / `Agent(...)` | Still Claude tool names — need a runtime map; `AskUserQuestion` → native `AskQuestion` when injected, never `CallDynamicTool` `cursor`/`AskQuestion`; **acplugin does not rewrite** them |
| Claude `/plugin install` | Does not install into Cursor; use Cursor-native (`/add-plugin`) or acplugin for Layer C |

Frameworks that write Cursor-flat commands / skills at init avoid most of that tax. AWOS in this repo pays it via wrappers + docs.

## Landscape

| Framework | Cursor OOB? | Core loop | Closest to AWOS? |
|---|---|---|---|
| **[OpenSpec](https://github.com/Fission-AI/OpenSpec)** (~63k★) | Yes — `openspec init` writes flat `/opsx-*` for Cursor | propose → apply → archive (specs as change deltas) | Medium — lighter SDD |
| **[Spec Kit](https://github.com/github/spec-kit)** (~125k★) | Yes — `--ai cursor-agent` → `.cursor/skills`; headless `cursor-agent -p --trust …` | constitution → specify → plan → tasks → implement | High — gated SDD |
| **[GSD Core](https://github.com/open-gsd/gsd-core)** (~8k★; formerly get-shit-done) | Yes — installer `--cursor` | discuss → plan → execute → verify (phases + `.planning/`) | High — execution-heavy |
| **[BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD)** (~51k★) | Yes — `--tools cursor` (preferred IDE) | Analyst/PM/Architect → SM stories → Dev/QA | Highest ceremony |
| **[Superpowers](https://github.com/obra/superpowers)** (~265k★) | Yes — Cursor-native `/add-plugin` | brainstorm → plan → TDD → subagent exec → review | Complementary (discipline, not product→roadmap) |
| **[Trellis](https://github.com/drewdoebereiner/trellis)** | Yes — copy skills into `.cursor/skills/` | backlog → implement → review → merge (cron-friendly) | Different layer (bulk ship) |
| **AWOS** ([#114](https://github.com/AlexanderMakarov/llm-wiki/issues/114)) | Partial — Claude installer + **this repo’s** flat `/awos-*`, runtime rule, `.cursor/mcp.json`; Layer C via acplugin except Cursor-native | product → roadmap → hire → spec → tech → tasks → implement → verify | Baseline |

Community note: older **get-shit-done-cursor** forks exist; prefer official **[@opengsd/gsd-core](https://www.npmjs.com/package/@opengsd/gsd-core)** with `--cursor`.

## Feature comparison

| Dimension | AWOS | OpenSpec | Spec Kit | GSD | BMAD | Superpowers | Trellis |
|---|---|---|---|---|---|---|---|
| **Product / vision docs** | Strong (`/product`, `/roadmap`, `/architecture`) | Weak (per-change only) | Medium (constitution) | Strong (`PROJECT.md`, roadmap, milestones) | Strongest (PRD + architecture agents) | Weak | Medium (roadmap/tickets) |
| **Durable specs** | Per-feature under `context/` | `openspec/specs/` + change deltas | Spec/plan/tasks artifacts | `.planning/` phase artifacts | Story files with full context | Plan in chat/files | Ticket-driven |
| **Task breakdown** | Vertical slices + agent tags | `tasks.md` checklist | `/speckit.tasks` | Phase plans, parallel waves | Hyper-detailed SM stories | Plan tasks | Backlog pull |
| **Subagent orchestration** | Yes + **`/hire` recruitment MCP** | Light | Moderate | Core design (fresh context per wave) | Persona agents | Subagent-driven-dev | Parallel bulk agents |
| **Capability hiring (skills/MCP)** | Unique strength (`awos-recruitment`) | No | No | Installer ships agents/skills | Expansion packs / modules | Plugin skills | Skills are the product |
| **Verify / UAT gate** | `/verify` vs acceptance criteria | `/opsx:verify` (expanded profile) | analyze / checklist / converge | `/gsd-verify-work` | QA agent | verification skills | Review + comment resolve |
| **Brownfield onboard** | Manual context | `/opsx:onboard` | Yes | `/gsd-onboard` | Planning workflows | Map via skills | Assumes tickets exist |
| **Multi-harness** | Claude-primary; Cursor via #114 adapters | 30+ tools | 30+ agents | Many runtimes via installer transforms | Many IDEs | Many harnesses | Skill-copy agnostic |
| **Headless Cursor CLI** | Not designed for it; flat `/awos-*` help Agent | Chat-oriented | Explicit `specify workflow run` + `cursor-agent` | Slash in Agent; installer-aware | IDE slash/skills | Skills in Agent | Skills in Agent |
| **Update story** | `./scripts/update-awos.sh` (installer + Cursor wrapper regen); acplugin re-run for converted Layer C only | `openspec update` regenerates tool files | `specify` upgrade path | Re-run installer | `bmad-method install --action update` | Plugin bump | Re-copy skills |
| **Tool-name portability** | Runtime rule required; acplugin does **not** rewrite prompt tools | Cursor-oriented prompts from init | Cursor skills from init | Installer transforms | Cursor tool files from install | Cursor-native plugin | Skill copy as-is |

## Learning curve (low → high)

1. **Superpowers** — Install plugin; agent self-triggers skills. Little ceremony; learn by doing. Not a product/roadmap system.
2. **OpenSpec** — Three commands for most work (`explore` / `propose` / `apply` / `archive`). Fastest path to “spec before code” with durable repo artifacts. Cursor naming (`/opsx-propose`) handled by init.
3. **GSD** — More commands and `.planning/` state, but the loop is repetitive (discuss → plan → execute → verify). Steeper than OpenSpec because of phases, waves, and “clear context between steps,” still aimed at solo flow.
4. **Spec Kit** — Explicit phase gates and more Markdown. Heavier than OpenSpec; GitHub-backed docs help. Best if you want a standard, rigid SDD pipeline including optional headless Cursor CLI.
5. **AWOS** — Clear chain, but product/roadmap/architecture prerequisites plus hire/MCP/plugins. On Cursor, #114 adds harness complexity (flat commands, tool map, dual MCP, acplugin for some plugins).
6. **BMAD** — Full agile org simulation (many agents, modules, story ceremony). Highest process overhead; strongest for greenfield / multi-role planning.
7. **Trellis** — Concepts are simple (six SDLC skills), but the operating model assumes ticket systems, cron, and “bulk unattended” — a different skill set than interactive SDD.

## Fit vs #114

If the goal is **“Cursor Agent CLI works without a Claude shim”**:

- **Best drop-in SDD:** **OpenSpec** — intentionally generates Cursor-flat commands; lightest learning curve for change-scoped work.
- **Best full pipeline + headless Cursor:** **Spec Kit** — first-class `cursor-agent` integration and CLI workflow dispatch.
- **Best execution / context-rot focus:** **GSD Core** — official `--cursor` installer; phase loop with parallel subagents.
- **Best planning ceremony / greenfield:** **BMAD** — Cursor preferred; heavyweight.
- **Best complement, not replacement:** **Superpowers** — Cursor-native Layer C in #114; pairs with any of the above (Trellis markets that pairing). Skip acplugin for Superpowers.

**What only AWOS really owns:** recruitment (`/hire` + MCP marketplace of skills/agents). OpenSpec / Spec Kit / GSD do not replace that; you would still hire skills by hand or keep AWOS Layer B.

**acplugin** is the general path for **non–Cursor-native Claude plugins** (layout/frontmatter → `.cursor/`). It does **not** replace Layer A wrappers, does **not** rewrite Claude tool names in skill/command bodies, and is one-shot (re-run on upstream bumps). Details: [`AWOS-CURSOR.md`](AWOS-CURSOR.md) and [#114](https://github.com/AlexanderMakarov/llm-wiki/issues/114).

**Practical stance for this repo:** keep AWOS for the product→hire→verify chain adapted in #114 (committed flat `/awos-*` + runtime rule + MCP so clones work). If you want Cursor-native SDD without maintaining those adapters, spike **OpenSpec** (light) or **GSD** (heavier execution) on one small chore and compare artifact quality vs `/awos-*`. Prefer **Spec Kit** when headless `cursor-agent` CI/automation matters.

## Quick install pointers

| Tool | Typical install |
|---|---|
| OpenSpec | `npm i -g @fission-ai/openspec@latest` then `openspec init` (select Cursor) |
| Spec Kit | `uvx --from git+https://github.com/github/spec-kit.git specify init --ai cursor-agent` (see Spec Kit docs for current installer) |
| GSD Core | `npx @opengsd/gsd-core@latest --cursor --local` (or `--global`) |
| BMAD | `npx bmad-method install --tools cursor --yes` (plus modules as needed) |
| Superpowers | Cursor `/add-plugin superpowers` |
| Trellis | Copy skills into `.cursor/skills/` per project README |
| AWOS | `./scripts/update-awos.sh` (or `bunx @provectusinc/awos` + `./scripts/sync-awos-cursor-commands.sh`) — see [`AWOS-CURSOR.md`](AWOS-CURSOR.md) |

## Out of scope

- Replacing this repo’s wiki slash commands (`/wiki-*`) with any of the above.
- Changing AWOS upstream to be Cursor-native.
- Expecting acplugin alone to make Claude plugins behave as if they were written for Cursor tool APIs.
