# Technical Specification: Refresh competitor landscape docs + demo sync

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** Alexander Makarov

---

## 1. High-Level Technical Approach

Docs-only product change plus a standard demo corpus refresh. No `llmwiki/` runtime code, no new CLI surface, no schema migration.

1. Promote the fresher maintainer draft (`tmp/competitor-landscape.md` on the operator machine — gitignored / outside the shipped tree) into `docs/competitor-landscape.md`, aligned with the README Agents table (11 adapters) and current runtime baseline (Python 3.12+, `markdown` only). Rebuild the comparison as one table of the closest active wiki peers, plus short notes under it for active-but-different tools. Drop tools with no public product change since 2026-09-21.
2. Fix the stale flat-vs-subdir path hint on the English getting-started sync comment.
3. Point the worktree’s gitignored `config.json` at throwaway vault **and** merge the primary checkout’s `synthesis` (and any other non-vault) sections so `scripts/refresh_demo.py` can reach a backend — without copying `vault.default_path`.
4. Run `python3 scripts/refresh_demo.py` from the worktree so the modified doc plans as remove→add for slug `competitor-landscape`, re-synths only that doc, rebuilds `demo/site`, advances `demo/.demo-source-rev`, and leaves lint clean.
5. Record the user-visible refresh under `CHANGELOG.md` `[Unreleased]` and a short AWOS flow-log note (this PR touches `docs/` + `demo/` + `context/`; product `llmwiki/` paths are unchanged, so the AWOS context CI gate is satisfied by the spec dir).

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Documentation edits

| Path | Responsibility |
|---|---|
| `docs/competitor-landscape.md` | Replace stale rows/bullets with the tmp draft’s corrections: input-sources list, multi-agent **11**, positioning bullet (core+contrib agents, README pointer), Karpathy page-kinds list without retired comparison/question kinds, Python **3.12+** + single `markdown` runtime dep. Keep the page and the `docs/index.md` link. Rebuild the comparison as specified below. |
| `docs/getting-started.md` | Change the sync comment path from `<vault>/raw/sessions/<project>/*.md` to flat `<vault>/raw/sessions/*.md` (or equivalent wording matching `CLAUDE.md` / convert’s `flat_output_name`). |
| `docs/i18n/*/getting-started.md` | **Out of scope** for this PR — i18n scaffolds are best-effort / stale since v0.3 (`docs/i18n/README.md`); no CI forces same-PR sync. |
| `docs/getting-started.md` “6 agents” aside (~L235) | **Out of scope** unless approved below — same stale count as the competitor page had, but a different section; fixing it is a one-line drive-by that can wait for a dedicated docs pass. |

**Assumption:** Canonical agent count for marketing tables is the README Agents table (**11** named adapters). PDF remains an *input via `add`*, not a twelfth sync adapter — match the tmp draft’s wording.

### Comparison layout

Activity window: last public product change on or after **2026-09-21** (checked 2026-10-21). Write product shape only. Do not copy star counts, recall rates, or “#1” claims.

**Table columns** — this project plus the two peers that also compile a Karpathy-style wiki a person reads. Replace the mem0 / Rewind / Pieces / manual-notes columns. Do not add a second table.

| Column heading | What the cells compare | Link |
|---|---|---|
| llmwiki | This repository. | — |
| llmwiki (lucasastorian) | The other project’s functions, cell by cell. The author in the heading only stops the two “llmwiki” columns from looking like the same product. Pushed 2026-10-20. | https://github.com/lucasastorian/llmwiki |
| Karpathy LLM Wiki (Obsidian) | The plugin’s functions, cell by cell (`karpathywiki`, repo `GD4AI/obsidian-llm-wiki`). Pushed 2026-10-21. | https://community.obsidian.md/plugins/karpathywiki |

**Function rows** (replace the old mem0 / Rewind / Pieces rows). Each cell is a concrete behavior, not “see their README”.

| Row | This project | llmwiki (lucasastorian) | Karpathy LLM Wiki (Obsidian) |
|---|---|---|---|
| What it compiles | Coding-agent session transcripts, plus docs you add | Documents, web clips, highlights, Office/PDF uploads | Notes and files already in an Obsidian vault (markdown, PDF, images, Office) |
| Where you read it | Static HTML site you open as files or publish | Next.js app (local loopback or llmwiki.app) | Inside Obsidian (wiki pages + side-panel query) |
| How it stays current | `sync` / `synth` on the machine (you run it, or a scheduler) | Capture as you read; optional nightly Claude routine | Ingest from the plugin; query in the editor |
| Runs without their cloud | Yes | Local mode is loopback-only; hosted app is optional | Plugin is local; an LLM provider can be local (Ollama) or a cloud API |
| What you install | Python 3.12+ and the `markdown` package | Python and Node, plus a web app | Obsidian, then the community plugin, then an LLM provider |
| Agent sessions | Adapters read Claude Code, Codex, Cursor, and the other README agents | MCP so Claude (and other MCP clients) can write the wiki; not a session-store compiler | No session-store sync; the vault is the source |
| Graph / links | Wikilinks and a generated graph view | Cross-links and a graph viewer | Wikilinks, Obsidian’s graph, retrieval over those links (no vector database) |

Keep one short “when to choose which” paragraph after the table for these three only. Drop rows that only existed to contrast Rewind or Pieces (screen recording, snippet manager, subscription price).

**Under the table** — still not a second grid. Each paragraph names the function: mem0 stores and retrieves memories for an application over an API; agentmemory writes memory back into the next coding-agent session; TencentDB Agent Memory shares chat memory, skills, a wiki, and a code graph across a team through a proxy. Say that none of those three is a personal wiki you compile from session files and open as a static site.

**Under the table** — one short paragraph and a link each. No columns, no feature grid.

| Tool | Note | Freshness | Link |
|---|---|---|---|
| mem0 | Memory API for applications and agents, not a browsable wiki. | `mem0ai/mem0` pushed 2026-10-21 | https://github.com/mem0ai/mem0 |
| agentmemory | Memory injected back into coding agents for the next session. | pushed 2026-10-20 | https://github.com/rohitg00/agentmemory |
| TencentDB Agent Memory | Team memory service (chat memory, skills, an LLM wiki, a code graph) shared across agents through a proxy. | pushed 2026-10-21 | https://github.com/TencentCloud/TencentDB-Agent-Memory |

**Remove**

| Tool | Why |
|---|---|
| Rewind / Limitless | Screen recorder shut down December 2025 (Limitless acquired; Rewind capture disabled 2025-12-19). The 2026 “Rewind” changelog is a different company (SaaS backups). |
| Pieces | Product updates page: last entry 2026-05-01. No September/October 2026 release. |
| Manual notes column | Not a versioned tool. One sentence may remain under “When llmwiki is NOT the right tool” for the few-sessions case. |

### Worktree config for refresh

- Keep `vault.default_path` → `$WT/.worktree-vault`.
- Merge from primary gitignored `config.json`: at least `synthesis` (operator currently uses `backend: claude`). Do not copy primary `vault`.
- Drive all commands as `python3 -m llmwiki` / `python3 scripts/refresh_demo.py` from `$WT`.

### Demo refresh

- After the docs commit is in the worktree working tree (or staged), `python3 scripts/refresh_demo.py --dry-run` must show remove+add for `docs/competitor-landscape.md`.
- Real run: `python3 scripts/refresh_demo.py` — uses `demo/` only; does not mutate the live Obsidian vault.
- Coverage gate must pass for slug `competitor-landscape` before the pin advances; on interrupt use `--resume`, never re-run full refresh after removes already applied.
- Expect updates under `demo/raw/docs/competitor-landscape/`, matching `demo/wiki/sources/competitor-landscape/`, and incidental catalog/state touch-ups (`demo/wiki/index.md`, `demo/llmwiki-state.json`, possibly Obsidian entity `sources:` if synth rewrites them). Prefer the refresh script over hand-editing `demo/raw/` (immutable rule).

### CHANGELOG / context

- `CHANGELOG.md` under `[Unreleased]`: *Changed* (or edit an existing Unreleased docs bullet if one already covers this page) — competitor landscape facts refreshed; getting-started sync path hint corrected.
- Spec artifacts stay under `context/spec/220-demo-drop-competitor-landscape/` (name kept for ticket continuity even though delivery is update-not-drop).

### Non-goals (tech)

- No changes under `llmwiki/`, no new tests required solely for prose (no test asserts `competitor-landscape` by name). Existing `tests/test_refresh_demo.py` uniqueness invariants must still pass after refresh.
- Do not revive `/vs/` (#138).

---

## 3. Impact and Risk Analysis

- **System Dependencies:** Reachable synthesis backend in worktree config; git working copy (refresh cannot run from a tarball). Demo is a CI fixture — bad refresh breaks wiki-checks / lint on `demo/`.
- **Risks & Mitigations:**
  - **Stale agent count elsewhere** — leaving getting-started “6 agents” creates intentional partial consistency; call it out in the PR body if left out of scope.
  - **Synth rate-limit / incomplete coverage** — script refuses to advance `.demo-source-rev`; use `--resume` / re-run path-scoped synth until coverage passes.
  - **Hand-editing demo raw** — forbidden; always go through remove/add via refresh.
  - **Copying primary `config.json` wholesale** — would aim agents at the live vault; merge non-vault keys only.
  - **Issue #220 auto-close** — PR should use `Closes #220` because the corrected acceptance (update + demo sync + path hint) fully delivers what we now treat as the issue’s real intent; note the premise correction in the PR Summary.

---

## 4. Testing Strategy

- [ ] `python3 scripts/refresh_demo.py --dry-run` shows the expected competitor-landscape remove→add plan before the real run.
- [ ] After refresh: `python3 -m llmwiki lint --vault demo` — no new broken links/orphans from this change.
- [ ] Spot-read updated `docs/competitor-landscape.md` vs README Agents table for count/list agreement.
- [ ] `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q` (full suite before push; expect green with no new product tests).
- [ ] Optional: `python3 -m pytest tests/test_refresh_demo.py -q` after refresh if the full suite is slow mid-loop.
