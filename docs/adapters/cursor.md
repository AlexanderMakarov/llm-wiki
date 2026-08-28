# Cursor IDE adapter

**Status:** Scaffold — listed for discovery; **not active on bare sync** until [#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2) lands full IDE ingest.
**Module:** `llmwiki.adapters.contrib.cursor`
**Source:** [`llmwiki/adapters/contrib/cursor.py`](../../llmwiki/adapters/contrib/cursor.py)

For **Cursor Agent CLI** sessions (`~/.cursor/chats/`), use the separate [`cursor_cli`](cursor-cli.md) adapter — that path is production for Agent CLI transcripts and participates in `filters.exclude_headless`.

## What it reads

Cursor IDE stores conversation history in per-workspace directories under platform-specific paths:

```
# macOS
~/Library/Application Support/Cursor/User/workspaceStorage/<hash>/

# Linux
~/.config/Cursor/User/workspaceStorage/<hash>/

# Windows
%APPDATA%\Cursor\User\workspaceStorage\<hash>\
```

The adapter checks those roots and discovers `.jsonl` files when present. Full `state.vscdb` parsing for IDE chats is not finished yet ([#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2)).

## Enable it

Listed in `llmwiki adapters` when `workspaceStorage` exists, but **not included on bare `sync`** (`active=no`) until ingest is complete ([#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2)). Use [`cursor_cli`](cursor-cli.md) for Agent CLI sessions.

```bash
python3 -m llmwiki sync --adapter cursor   # explicit only; scaffold
```

## Automated (headless) sessions

No verified automation-launch markers for IDE workspace chats today — `is_headless_session` returns false. Prefer [`cursor_cli`](cursor-cli.md) when you need Agent CLI headless filtering.

## Project slug derivation

Cursor workspace directories use opaque hashes. The adapter truncates the hash to 12 characters and prefixes with `cursor-`:

```
workspaceStorage/a1b2c3d4e5f6789/session.jsonl
  -> cursor-a1b2c3d4e5f6
```

## Schema versions supported

```python
SUPPORTED_SCHEMA_VERSIONS = ["v1"]
```

## Configuration

```json
{
  "adapters": {
    "cursor": {
      "roots": ["~/custom/cursor/path"]
    }
  }
}
```

## Testing the adapter

```bash
python3 -m llmwiki adapters
python3 -m pytest tests/test_adapter_graduation.py -k cursor -v
```

## See also

- [Cursor Agent CLI adapter](cursor-cli.md)
- [Multi-agent setup](../multi-agent-setup.md)
- [`llmwiki/adapters/contrib/cursor.py`](../../llmwiki/adapters/contrib/cursor.py)
