# Cursor IDE adapter

**Status:** Production — Composer ingest from global `state.vscdb`
**Registry name:** `cursor_ide` (alias `cursor` still resolves for CLI / old configs)
**Module:** `llmwiki.adapters.contrib.cursor_ide`
**Source:** [`llmwiki/adapters/contrib/cursor_ide.py`](../../llmwiki/adapters/contrib/cursor_ide.py)

For **Cursor Agent CLI** sessions (`~/.cursor/chats/`), use the separate [`cursor_cli`](cursor-cli.md) adapter.

## What it reads

Cursor IDE stores Composer threads in the **global** SQLite DB:

```
# macOS
~/Library/Application Support/Cursor/User/globalStorage/state.vscdb

# Linux
~/.config/Cursor/User/globalStorage/state.vscdb

# Windows
%APPDATA%\Cursor\User\globalStorage\state.vscdb
```

Table `composerHeaders` lists threads (`composerId`, `workspaceId`, `isArchived`, `isSubagent`). Message bodies live in `cursorDiskKV` under `bubbleId:<composerId>:<bubbleId>` (`type` 1 = user, 2 = assistant). Per-workspace `workspaceStorage/<hash>/` is used only for association when needed — not as the session file itself.

Each Composer thread is one sync session (non-file `SessionRef`). Archived threads are still ingested under the same `composerId`.

## Enable it

Ingest works via explicit adapter selection:

```bash
python3 -m llmwiki sync --adapter cursor_ide
# alias still works:
python3 -m llmwiki sync --adapter cursor
```

`select_sync_adapters` bypasses `ingest_ready` for `--adapter`, so this always runs when the store is present. Bare `llmwiki sync` still skips Cursor IDE while `ingest_ready = False` — intentional so a default sync does not flood from a large historical Composer DB. Set `filters.since` or `adapters.cursor_ide.since` (or pass `--since`) before flipping `ingest_ready` locally; see [Sync lookback](../configuration-reference.md#sync-lookback).

Listed in `llmwiki adapters` / `configure-sources` as **`cursor_ide`**. Use [`cursor_cli`](cursor-cli.md) for Agent CLI sessions under `~/.cursor/chats/`.

## Automated (headless) sessions

With `filters.exclude_headless` (default **true**), threads with `composerHeaders.isSubagent = 1` (agents spawned from a parent Composer) are skipped. User-facing Composer chats stay eligible. Set `"exclude_headless": false` to include spawned threads.

## Project slug derivation

When `workspaceId` is present (typically the `workspaceStorage` directory hash), the slug is `cursor-<first-12-chars>` — the **same form** as [`cursor_cli`](cursor-cli.md). Agent CLI’s `~/.cursor/chats/<hash>/` directory names may differ from IDE workspace hashes on some installs; full cross-adapter project merge is [#126](https://github.com/AlexanderMakarov/llm-wiki/issues/126).

## Configuration

```json
{
  "adapters": {
    "cursor_ide": {
      "global_db": "~/.config/Cursor/User/globalStorage/state.vscdb",
      "roots": ["~/.config/Cursor/User/workspaceStorage"]
    }
  }
}
```

`global_db` is optional (platform defaults apply). `roots` still override workspaceStorage paths used for association. A legacy `adapters.cursor` block is still read if `adapters.cursor_ide` is absent.

## Testing the adapter

```bash
python3 -m llmwiki adapters
python3 -m pytest tests/test_cursor_ide_adapter.py -q
```

## See also

- [Cursor Agent CLI adapter](cursor-cli.md)
- [Multi-agent setup](../multi-agent-setup.md)
- [`llmwiki/adapters/contrib/cursor_ide.py`](../../llmwiki/adapters/contrib/cursor_ide.py)
