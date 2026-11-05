# Flow log — #356 Cursor usage API (ACP/AO Tokens)

- **Issue:** https://github.com/AlexanderMakarov/llm-wiki/issues/356
- **Branch:** `feat/356-cursor-usage-api`
- **Delivered:** `cursor_usage_api` config (`off` | `dashboard` | `admin`), `llmwiki/cursor_usage_api.py`, sync/migrate integration, hook-wins dedupe, tests in `tests/test_cursor_usage_api.py`, docs + CHANGELOG.

## Follow-up — backfill to the sync lookback (2026-11-05)

- **Gap found live:** the first poll only fetched the last 3 days and later polls started at `high_water_ms`, so ACP sessions older than the first poll never got Tokens (most of a month of ACP runs uncovered on the operator vault). Dashboard retention was verified read-only to reach back several months.
- **Change:** `backfill_floor_ms()` resolves the `cursor_cli` lookback (`adapters.cursor_cli.since` → `filters.since`, cap 365 days). `backfilled_from_ms` in `cursor-usage-api-state.json` triggers one `[floor, now]` fetch when missing (first poll / caches from the 3-day build) or when the lookback moves earlier; otherwise polling stays incremental. Failed fetches leave the marker unset so the backfill retries.
- **Tests:** `tests/test_cursor_usage_api.py` — first-poll floor, legacy cache re-fetch, incremental after backfill, earlier-lookback re-backfill, retry after 429.
- **Still out of scope:** #396 IDE ledger semantics (ignores `cursor_ide.enabled` / lookback) — separate fix.
