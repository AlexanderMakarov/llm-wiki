# Codex CLI Tokens capture — investigation notes (#324 / spec 329)

Contributor working notes (not user docs). Use placeholders only (`~/.codex/sessions/`, `<vault>`, `<session-uuid>`, `<user>`). No real usernames, hostnames, personal vault roots, or live session UUIDs.

Last updated: 2026-10-16 (on-disk Codex JSONL rollouts sampled 2026-09+; mapping locked in `technical-considerations.md`).

---

## Verified native fields (Tokens)

Source: `event_msg` records with `payload.type == "token_count"` under `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` (also `~/.codex/projects/` when present).

| Native path | Role |
|---|---|
| `payload.info.total_token_usage` | **Session cumulative snapshot** — prefer the **last** `token_count` event only |
| `payload.info.last_token_usage` | Per-turn delta — **sum once** across the session when totals are absent (sampled session: sum of lasts equals final total) |

Measured fields inside either blob (when present):

| Field | Notes |
|---|---|
| `input_tokens` | Inclusive of cache read/write in sampled rollouts |
| `cached_input_tokens` | Cache read subset of input |
| `cache_write_input_tokens` | Cache write |
| `output_tokens` | Inclusive of reasoning when `reasoning_output_tokens` is also present |
| `reasoning_output_tokens` | Subset of output — **omit from Tokens** when the key is present |
| `total_tokens` | Informational; mapper does not treat it as a fifth bucket |

---

## Rejected (never Tokens)

| Field / block | Why |
|---|---|
| `info.model_context_window` | Context-window size / occupancy, not measured turn throughput |
| `rate_limits` / plan `used_percent` | Billing or plan limits, not the four Tokens buckets |

Occupancy or rate-limits alone → no mapped usage (`None`); do not invent zeros.

---

## Cumulative vs last (no double-count)

- Multiple `token_count` events in one session carry **monotonic** `total_token_usage` snapshots.
- **Correct:** take the **last** `total_token_usage`, **or** (if totals missing) sum `last_token_usage` **once** across events.
- **Wrong:** sum successive `total_token_usage` values (that double-counts earlier turns).

---

## Reasoning omission

- When `reasoning_output_tokens` is **present** on the chosen blob: map `output` as `max(0, output_tokens - reasoning_output_tokens)`.
- When the key is **absent**: use `output_tokens` as-is; do not invent a reasoning split (honesty limit — document, do not fabricate).

Synthetic fixture (repo): `tests/fixtures/codex_token_count_session.jsonl`.

---

## Redacted structure (illustrative)

Placeholders only — numbers are synthetic:

```json
{
  "type": "event_msg",
  "timestamp": "2026-09-15T12:00:00.000Z",
  "payload": {
    "type": "token_count",
    "info": {
      "total_token_usage": {
        "input_tokens": 400,
        "cached_input_tokens": 50,
        "cache_write_input_tokens": 10,
        "output_tokens": 90,
        "reasoning_output_tokens": 30,
        "total_tokens": 490
      },
      "last_token_usage": {
        "input_tokens": 300,
        "cached_input_tokens": 50,
        "cache_write_input_tokens": 10,
        "output_tokens": 70,
        "reasoning_output_tokens": 30,
        "total_tokens": 370
      },
      "model_context_window": 200000
    },
    "rate_limits": {
      "primary": { "used_percent": 2.5 }
    }
  }
}
```

Session path shape (never commit real host paths):

```text
~/.codex/sessions/YYYY/MM/DD/rollout-<session-uuid>.jsonl
```

---

## Mapping into shared Tokens (product lock)

Target Claude-shaped `message.usage` (what `compute_token_totals` already sums):

| llmwiki bucket | Source |
|---|---|
| `input` | `max(0, input_tokens - cached_input_tokens - cache_write_input_tokens)` (clamp) |
| `cache_creation` | `cache_write_input_tokens` |
| `cache_read` | `cached_input_tokens` |
| `output` | ordinary output only (reasoning subtracted when key present) |

Package: `llmwiki/codex_token_usage.py`; adapter wire-up in `llmwiki/adapters/codex_cli.py`.

---

## Historical backfill

When `~/.codex/sessions` (and/or configured roots) still exist on the machine:

```bash
llmwiki migrate session-tokens --vault <vault> --dry-run
llmwiki migrate session-tokens --vault <vault>
llmwiki build --vault <vault>
```

Steady-state: fingerprint-changed `llmwiki sync` also upserts nonempty Codex usage into `usage/session-tokens.json` and raw `token_totals`. Unchanged historical sessions need migrate (or a forced re-sync) after this capture lands — the existing `session-tokens` migrate already discovers `codex_cli` origins; no new migrate subcommand.

Unavailable = sessions with no usable measured `token_count` fields (or store deleted) → stay missing, not measured zero.

---

## References

- Spec: `functional-spec.md`, `technical-considerations.md`
- Package: `llmwiki/codex_token_usage.py`, `llmwiki/adapters/codex_cli.py`
- User docs: `docs/adapters/codex-cli.md`, `docs/UPGRADING.md` (session Tokens / Codex note)
