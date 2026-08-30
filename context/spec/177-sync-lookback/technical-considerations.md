# Technical Specification: Durable sync lookback (`filters.since` + per-adapter)

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** Aleksandr Makarov
- **Issue:** [#192](https://github.com/AlexanderMakarov/llm-wiki/issues/192)

---

## 1. High-Level Technical Approach

Extend CLI `--since` into durable config with resolution **CLI → adapter `YYYY-MM-DD` → adapter `"all"` (no gate) → shared `filters.since` → unlimited**. Apply lookback early on `SessionRef.mtime` / Cursor headers, then again via post-load `latest_record_time`. Never stamp `sync.files` for lookback-only skips; GC that adapter’s `sync.files` older than its effective lookback after a successful sync. `configure-sources` suggests today−30, shows **Eligible · In last 30 days** per source, and accepts **Enter / `all` / `YYYY-MM-DD`**. One optional `BaseAdapter.estimate_sync_candidates()` for counts — not a large adapter rewrite.

No new runtime deps.

---

## 2. Proposed Solution & Implementation Plan

### Config

| Location | Value | Meaning |
|---|---|---|
| `filters.since` absent/"" | — | Unlimited shared |
| `filters.since` | `YYYY-MM-DD` | Shared floor |
| `adapters.<name>.since` absent | — | Inherit shared |
| `adapters.<name>.since` | `"all"` | No date gate for this source |
| `adapters.<name>.since` | `YYYY-MM-DD` | Override |
| CLI `--since` | `YYYY-MM-DD` | Overrides all sources for that run |

Invalid date string → exit **2** (same style as today’s bad `--since`). `"all"` only valid on per-adapter key.

Helper: `resolve_effective_since(cli, config, adapter_name) -> datetime | None` in `llmwiki/sync/lookback.py` (or `adapters/settings.py`).

### Convert (`convert.py`)

1. Per adapter: resolve `since_dt`.
2. `discover_session_refs(since_dt=…)` optional; convert also drops `ref.mtime < since_dt` before load.
3. Report per adapter: **after early filter** (candidates) → **synced**; no full-store total.
4. Post-load `latest_record_time` gate unchanged; lookback skip → no `sync.files` write.
5. After successful non-dry-run: GC `sync.files` keys `f"{adapter}::"` with stored mtime before that adapter’s `since_dt`.
6. Hint line: how to change via `filters.since` / `adapters.<name>.since` / `configure-sources`.

### BaseAdapter (small)

| API | Role |
|---|---|
| `discover_session_refs(self, since_dt=None)` | Optional early filter; default ignores kwarg (convert still mtime-prunes) |
| `estimate_sync_candidates(self) -> …` | Returns `{eligible: int, in_last_30_days: int}` for configure UX |

**Default `estimate_sync_candidates`:** discover refs; Eligible ≈ all discovered (mtime path; no mandatory headless peek in v1); In last 30 days = mtime ≥ today−30. Document caveat for stores that need parse for headless.

**Cursor override:** headers/SQL — exclude empty/automated; split by `lastUpdatedAt`/`createdAt` vs today−30 (cheap, no bubble load).

### Configure quiz (`configure_sources.py`)

Always show both counts per enabled source before/while asking:

```text
  claude_code — Eligible: 412 · In last 30 days: 38
  openclaw    — Eligible: 20  · In last 30 days: 20
```

**Shared:**

```text
Shared earliest session date [2026-07-31 = today−30].
  Enter = accept suggestion · all = unlimited · or type YYYY-MM-DD:
```

| Input | Write |
|---|---|
| Enter | `filters.since = "<today−30 absolute>"` |
| `all` | leave shared unset |
| `YYYY-MM-DD` | that value |

**Per enabled source:**

```text
  openclaw override [Enter = use shared · all = no date gate for this source · YYYY-MM-DD]:
```

| Input | Write |
|---|---|
| Enter | no `since` key (inherit) |
| `all` | `adapters.<name>.since = "all"` |
| `YYYY-MM-DD` | that override |

Extend config write to merge `filters.since` and per-adapter `since` without clobbering unrelated keys. Non-interactive / skipped interview invents no dates. `setup.sh` already launches configure-sources.

### Docs / examples / CHANGELOG / UPGRADING

Document keys, `"all"`, inheritance, early prune, no state on lookback skip, GC, quiz keys, count labels. Example config shows `filters.since` commented/absent by default.

### Tests

Precedence including `"all"`; invalid → 2; early prune; no state write on lookback skip; GC; configure Enter/`all`/date writes; estimate helper with fakes.

---

## 3. Impact and Risk Analysis

| Risk | Mitigation |
|---|---|
| mtime ≠ content last activity | Keep hybrid post-load gate |
| Default estimate ignores headless | Documented caveat; Cursor accurate; optional later peek |
| GC drops old headless stamps | Re-parse until re-stamp; document |
| GC ≠ delete `raw/` | Out of scope; document |
| Configure filters merge | Touch only `since` keys |

**System dependencies:** `#2` SessionRef; unified `llmwiki-state.json` `sync.files`; existing `configure-sources` / `setup.sh` interview entry.

**Out of this PR:** relative stored forms (`90d`); queue/synth state diet; Cursor `ingest_ready`; mandatory headless peek in default estimate.
