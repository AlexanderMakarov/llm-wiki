# Technical Specification: Extend exclude_headless across agentic adapters

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Completed
- **Author(s):** Aleksandr Makarov
- **Issue:** [#180](https://github.com/AlexanderMakarov/llm-wiki/issues/180)

---

## 1. High-Level Technical Approach

Keep one policy choke point: `filters.exclude_headless` (default on) gates **ingest** (`convert_all`) and **synth/estimate** (`is_headless` on raw frontmatter). Do not invent a second filter.

Add **`BaseAdapter.is_headless_session(self, records) -> bool`**. Every registered session adapter implements it in this change. Convert calls the adapter’s method after `normalize_records`. Persist `is_headless` on rendered raw markdown for sessions that are kept. Synth continues to read frontmatter (and existing Claude fallbacks); new converts always write the flag so synth stays simple.

Claude keeps today’s `entrypoint` / `promptSource` rules (as the Claude adapter’s implementation or the shared default those rules live in). Other adapters map **only verified store evidence**; when an adapter has no automation markers, its implementation returns `False` (not headless) — interactive / useful sessions stay eligible. Legacy raw files with no markers stay eligible until re-sync.

**Cursor Agent CLI:** headless when meta has `subagentInfo` (nested Task/subagents, including code-reviewer and other second-model child agents) **or** `approvalMode` is `auto-review` (non-interactive second-opinion / auto-review runs). Top-level interactive Agent sessions remain eligible.

**OpenClaw:** `is_headless_session` always returns `False`. User-facing docs state that all OpenClaw sessions are treated as not headless. A short comment in the OpenClaw adapter code may note that dreaming artifacts live outside the session store (not a docs topic).

Docs (R6): support map + per-source automated meaning; **audit all docs (except changelog / upgrade history style files) so adapter support text matches current product state** — no “will be added in v…” / stub-future claims.

---

## 2. Proposed Solution & Implementation Plan

### Adapter contract

- `BaseAdapter.is_headless_session(self, records: list[dict]) -> bool` — required override surface for every adapter class that ships in `llmwiki/adapters/` and `llmwiki/adapters/contrib/` (including Obsidian / ChatGPT, which return `False` and lock that with tests).
- Default on the base class may encode Claude’s historical rule only if Claude itself does not override; prefer each adapter owning its rule so “every adapter implements the checker” is enforceable in tests (e.g. each concrete adapter defines the method).
- `convert_all`: after normalize, `adapter.is_headless_session(records)`; on True and `exclude_headless`, skip + count toward existing aggregate headless summary (no per-adapter breakdown).
- `render_session_markdown`: write `is_headless: true|false` (and any native audit fields worth keeping, e.g. Cursor `approvalMode` / subagent `typeName`).

### Per-adapter behavior (this change)

| Adapter | `is_headless_session` |
|---|---|
| `claude_code` | Existing Claude markers (`entrypoint` `sdk-*`, `promptSource` `sdk`) |
| `cursor_cli` | `subagentInfo` present **or** `approvalMode == auto-review` |
| `openclaw` | Always `False` (code comment only re: dreaming outside session store) |
| `codex_cli`, `opencode`, `copilot_cli`, `copilot_chat`, `chatgpt`, `gemini_cli`, `cursor` (IDE), `obsidian` | Implement the method in-scope. Return `False` unless research in this PR finds verified automation / nested-agent / second-model markers — then map those explicitly. No silent invention. |

Research for Codex / OpenCode / Copilot / Gemini / Cursor IDE happens **during implementation of those methods**, still in this PR: inspect schemas/fixtures/local stores when available; document the chosen rule in the adapter docstring / support map.

### Cursor vs subagent policy

Cursor nested agents are classified under **`exclude_headless`**, not by changing `include_subagents`. Document precedence if both filters apply; add a test for the intended order. Disabling `exclude_headless` still includes those sessions.

### Docs

- Dedicated support / “what is automated” coverage for registered sources; Cursor Agent CLI vs Cursor IDE (#2); today’s `--adapter` opt-in called out (#182) without implementing #182.
- OpenClaw user docs: **all OpenClaw sessions are treated as not headless** — nothing further about dreaming.
- **Docs currency gate:** `rg` (or equivalent) across `docs/` (and other user-facing markdown that ships in the product docs site — **exclude** `CHANGELOG.md`, `docs/UPGRADING.md`, and similar historical release notes) for every registered adapter name / common display name. Fix any stale “stub”, “coming in v0.x”, “will be supported in…”, or otherwise non-current support claim so pages describe **current** behavior only.
- `CHANGELOG.md` + `docs/UPGRADING.md`: re-sync may drop newly classified Cursor headless rows from the synth backlog; legacy unmarked files stay eligible until re-sync.

### Files (expected)

- `llmwiki/adapters/base.py` — method on the contract
- Every adapter module under `llmwiki/adapters/` and `contrib/`
- `llmwiki/convert.py` — call site + frontmatter
- `llmwiki/_frontmatter.py` — only if synth fallbacks must learn new persisted fields
- Tests: `test_exclude_headless*.py`, per-adapter headless tests, docs-currency test or scripted check
- Docs paths corrected by the currency grep

---

## 3. Impact and Risk Analysis

- **Dependencies:** ingest + synth/estimate share `exclude_headless`.
- **Risk — Cursor nested agents vs `include_subagents`:** headless exclusion may drop Task children even when subagent policy would keep them. Mitigation: docs + UPGRADING + precedence test; Claude subagent path unchanged.
- **Risk — auto-review over-filter:** accepted product rule; users can set `exclude_headless: false`.
- **Risk — weak markers on Codex/etc.:** implementations return `False` until evidence exists; research is in-scope but must not invent fields.
- **Legacy raw:** unmarked → not headless until re-sync.

---

## 4. Testing Strategy

- Contract: every registered adapter class defines `is_headless_session` (registry walk test).
- Cursor: fixtures for `subagentInfo` → headless; `approvalMode=auto-review` → headless; interactive top-level Agent meta → not headless; filter off includes all.
- Claude: existing ingest/synth regressions.
- OpenClaw: always not headless; Obsidian / ChatGPT return False.
- Codex / OpenCode / Copilot / Gemini / Cursor IDE: tests match the rule each method documents (False-by-default or marker-based if research lands markers).
- Ingest + synth/estimate: shared policy; sync summary still aggregate headless count.
- Legacy unmarked raw: eligible under synth.
- **Docs currency:** automated check (test or CI-oriented script used in verify) that greps user-facing docs (excluding changelog / upgrading history) for adapter identifiers and fails on banned stale phrases (e.g. “will be supported in”, “coming in v0.”, “v0.1 stub” paired with Codex, etc.) or on an allowlisted set of known-bad strings updated as the audit cleans them — goal: docs show **current** support state only.
