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

**Table columns** — tools that persist memory for agents. Operator locked this on 2026-10-21 after rejecting a wiki-shaped table (lucasastorian and the Obsidian plugin do not ingest coding-agent session stores; the static site is observability, not the product). Do not add a second table.

| Column | Link | Freshness |
|---|---|---|
| llmwiki | this repository | — |
| agentmemory | https://github.com/rohitg00/agentmemory | pushed 2026-10-20 |
| mem0 | https://github.com/mem0ai/mem0 | pushed 2026-10-21 |
| TencentDB Agent Memory | https://github.com/TencentCloud/TencentDB-Agent-Memory | pushed 2026-10-21 |

**Function rows**, in this order. Cells use the same sentence shape across columns. Write each tool’s own terms. Do not copy star counts or benchmark claims.

1. Output for agents — the channel. Whether anything is written into the prompt.
2. Context impact — what sits in the agent context. llmwiki is the 6 MCP tool descriptions. The others inject a filtered slice, not the whole store.
3. Output for humans.
4. Agent coverage — digit first, then the names, except mem0 (any caller of `add` / `search`). Do not explain contrib versus core. TencentDB’s digit is 9, from its install guide on `feat/server_team`: Claude Code, CodeBuddy, WorkBuddy, Codex, DeepSeek Harness, OpenCode, Hermes, OpenClaw, Pi. The default-branch README only names OpenClaw and Hermes.
5. KB sources — one bracket list.
6. KB layers — one bracket list in that tool’s terms.
7. Query features — one line, same length as the other columns.
8. Automation cadence — llmwiki: OS scheduler (daily or hourly), `watch`, or hooks (hooks are brittle and not the default). Pull only.
9. Resources usage — what stays running. Do not contrast another tool’s cost with “not a static site”.
10. Tokens cost — whether the tool calls an LLM. llmwiki: no LLM for search, sync, or reading raw pages; LLM for `synth` and inner skills.
11. Observability — how a person sees contents, freshness, and agent use.

**Under the table** — lucasastorian/llmwiki (https://github.com/lucasastorian/llmwiki, pushed 2026-10-20) and the Obsidian Karpathy LLM Wiki plugin (`karpathywiki`, https://community.obsidian.md/plugins/karpathywiki, pushed 2026-10-21). One short note each: they build a wiki a person reads and do not take coding-agent session stores.

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
