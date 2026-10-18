# Codex CLI adapter

**Status:** Production
**Module:** `llmwiki.adapters.codex_cli`
**Source:** [`llmwiki/adapters/codex_cli.py`](../../llmwiki/adapters/codex_cli.py)

## What it reads

OpenAI's Codex CLI stores session transcripts as `.jsonl` under:

```
~/.codex/sessions/
    YYYY/MM/DD/rollout-*.jsonl
~/.codex/projects/
    <project>/
        <session-id>.jsonl
```

The adapter checks both roots. Override with `adapters.codex_cli.roots` in `config.json`.

## Enable it

**Core** adapter — included on a bare `llmwiki sync` when either root exists. No `--adapter` flag required.

```bash
python3 -m llmwiki adapters | grep codex_cli
python3 -m llmwiki sync
```

## Project slug derivation

Codex date-buckets sessions under `~/.codex/sessions/YYYY/MM/DD/`, so the directory path is not the project. The adapter reads the first `session_meta` record's `cwd` and uses its basename (lowercased, spaces → dashes). If `cwd` is missing, it falls back to the parent directory name.

## Schema versions supported

```python
SUPPORTED_SCHEMA_VERSIONS = ["v0.x", "v1.0"]
```

Codex-native record types (`response_item`, `event_msg`, …) are normalized into the shared Claude-style format used by the converter.

## Automated (headless) sessions

`filters.exclude_headless` (default on) applies to every coding-agent adapter. Codex has **no verified automation-launch markers** in the store today, so Codex sessions are treated as **not** headless. Interactive chats stay eligible; turn the filter off only if you need other agents' automated runs included. See [Multi-agent setup — What “automated” means](../multi-agent-setup.md#what-automated-headless-means).

## Tokens capture

When a Codex session JSONL includes `event_msg` payloads with `payload.type == "token_count"`, sync maps measured usage into the shared Analytics **Tokens** buckets (input, cache creation, cache read, output) and writes nonempty `token_totals` / `usage/session-tokens.json` the same way as other agents (#324).

**Verified fields** (prefer the last cumulative snapshot):

| Native field | Role |
|---|---|
| `info.total_token_usage` | Session cumulative — use the **last** `token_count` only (do not sum successive totals) |
| `info.last_token_usage` | Per-turn delta — sum **once** across the session when totals are absent |
| `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens` | Mapped into the four Tokens buckets (cache subsets are not double-counted as input) |
| `reasoning_output_tokens` | When present, subtracted from output so reasoning is **not** counted toward Tokens |

**Not Tokens:** `model_context_window` (occupancy / window size) and `rate_limits` / plan percentages. Sessions without measurable `token_count` fields stay missing — they are never written as measured zero.

**Historical backfill:** if `~/.codex/sessions` (or configured roots) still exist, re-run `llmwiki migrate session-tokens` after upgrading so older Codex sessions fill in; fingerprint-changed `sync` covers new or changed sessions. Prefer a fast Codex-only pass when you do not need Claude/Cursor origins yet:

```bash
llmwiki migrate session-tokens --vault /path/to/vault --adapter codex_cli --skip-raw
llmwiki build --vault /path/to/vault
```

See [UPGRADING — session Tokens](../UPGRADING.md#unreleased--session-tokens-usage-store--cursor-cli-capture-325).

## Configuration

```json
{
  "adapters": {
    "codex_cli": {
      "roots": ["~/.codex/sessions", "~/.codex/projects"]
    }
  }
}
```

## Privacy

Redaction is the same as for Claude Code — API keys, tokens, and emails are scrubbed at convert time, and home-path usernames too when `redaction.redact_username: true`. Add Codex-specific path patterns to `redaction.extra_patterns` if needed.

## Testing

```bash
python3 -m llmwiki adapters
python3 -m pytest tests/ -k codex -q
```

## See also

- [Multi-agent setup](../multi-agent-setup.md) — support map + enablement
- [Use with Codex CLI](../tutorials/04-use-with-codex-cli.md) — end-to-end tutorial
- [`llmwiki/adapters/codex_cli.py`](../../llmwiki/adapters/codex_cli.py)
