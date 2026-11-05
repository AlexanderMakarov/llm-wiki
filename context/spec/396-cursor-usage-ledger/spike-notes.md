# Cursor usage ledger spike (#396)

Contributor notes — no personal paths or message text.

## Schema (global `state.vscdb`)

| Location | Role |
|---|---|
| Table `cursorDiskKV`, keys `bubbleId:<composerId>:<bubbleId>` | Per-turn bubble JSON; measurable field `tokenCount.inputTokens` / `outputTokens` (camelCase). No cache read/write in this shape. |
| Table `composerHeaders` | `composerId`, `lastUpdatedAt` for activity timestamps |
| Table `ItemTable`, key `cursorAuth/accessToken` | Auth only — **never read for Tokens** (#396 privacy) |

## Join key

- **IDE Composer:** `composerId` UUID = `cursor_ide` adapter `sessionId` = raw frontmatter `sessionId`.
- **Agent CLI:** chat folder UUID = `store.db` meta `agentId`. **Not present** in global `cursorDiskKV` on probed installs — ledger does not cover CLI transcripts.

## Session kinds covered

| Kind | Ledger |
|---|---|
| IDE Composer (interactive) | Yes, when bubbles carry non-zero `tokenCount` |
| IDE spawned subagents | Same DB; ingest policy still uses `exclude_headless` |
| Agent CLI (`cursor-agent`) | No — use hooks / stream-json / optional API (#356) |
| ACP / AO headless | No — use optional API (#356) unless future schema adds ids |

## Precedence (locked)

1. `~/.cursor/llmwiki-cursor-token-events.jsonl` (hook / stream-json ingest)
2. Vault cache `usage/cursor-usage-ledger-cache.json`
3. Opt-in `cursor_usage_api` (#356)

## #356 decision

Keep **#356** as opt-in fallback for CLI/ACP gaps the ledger does not cover. Do not expand API work until ledger coverage is measured on target machines.
