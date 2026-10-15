# Technical Specification: Session token usage store + Cursor CLI capture

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** 4ellendger
- **Related:** [#322](https://github.com/AlexanderMakarov/llm-wiki/issues/322) (consume this store later; last-activity session-day approximation)

---

## 1. High-Level Technical Approach

**Design rule:** hot paths optimize for **number of files opened/written**. Reject one JSON file per session and reject multi-file aggregate splits that can drift under concurrent writers.

**SoT for Analytics Tokens:** one vault file, atomic RMW (write temp → rename):

```text
<vault>/usage/session-tokens.json
```

**SoT for static session-page Tokens:** raw session frontmatter `token_totals` (four buckets), written whenever convert creates/updates that raw page.

**Site sidecar:** `site/session-tokens.js` (or equivalent) copied from the usage snapshot on sync (and on migrate when it changes Tokens) so Analytics can refresh without a full HTML rebuild.

```text
migrate session-tokens   # one-shot historical backfill (UPGRADING)
  → discover / re-read origins as needed → patch raw token_totals → RMW usage/session-tokens.json → sidecar

sync / metrics pass      # steady state: new + fingerprint-changed only
  → optional raw/sessions/*.md (+ token_totals on write/update)
  → RMW usage/session-tokens.json only if something changed
  → sidecar if usage file changed

build / Analytics
  → read usage/session-tokens.json (or sidecar); NOT raw/** for the Tokens tile
```

Four-bucket contract unchanged (`compute_token_totals`). Cursor maps real usage; occupancy never written.

**Day rule (locked):** attribute each session’s **entire** four-bucket total to `UTC date(last_activity)`. On resume/update, re-upsert: subtract previous contribution if fingerprint/day/totals changed, then add under the new last-activity day.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Single file shape

`usage/session-tokens.json`:

| Section | Role | Size class |
|---------|------|------------|
| `totals` | Lifetime four buckets + `sum` | O(1) |
| `by_agent` | per agent: `measured`, `known`, `totals` | O(agents) |
| `days` | `YYYY-MM-DD` → agent → four buckets + `sum` (+ optional `measured_sessions`) | ~3660 × agents / 10y — small |
| `sessions` | `session_key` → `{ agent, day, totals, fingerprint, last_activity, in_raw?, metrics_only? }` | grows with tracked sessions; **necessary** for correct subtract/add on resume without re-scanning all origin history every time |
| `attribution` | `{ "day_rule": "last_activity_utc", "timezone": "UTC" }` | O(1) |
| `updated_at` | ISO timestamp | O(1) |

Analytics / #322 read `totals`, `by_agent`, and `days` only. The `sessions` map is an implementation ledger inside the same file (one lock, one atomic write) — not a second path operators manage.

**Do not** ship `session-tokens-daily.json` or `session-tokens-ledger.json` as separate files.

### Frontmatter + Cursor backfill timing

| Path | When | What |
|------|------|------|
| **`llmwiki migrate <session-tokens-…>`** | **Primary historical backfill** after upgrade (UPGRADING) | Explicit pass: for capable sessions (origin and/or existing raw), compute usage, patch raw `token_totals` where raw exists, upsert usage file, refresh sidecar. Idempotent; `--dry-run`. Does **not** rely on sync skip state — that is why it is reliable |
| Regular `sync` | Steady state | **List/discover** + fingerprint vs sync state / usage stub. **Unchanged → skip** Tokens work. **New or fingerprint-changed** → normalize → totals → upsert; set frontmatter when raw written/updated. Does **not** backfill “synced before tokens existed, fingerprint still matches” |
| Resume | Fingerprint changed | Re-upsert; move day if `last_activity` day changed; refresh frontmatter when raw exists |
| Second+ sync, no changes | Steady state | Fingerprint no-ops; **must not** re-parse all bodies; **must not** rewrite usage file if nothing changed |

**Why migrate, not sync, for history:** `llmwiki-state.json` (and origin mtime fingerprints) answer “has convert already processed this unchanged file?” — not “does frontmatter already contain `token_totals`?” After shipping this feature, pre-existing synced sessions keep matching fingerprints, so sync would skip forever unless we broke the skip (full re-read) or added a parallel “tokens backfill pending” bit. A named migrate is the same reliability model as other one-shot vault repairs.

**Fingerprint (steady-state sync only):** cheap origin metadata (path + mtime_ns + size, or store revision), aligned with convert skip where possible. Not a full-transcript hash unless metadata is missing.

Occupancy-only Cursor rows: skip fabricated usage (no frontmatter totals invented).

### Multi-day + resume algorithm (option A)

1. `day = UTC date(last_activity)` (fallback chain documented in code if last_activity missing: e.g. `ended` → `started` → file stamp — prefer failing soft to started only when last_activity absent).
2. **Before** full parse: if `session_key` exists and origin fingerprint unchanged → **skip** (no normalize, no `compute_token_totals`, no file write for that session).
3. If new/changed: compute totals; subtract old `totals` from `days[old_day][agent]` and lifetime/`by_agent` when replacing; add new totals to `days[new_day][agent]` and lifetime; update stub (`day`, `totals`, `fingerprint`, `last_activity`).
4. If every session in the pass was a fingerprint skip, **do not** rewrite `usage/session-tokens.json` (and do not refresh the sidecar) solely for Tokens — leave mtime alone.
5. Coverage: `known` / `measured` derived from stubs (measured = ≥1 non-zero bucket), including `metrics_only`.

### Metrics without raw

Metrics pass on sync: for discoverable sessions skipped by convert (filter / don’t-sync), still upsert with `metrics_only: true`. No session HTML page required.

### Cursor CLI + shared writers

- `cursor_cli.normalize_records`: attach mapped `message.usage` in Claude’s field names when a real usage source exists; **never** occupancy.
- Shared helper: Cursor inclusive input → disjoint four buckets (formula below).
- Claude and other capable adapters call the same `upsert_session_tokens(...)`.

#### How to obtain the four values from Cursor (do not drop this)

**Target shape** (what `compute_token_totals` already sums on assistant `message.usage`):

| llmwiki bucket | Claude / convert field |
|----------------|------------------------|
| `input` | `input_tokens` |
| `cache_creation` | `cache_creation_input_tokens` |
| `cache_read` | `cache_read_input_tokens` |
| `output` | `output_tokens` |

**Accepted Cursor sources for those counts** (session usage / throughput — not plan $):

| Source | Fields | Notes |
|--------|--------|-------|
| Hooks `stop` / `afterAgentResponse` | `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens` | Parent agent only; fields **optional** (absent ≠ zero). Same totals for a `generation_id` on both hooks — **pick one, do not sum both**. `subagentStop` has **no** token fields. Forum: [cursor.com/t/…/168317](https://forum.cursor.com/t/how-to-obtain-token-usage-per-request/168317) (Kevin). |
| Protobuf / UI `TurnEndedUpdate` | `1 input_tokens`, `2 output_tokens`, `3 cache_read_tokens`, `4 cache_write_tokens`, (+ `reasoning_tokens` — out of Tokens buckets unless product later extends) | Same semantic family as hooks. |
| Agent CLI `stream-json` final `result` | usage when present | Non-interactive CLI often **omits** hook events; stdout `result` may still carry usage for print/stream mode — prefer when hooks absent. |
| Admin / dashboard usage API | billed events | **Out of scope** for this ticket (network + auth); document as possible future, not required for #325. |

**Rejected for Tokens (occupancy — never write as `token_totals`):**

| Source | What it is |
|--------|------------|
| `store.db` protobuf **field 5** ≈ `ConversationTokenDetails` | Context-window gauge: `used_tokens` / `max_tokens` + `PromptTokenBreakdownSnapshot` categories (`system_prompt`, `tools`, `rules`, `skills`, `mcp`, `subagents`, `summarized_conversation`, `conversation`) with `estimated_tokens` / `character_count`. Snapshot of “how full is the prompt,” not cumulative turn throughput. JSON message blobs in `store.db` have **no** `token`/`usage` keys. |

**Inclusive → disjoint map** (Kevin: Cursor `input_tokens` **already includes** cache read/write; Claude’s four buckets are **non-overlapping**; Analytics sums all four — so we must split, not leave cache inside `input` and also add `cache_*`):

```text
# From one turn’s Cursor usage object (hook / TurnEndedUpdate / stream-json):
cr = cache_read_tokens or 0          # only when the field is present; see absence rules
cw = cache_write_tokens or 0
inp = input_tokens                   # required to treat the turn as measured
out = output_tokens

message.usage = {
  input_tokens:                  max(0, inp - cr - cw),   # fresh / non-cache share
  cache_creation_input_tokens:   cw,                        # cache_write → cache_creation
  cache_read_input_tokens:       cr,
  output_tokens:                 out or 0,
}
```

Then existing `compute_token_totals` sums those fields across assistant turns → session `token_totals` / usage-file upsert.

**Absence / honesty:**

- Missing usage object entirely → session contributes **no** measured Tokens (omit from measured; do not invent zeros from occupancy).
- Present object with some fields missing → treat missing numeric fields as 0 for arithmetic **only after** deciding the turn is measurable (e.g. `input_tokens` or `output_tokens` present); do not treat “no usage blob” as measured zero.
- Historical chats that only have `store.db` occupancy: migrate/sync **cannot** invent four-bucket usage — document gap; optional later surface for occupancy elsewhere (not Tokens tile).

**Implementation sketch:** helper e.g. `map_cursor_usage_to_claude_usage(raw: dict) -> dict | None`; `normalize_records` attaches result onto assistant records; fixtures from redacted hook/`TurnEndedUpdate` payloads + a store.db occupancy fixture that must **not** produce `token_totals`.

### Sync / build I/O

| Op | Tokens-related vault/site files |
|----|----------------------------------|
| `sync` | RMW usage file + sidecar **only if** new/changed sessions contributed; raw only for synced transcripts |
| `build` | Read that usage file (or sidecar); no raw walk for Tokens tile |
| `migrate session-tokens` | One-shot historical: may re-read origins / patch many raw frontmatter files — rare, not daily loop |

### Widgets + docs

- All Tokens widgets: hover from `by_agent`; omit agents with `measured == 0`; short blurb (usage≠billing; four categories; last-activity day attribution).
- `docs/reference/state-persistence.md` — one row for `usage/session-tokens.json`.
- `docs/reference/ui.md` — session page frontmatter vs Analytics usage file; migrate for history; sync for new/changed.
- CONTRIBUTING + maintainer ARCHITECTURE — Vault I/O / file-count rule.
- CHANGELOG / UPGRADING — named migrate as historical Tokens backfill; sync steady-state thereafter.

### Module sketch

| Piece | Responsibility |
|-------|----------------|
| `llmwiki/session_tokens_usage.py` (name TBD) | load/save one JSON; atomic upsert; emit sidecar; rebuild aggregates from `sessions` if corrupt |
| adapters + convert | totals + last_activity; invoke upsert; write frontmatter on raw |
| sync CLI | metrics pass + convert; sidecar |
| `viz_tokens.py` / build | consume usage file; hints |
| migrate cmd | historical backfill (origin + raw patch + usage file); idempotent |
| tests | migrate fills pre-sync sessions sync would skip; sync fingerprint no-op; last_activity day move; metrics_only; Cursor map |

---

## 3. Impact and Risk Analysis

- **#322:** `days` × agent unblocks rolling windows; headline from `totals` / `by_agent`.
- **`sessions` map growth:** one file still; monitor size; still beats n inodes / n opens.
- **Idempotency / resume:** subtract-then-add must be tested (day move, force sync, metrics_only → in_raw).
- **Lookback:** sessions outside discovery window are not refreshed until seen again — document.
- **Scope:** store + I/O rules → Cursor writer → frontmatter → widgets/docs.

---

## 4. Testing Strategy

- Upsert idempotency; last_activity day change moves contribution; frontmatter written on convert.
- Migrate backfills sessions that sync fingerprint-skip would never touch; sync alone does not fill those.
- Second sync with unchanged fingerprints: no full body re-parse; usage file mtime unchanged when all skips.
- metrics_only in totals/hover, absent from session list.
- Cursor usage vs occupancy; coverage omits zero-measured.
- Unit tests for inclusive→disjoint map (double-count prevention; clamp; missing fields; occupancy fixture → no totals).
- Assert Tokens refresh does not open per-session usage files.
- Docs rows for state-persistence + I/O rule.

---

## Appendix A — Cursor investigation notes (preserve across rewrites)

Verified in local Agent CLI stores + bundle descriptors (`ConversationTokenDetails`, `TurnEndedUpdate`, `TokenUsage`, `ContextWindowStatus`) and Cursor forum staff answers (Kevin, thread 168317). **Do not delete this appendix when revising store/I/O sections above.**

1. **`agent-transcripts/*.jsonl`:** no token fields (`{role, message}` only).
2. **`~/.cursor/chats/…/store.db`:** SQLite `meta` + `blobs`; usage-shaped numbers in protobuf field 5 are **occupancy**, not billed/turn throughput; JSON blobs lack usage keys.
3. **Field 5 decode:** `used_tokens` == `breakdown.total_used_tokens` == sum of category `estimated_tokens`; `character_count/estimated_tokens` ≈ 2–3.8 — estimate-from-chars, not API billing.
4. **Hooks:** `stop` / `afterAgentResponse` carry turn totals; don’t sum both for one generation; CLI headless often skips hooks.
5. **Product lock for #325:** four-bucket session usage via map above; occupancy never substitutes; plan % / dollars out of scope.
