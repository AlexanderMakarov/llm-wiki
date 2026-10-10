# Technical Specification: Honest Home Timeline for sync, synth, build, and lint

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** Alexander Makarov
- **Issue:** [#234](https://github.com/AlexanderMakarov/llm-wiki/issues/234)

---

## 1. High-Level Technical Approach

Extend the existing vault state snapshot (`llmwiki-state.json`, and the existing `llmwiki-state.js` wrapper that only embeds that same JSON for the browser — **not** an HTML edit) with explicit **stage completion stamps** and a **lint outcome** (`status` + optional multiline `error` text). Writers run at the end of sync (already), synth, build, and lint via **shared helpers** (DRY — one writer per concern, called from both standalone CLI and `all`). Home’s **Pipeline state** widget reads the new fields (not the Automation panel). After lint updates the JSON, keep the vault/site **data** sidecars in sync so standalone `llmwiki lint` refreshes Pipeline state **without rewriting any HTML pages**.

**Required UI:** when `last_lint_error` is non-empty, show a note **under the Candidates / knowledge table**. Stage stamps (**Last sync / Last synth / Last build / Last lint**) live in the **Timeline** collapsible. The **Automation** panel holds **settings only** (shrunk as already decided).

Do **not** add publish/rollback of `site/` on lint-fail. Confirm continue-after-failure unless `--fail-fast`. Under `--fail-fast`, console reporting is enough. No new runtime dependencies.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.0 DRY / reuse (mandatory)

Do **not** invent parallel stamp or copy paths per command. Extract or extend existing helpers and call them from every entrypoint:

| Concern | Prefer existing / shared | Call sites |
| --- | --- | --- |
| State write + JS wrapper | `state_store.update_state` / `write_state` (already writes JSON + vault `llmwiki-state.js`) | all stamp writers |
| Copy snapshot into `site/` | Reuse the copy logic already in `build_site` (extract a tiny shared function if needed — one implementation) | `build_site` (existing) + post-lint |
| Lint console text | Existing lint text renderer used by `cmd_lint` / `_run_lint_step` | print unchanged; store `render_ops_error` output (same line shape, policy-failing findings first, #256) into `last_lint_error` and the full `render_text` report into `last_lint_report` |
| Lint stamp + status + error + site data sync | **One** helper (e.g. `record_lint_ops(...)`) | `cmd_lint` and `pipeline._run_lint_step` |
| Synth stamp | **One** helper | `cmd_synthesize` (non-estimate) and `pipeline` synth stage |
| Build stamp | Inside `build_site` on rc==0 only (CLI `build` and `all` already share this) | no duplicate in `cli.py` |

If a helper already exists for one CLI path, **extend and call it** from the other — do not copy-paste field `__setitem__` blocks.

### 2.1 State model (`ops` in `llmwiki-state.json`)

File: `llmwiki/state_store.py` — extend `default_state()["ops"]` (and `_ensure_shape` merge) with:

| Field | Type / empty | Writer | Reader |
| --- | --- | --- | --- |
| `last_sync` | already under `sync.meta.last_sync` | `convert.save_sync_meta` (unchanged) | Pipeline state |
| `ops.last_synth_at` | ISO-8601 `Z` or `""` | shared synth stamp helper | Pipeline state |
| `ops.last_build_at` | ISO-8601 `Z` or `""` | `build_site` on rc==0 | Pipeline state |
| `ops.last_lint_run_at` | already exists | shared lint record helper | Pipeline state |
| `ops.last_lint_status` | `""` \| `"ok"` \| `"failed"` | shared lint record helper | Pipeline state + banner |
| `ops.last_lint_error` | `""` or multiline console-shaped text (policy-failing findings, stored in full) | shared lint record helper; clear when ok | Red note under Candidates when it has an `[error]` line; Home JS shows up to **10 lines** + `…` |
| `ops.last_lint_report` | `""` or the full console lint report (#256) | shared lint record helper; set only when the policy fails, cleared when ok | **Linter output** collapsible after Estimate warnings |

**Assumptions (verify):**

1. Stamp `last_synth_at` when the synth **stage finishes** even if some files errored; do **not** stamp when the backend was unavailable and synth never ran.
2. Lint “failed” means the active fail policy tripped, not merely findings under `never`.
3. Hide empty **Last reflect** from the remaining Timeline (or drop it) — honesty cleanup.
4. **`--fail-fast`:** console must report failure; static-site surfacing for early abort is not required.

### 2.2 Lint updates state data only (not HTML)

**Clarification:** `lint` must **not** rewrite Home HTML (or any other `site/*.html`). It only updates **JSON state** (`llmwiki-state.json`). The existing `llmwiki-state.js` is a thin `window.LLMWIKI_STATE_SNAPSHOT = …` wrapper around that same JSON (already produced by `write_state` / `update_state`).

**Gap:** standalone lint updates vault-root JSON (+ vault JS). Home from `site/index.html` loads `site/llmwiki-state.js`, which can stay stale until the next build copies it.

**Plan:** after the shared lint record helper stamps ops, if `site/` exists, call the **same** sidecar-to-site copy used by `build_site`. Still **no** `build_site`, no HTML mutation.

### 2.3 Stamp writers

| Stage | Where to stamp |
| --- | --- |
| Sync | existing `convert.py` → `sync.meta.last_sync` |
| Synth | shared helper from `pipeline` + `cmd_synthesize` |
| Build | `build_site` on rc==0 only |
| Lint | shared `record_lint_ops` from `cmd_lint` + `_run_lint_step` |

**Lint error text:** same line shape as console lint output (multiline), stored in full. `llmwiki/lint/report.py:render_ops_error(outcome, total_pages, fail_on=…)` shares the summary and `## rule (n)` / `  [severity] page: message` helpers with `render_text`, but selects findings by the active policy — errors only under `errors`; errors then warnings under `warnings`; never info — and drops the skipped-rules block and blank separators. `state_store.format_lint_error_for_ops` is a pass-through (CRLF and trailing blank lines only). `record_lint_ops(report_text=…)` also stores the full `render_text` report in `last_lint_report`. Display limits live in `renderStateWidget`: the red note renders only when the text has an `[error]` finding line and shows its first 10 lines plus `…`; the full report renders pre-wrap in a **Linter output** `detailsSection` right after Estimate warnings.

**Lint-fail in `all`:** stamps + data sidecar sync before exit 2; HTML from the preceding build stays — **no revert**.

**`--fail-fast` early stop:** console only; site/JSON lint surfacing not required.

### 2.4 Home Pipeline state UI (`llmwiki/render/js.py` + CSS as needed)

**Ownership split:**

| Surface | Shows |
| --- | --- |
| **Eligible sources / Knowledge tables** | Count tables only. Red lint-error **note under the Candidates / knowledge table** when `last_lint_error` contains an `[error]` finding line (pre-wrap, up to 10 lines + `…` in JS, #256). Warnings-only policy failures: no red note; Timeline Last lint · failed + **Linter output**. Empty error → no note. **Linter output** collapsible after Estimate warnings renders `last_lint_report`. |
| **Timeline** (collapsible) | Oldest pending, **Last sync / Last synth / Last build / Last lint** (time + lint pass/fail), Last queue run. Hide dead Last reflect. |
| **Automation** (`render_automation_panel`) | **Settings only** — short Synth backend line, Agent hooks (no “(recommended)”), Watch on its own line, log path, Maintain one-liner. **No** stage timestamps / lint outcome / lint-fail reminder / Updated. |

### 2.5 Automation panel shrink (`llmwiki/build.py` `render_automation_panel`)

- Remove `lint_fail_line` entirely.
- Remove `Updated: …` list item.
- Short **Synth backend** line with spend hint (user wording); ingest gets a short “does not spend money” form.
- **Agent hooks** without “(recommended)”; **Watch** on a separate line.
- For Maintain: one short clause that Maintain refreshes the site once after summarization.
- Do **not** add pipeline timestamps here.

Update tests that assert Automation panel HTML (`tests/test_automation_install.py`, related).

### 2.6 Docs

- `docs/reference/cli.md` — Maintain site-once-after-synth; `--fail-fast`; lint-fail does not undo build.
- `docs/reference/ui.md` / `state-persistence.md` — Pipeline state owns stage stamps + lint banner; Automation is settings-only; lint refreshes JSON/data sidecar only.
- `CHANGELOG.md` / `UPGRADING.md` as required by CONTRIBUTING.

### 2.7 Pipeline continue / `--fail-fast`

**Already implemented** in `llmwiki/pipeline.py`. Tech work: **tests + docs** (synth-fail → build still runs; `--fail-fast` skips later stages). No stage-order change.

### 2.8 Architecture changes

None beyond existing state snapshot + Home widget + panel HTML. No new services, MCP tools, or adapters.

---

## 3. Impact and Risk Analysis

- **System dependencies:** Pipeline state depends on `site/llmwiki-state.js`; lint must keep that data file in sync via the shared copy helper.
- **Risks & mitigations:**
  - **Duplicated stamp logic** — enforce §2.0 DRY; single helper per stage.
  - **Stale site data after lint** — shared copy + tests without `build`.
  - **Error text drift from console** — share the lint text renderer's line helpers.
  - **Banner vs Automation confusion** — timestamps only under Pipeline state; Automation settings-only.
  - **Automation panel test brittleness** — update goldens in the same PR.
  - **`--fail-fast` and site** — do not over-engineer site updates on early abort.

---

## 4. Testing Strategy

- **Widget:** Timeline shows Last sync/synth/build/lint; lint note under Candidates iff `last_lint_error` lists an `[error]` finding (10 displayed lines + `…`); Linter output collapsible renders `last_lint_report`; Automation HTML has no stage stamps / lint-fail reminder / Updated.
- **DRY:** stamp helpers used from both CLI and `all` (assert via behavior, not duplicate code paths left behind).
- **State writers:** synth/build/lint stamp `ops.*`.
- **Lint → state data only:** JSON (+ `site/` data sidecar) updates; no HTML rewrite required.
- **Lint-fail keeps build HTML:** exit 2; site HTML from this run remains; banner/error in snapshot.
- **Continue vs fail-fast:** as before; fail-fast need not assert site lint surfacing.
- **Docs / CHANGELOG:** per CONTRIBUTING.

Specialist note: no dedicated `python-cli-backend` agent; implement via general-purpose + testing-expert for QA slice.

## Change Log

### 2026-10-09 — Home lint note shows policy-failing findings; full report in Linter output ([#256](https://github.com/AlexanderMakarov/llm-wiki/issues/256))

- **What changed:** R2 keeps the console line shape for `ops.last_lint_error` but no longer stores a prefix of the full report. The note lists the findings that tripped the active fail policy — errors under fail-on-errors; errors, then warnings, under fail-on-warnings — after the scanned / issue-count summary, without the skipped-rules block, and is stored in full. Home shows the red note only when it contains an `[error]` finding line and displays at most 10 lines followed by `…` (the limit lives in the browser, not in storage). A warnings-only fail-on-warnings failure leaves the red note hidden; Timeline and **Linter output** carry the failure. A new `ops.last_lint_report` keeps the full console report from a failed lint (cleared on a passing run) and backs a **Linter output** collapsible placed right after Estimate warnings.
- **Why:** the console report is grouped alphabetically by rule, so early warning rules (for example `content_freshness`) filled the old ~6-line note and the errors that failed the run never reached Home. Keeping the full text in state lets the operator read the complete report on Home without re-running lint.
- **Scope of the amendment:** which findings are stored, how many lines Home displays, when the red note appears, and the new Linter output section; console output and the note's placement under the Candidates table are unchanged. `tasks.md` stays the historical record of the original delivery.
