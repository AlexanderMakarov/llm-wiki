# Cursor Tokens capture — investigation notes (#325 / spec 328)

Contributor working notes (not user docs). Keep placeholders for personal paths (`~/.cursor/…`, `<vault>`). Update when a spike lands new evidence.

Last updated: 2026-10-15 (local review + parallel digs + hook latency benches).

---

## Product preferences (locked this thread)

| Choice | Decision |
|---|---|
| IDE `stop` / `afterAgentResponse` hooks → local JSONL | **Pursue** for forward capture (option A), with latency caveats |
| Awaited hook body | **POSIX shell (`/bin/sh`)** — works under bash and zsh environments; ~3 ms p50 |
| Rust / Go native hook binary | **Reject for shipping** — ~2 ms faster than bash, not worth CI + multi-arch compile/release |
| Python as awaited `stop` body | **Reject** — ~40–90 ms interpreter startup; keep Python for `--install-hook` / `--ingest-stream-json` only |
| Agent CLI PATH shim / stream-json wrapper | **Reject** — too intrusive/rigid |
| Cursor Admin / Usage API | **Postpone** |
| `ConversationTokenDetails` / context-window occupancy in `store.db` | **Reject** for Tokens (compacts/summarizes; wrong metric) |
| Proxy / MITM model traffic | **Reject** (same class of issues as shim) |
| Parse `~/.local/share/cursor-agent` logs | **Checked — not worth it** (dirs empty of session usage) |
| Historical backfill desire | **Strong** — full history not available from `store.db`; partial IDE `state.vscdb` bubble harvest is an optional spike only |

---

## What we checked (and outcomes)

### Dead / wrong for Tokens

| Sink | Outcome |
|---|---|
| `~/.cursor/chats/<ws>/<uuid>/store.db` JSON message blobs | No turn `input_tokens` / `inputTokens` usage objects |
| Same DB protobuf-ish blobs | `ConversationTokenDetails` (used/max + breakdown) = **occupancy**, not per-turn throughput |
| `TurnEndedUpdate` schema in agent JS | Exists on wire (`1 input_tokens` … `4 cache_write_tokens`); **not found persisted** in `store.db` for a session that *did* emit stream-json usage |
| `~/.cursor/projects/**/agent-transcripts/*.jsonl` | `{role, message}` only (matches Kevin / forum 168317) |
| `~/.local/share/cursor-agent/{logs,artifacts}` | Empty of session/usage data; `versions/` is install trees only |
| `ai-tracking/ai-code-tracking.db` | Code-attribution hashes/scores, not LLM turn usage |
| Occupancy ≈ one-turn input on a short chat | Can look similar by coincidence; multi-turn sum of turn inputs ≫ window fill |

### Confirmed forward sources

| Source | Fields | Notes |
|---|---|---|
| Hook `stop` / `afterAgentResponse` (forum Kevin) | `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens` (+ `conversation_id`, `generation_id`) | Parent turn only; optional fields; **do not sum both hooks** for one `generation_id`; `stop` is awaited in agent loop |
| Agent CLI `-p --output-format stream-json` final `result.usage` | camelCase `inputTokens` / `outputTokens` / `cacheReadTokens` / `cacheWriteTokens` | Stdout only unless ingested; interactive TUI without print mode does not leave this on disk |

### Partial historical sink (IDE)

| Sink | Outcome |
|---|---|
| `~/.config/Cursor/User/globalStorage/state.vscdb` → `cursorDiskKV` keys `bubbleId:<composer>:<bubble>` → `tokenCount.{inputTokens,outputTokens}` | Non-zero values observed roughly **2025-09 → 2026-01** on the investigated machine; later bubbles still have `tokenCount` but **zeros**; **no** cache read/write fields; composer/bubble ids ≠ chat folder UUIDs |

**Cutoff interpretation:** the hard stop of non-zero values is consistent with either an **OS reinstall** (DB replaced/reset) or a **Cursor IDE update** that stopped writing live turn counts into `bubbleId` rows (schema left in place). Treat as machine-local evidence, not a universal Cursor guarantee. Do not assume post-cutoff zeros mean “zero tokens used.”

---

## Occupancy vs per-turn (one-liner)

- **Occupancy** = how full the context window is *now* (bounded by max tokens; moves with compact/summary).
- **Per-turn usage** = tokens processed for that agent loop (can sum far above window size across many turns).
- Separating cache vs fresh input is a *sub-problem of turn usage*, not the occupancy question.

---

## Latency benches (hook process + append)

Hypothesis: Cursor awaits `stop`; cost is mostly **process spawn + writing one JSONL line**, especially under concurrent appends.

Method (local Linux, 2026-10-15): warm disk; ~340-byte stop-shaped JSON on stdin; append one line via `O_APPEND` to a temp JSONL under `/tmp/llmwiki-cursor-hook-bench/`; wall time of the whole process (spawn → stdin → write → exit); **n=50** sequential; concurrent = **20 writers × 5 = 100** parallel appends to one file (no `flock`). Host has bash + Go + Rust; **zsh not installed** (not measured). Numbers are indicative for this machine, not a product SLA. Raw JSON: `/tmp/llmwiki-cursor-hook-bench/results.json` (ephemeral).

### Sequential (p50 / p95 / mean / max, ms)

| Handler | p50 | p95 | mean | max | Notes |
|---|---:|---:|---:|---:|---|
| `true` (fork floor) | 1.0 | 2.3 | 1.2 | 3.1 | No I/O |
| **Rust** static binary | **0.76** | 1.5 | 0.85 | 1.6 | Fastest; under fork noise |
| **Go** static binary | **1.4** | 2.4 | 1.5 | 3.5 | Near `true` |
| **bash** `cat`→`printf >>` | **2.8** | 3.7 | 2.9 | 4.7 | Fine if we want zero compile |
| `python3 -m llmwiki.cursor_token_events` | **42** | 54 | 42 | 57 | Interpreter startup dominates (~15× bash) |

Earlier in-session probe of the same Python module was ~70–90 ms (colder / different load); this run settles ~40–55 ms. Still far above shell/native.

### Concurrent append (20×5, same file, no lock)

| Handler | per-op p50 | p95 | wall (100 ops) | lines / JSON integrity |
|---|---:|---:|---:|---|
| Rust | 8.0 | 14 | 49 ms | 100/100 ok |
| Go | 9.8 | 19 | 67 ms | 100/100 ok |
| bash | 14 | 28 | 94 ms | 100/100 ok |
| Python module | 185 | 322 | 1036 ms | 100/100 ok |

No torn/corrupt JSONL lines with single-line `O_APPEND` writes — **`flock` not required** for this payload size on Linux. Concurrent Python pays ~1 s wall for 100 stops; native stays under ~70 ms wall.

**Takeaway for product (locked):** ship a **POSIX `/bin/sh` `stop` handler** (~2.8 ms p50). Do **not** ship Rust/Go binaries (CI + multi-machine builds not worth ~2 ms vs bash). Keep Python for install/ingest only. Prefer single hook (`stop` *or* `afterAgentResponse`, not both) so we do not double-count or double-await.

### Latency summary (same host, for quick paste)

| Role | Handler | Sequential p50 | Concurrent wall (100 ops) |
|---|---|---:|---:|
| Fork floor | `true` | 1.0 ms | — |
| Rejected (native) | Rust / Go | 0.76 / 1.4 ms | 49 / 67 ms |
| **Ship** | **bash / sh append** | **2.8 ms** | **94 ms** |
| Rejected (awaited) | Python module | 42 ms | 1036 ms |

---

## Direction going forward

1. **Forward path:** option A with POSIX shell `stop` (~3 ms p50) installed by `python3 -m llmwiki.cursor_token_events --install-hook`; map inclusive→disjoint in llmwiki when reading JSONL.
2. **Historical:** cannot invent from `store.db`; optional one-shot harvest of pre-cutoff `bubbleId.tokenCount` (input/output only, incomplete); cutoff = OS reinstall **or** IDE update that stopped writing non-zero values (schema retained with zeros).
3. **Not building:** Rust/Go hook binaries, CLI shim, Admin API (yet), occupancy→Tokens, MITM, cursor-agent log parser.

---

## References

- Forum: https://forum.cursor.com/t/how-to-obtain-token-usage-per-request/168317
- Spec: `technical-considerations.md` Appendix A; `functional-spec.md`
- Package (feature branch): `llmwiki/cursor_token_events.py`, `llmwiki/cursor_token_usage.py`
