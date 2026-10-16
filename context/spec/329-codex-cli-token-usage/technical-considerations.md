# Technical Specification: Codex CLI session Tokens capture

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** 4ellendger
- **Related:** [#324](https://github.com/AlexanderMakarov/llm-wiki/issues/324); store/pipeline from [#325](https://github.com/AlexanderMakarov/llm-wiki/issues/325); #322 consumes day × agent later

---

## 1. High-Level Technical Approach

Do **not** redesign `usage/session-tokens.json`. Add a Codex→Claude usage mapper (same pattern as `llmwiki/cursor_token_usage.py`), teach `codex_cli.normalize_records` to attach measurable usage from native `event_msg` / `token_count`, and update coverage docs/hint. Steady-state sync + `migrate session-tokens` already upsert when `compute_token_totals` is nonempty.

Prefer native measured token usage. Approximate week/month attribution uses the shared last-activity UTC day rule already in the usage file — no per-event time buckets in this ticket.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Native fields (verified on-disk)

| Source | Role for Tokens |
|--------|-----------------|
| `event_msg` → `payload.type == "token_count"` → `info.total_token_usage` | **Session snapshot** — cumulative; use **last** event only (or equivalent final snapshot). Fields: `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens`, `reasoning_output_tokens`, `total_tokens` |
| same → `info.last_token_usage` | Per-turn delta; sum of lasts equals final total in sampled session — alternative path if totals absent |
| `info.model_context_window` | **Rejected** (occupancy / window size) |
| `rate_limits` / plan percents | **Rejected** (billing/plan, not Tokens) |

Versions/providers: document as Codex CLI JSONL rollouts under `~/.codex/sessions/` (sampled 2026-09+). Unavailable = sessions with no usable `token_count` measured fields.

Investigation evidence (redacted structure) lives in `investigation-notes.md` in this spec directory when written during implement.

### Mapping (product lock: omit reasoning)

Target shape — what `compute_token_totals` already sums on assistant `message.usage`:

| llmwiki bucket | Claude / convert field |
|----------------|------------------------|
| `input` | `input_tokens` |
| `cache_creation` | `cache_creation_input_tokens` |
| `cache_read` | `cache_read_input_tokens` |
| `output` | `output_tokens` |

```text
# From final total_token_usage (preferred) OR sum(last_token_usage) once:
inp = input_tokens
cr  = cached_input_tokens      # subset of input — do not leave inside input and also add
cw  = cache_write_input_tokens
out = output_tokens
rea = reasoning_output_tokens  # subset of output when present

message.usage = {
  input_tokens:                max(0, inp - cr - cw),  # if cw already outside input, only subtract cr; clamp
  cache_creation_input_tokens: cw,
  cache_read_input_tokens:     cr,
  output_tokens:               max(0, out - rea),      # omit reasoning
}
```

- If `reasoning_output_tokens` key is **absent** → do **not** invent a split; use `output_tokens` as-is and document the honesty limit.
- If no measurable `token_count` → return `None` (no fabricated zeros). Occupancy / rate_limits alone → `None`.
- **Double-count guard:** never sum successive `total_token_usage` snapshots; take the last cumulative (or sum `last_token_usage` once across the session).

### Adapter + shared writers

| Piece | Responsibility |
|-------|----------------|
| `llmwiki/codex_token_usage.py` (new) | Extract final Codex usage blob from records / events; `map_codex_token_usage_to_claude_usage(...)` → Claude four fields or `None` |
| `llmwiki/adapters/codex_cli.py` | Stop ignoring all `event_msg`; collect `token_count`; attach one mapped `message.usage` onto a synthetic or last assistant record so `compute_token_totals` sees it |
| Existing convert / `upsert_session_tokens` / `migrate session-tokens` | Unchanged contract — nonempty totals → frontmatter + usage file + agent `codex_cli` + last-activity day |
| `viz_tokens.TOKEN_COVERAGE_LINES` | Split Codex vs Cursor IDE: Codex included when usage fields present; Cursor IDE remains not captured |
| docs | `docs/adapters/codex-cli.md`, `docs/UPGRADING.md` (migrate/re-sync when store remains), `CHANGELOG.md`, `docs/reference/ui.md` if coverage copy is documented there |
| fixtures/tests | Synthetic JSONL with multi-`token_count` (monotonic totals), no-events / occupancy-only → no totals; reasoning subtraction; coverage string update |

### Historical backfill

`llmwiki migrate session-tokens` already discovers `codex_cli` origins. After mapping lands, operators re-run migrate (or fingerprint-changed sync) when `~/.codex/sessions` remains. No new migrate subcommand unless implement finds a wiring gap.

---

## 3. Impact and Risk Analysis

- **System dependencies:** `compute_token_totals`, `session_tokens_usage`, migrate session-tokens, Analytics coverage hint (#323 / #325).
- **Risks:**
  - Inclusive vs exclusive input/cache field semantics across Codex versions → clamp `max(0, …)`; fixtures + investigation notes.
  - Attaching usage to the wrong record skips convert upsert → prefer final synthetic assistant-with-usage or patch last assistant; assert via convert/migrate tests.
  - Fallback coverage copy still says “Codex not captured” → update `TOKEN_COVERAGE_LINES` + tests.
- **Out of scope:** #322 UI; #321 Home; store redesign; Cursor IDE capture.

---

## 4. Testing Strategy

- Unit: mapper (disjoint buckets, reasoning omit, `None` for empty/occupancy-only, last-total not sum-of-totals).
- Adapter: normalize fixture JSONL → assistant usage present; multi-event no double-count.
- Integration: convert/migrate upserts `token_totals` + usage file for Codex agent; coverage hint text.
- Extend existing Cursor/session-tokens tests rather than duplicate store logic. Prefer stable slug test module names (no new `test_324_*.py`).
