# Cursor Agent CLI adapter

**Status:** Production
**Module:** `llmwiki.adapters.contrib.cursor_cli`
**Source:** [`llmwiki/adapters/contrib/cursor_cli.py`](../../llmwiki/adapters/contrib/cursor_cli.py)

This is **not** the Cursor IDE adapter. IDE workspace chats use [`cursor`](cursor.md) and are a separate, incomplete ingest path ([#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2)).

## What it reads

Cursor Agent CLI (`cursor-agent`) stores each chat under:

```
~/.cursor/chats/<workspace-hash>/<chat-uuid>/store.db
```

`store.db` is a content-addressed blob store. The adapter reconstructs conversation order from the root tree blob and keeps user prompts verbatim; system / tool-result noise is dropped for the wiki.

Store meta ``agentId`` becomes frontmatter ``sessionId`` (and a short ``slug``) — never the filesystem stem ``store``. Meta ``createdAt`` (unix ms) becomes the session ``timestamp`` / ``started`` date used in raw filenames.

## Enable it

Runs on bare `llmwiki sync` when `~/.cursor/chats/` exists. Override roots in `adapters.cursor_cli` or run `llmwiki configure-sources`.

```bash
python3 -m llmwiki sync                    # includes cursor_cli when store present
python3 -m llmwiki sync --adapter cursor_cli   # this source only
```

## Automated (headless) sessions

With `filters.exclude_headless` (default **true**), a Cursor Agent CLI session is skipped when store meta has:

- `subagentInfo` present (nested Task / subagent runs, including second-model children), **or**
- `approvalMode` equal to `auto-review` (non-interactive auto-review runs)

Interactive top-level Agent sessions (no `subagentInfo`, not `auto-review`) stay eligible. Those nested/auto-review sessions are classified under **`exclude_headless`**, not by changing `include_subagents`. Set `"exclude_headless": false` to include them.

See [Multi-agent setup — What “automated” means](../multi-agent-setup.md#what-automated-headless-means).

## Configuration

```json
{
  "adapters": {
    "cursor_cli": {
      "roots": ["~/.cursor/chats"]
    }
  }
}
```

## See also

- [Cursor IDE adapter](cursor.md) — workspaceStorage / `#2`
- [Multi-agent setup](../multi-agent-setup.md)
- [`llmwiki/adapters/contrib/cursor_cli.py`](../../llmwiki/adapters/contrib/cursor_cli.py)
