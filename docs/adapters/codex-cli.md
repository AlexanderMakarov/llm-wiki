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

Redaction is the same as for Claude Code — username, API keys, tokens, and emails are scrubbed at convert time. Add Codex-specific path patterns to `redaction.extra_patterns` if needed.

## Testing

```bash
python3 -m llmwiki adapters
python3 -m pytest tests/ -k codex -q
```

## See also

- [Multi-agent setup](../multi-agent-setup.md) — support map + enablement
- [Use with Codex CLI](../tutorials/04-use-with-codex-cli.md) — end-to-end tutorial
- [`llmwiki/adapters/codex_cli.py`](../../llmwiki/adapters/codex_cli.py)
