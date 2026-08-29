# Cursor IDE store inventory (redacted)

Probed read-only on operator Linux install for AWOS spec `176-cursor-ide-ingest` / [#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2). **No message text, paths, or usernames recorded.**

## Global DB

- Path pattern: `~/.config/Cursor/User/globalStorage/state.vscdb` (Linux)
- Tables seen: `ItemTable`, `cursorDiskKV`, `composerHeaders`

### `cursorDiskKV` key prefixes (counts are environment-specific)

| Prefix | Role |
|---|---|
| `composerData:<composerId>` | Thread metadata + embedded `conversation` list |
| `bubbleId:<composerId>:<bubbleId>` | Per-message bubble payloads |
| others (`agentKv`, `checkpointId`, …) | Out of scope for ingest |

Approx on probe machine: ~1k `composerData`, ~77k `bubbleId`.

### `composerData` JSON fields (sample)

Always/common: `composerId`, `createdAt`, `lastUpdatedAt`, `status`, `forceMode`, `conversation` (list), `text` / `richText`, `context`, tabs/capabilities maps, …

Optional: `name`, `isAgentic` (rare on thread object).

**Not present** on this Cursor build (issue body named these): `conversationMap`, `fullConversationHeadersOnly`.

**Ordering:** use `conversation` list order; each element has at least `bubbleId` (+ often `type` / text). Full payload still lives under `bubbleId:…` rows.

### `bubbleId` JSON fields (sample)

- `type`: `1` = user, `2` = assistant (confirmed)
- `text`, sometimes `richText`
- `toolResults` (list), `allThinkingBlocks`, `toolFormerData` (dict, some assistant turns)
- `isAgentic` (bool on bubbles)
- `createdAt` may be absent on some bubbles; prefer thread `createdAt` / `lastUpdatedAt` for session mtime
- `unifiedMode` (int) on some user bubbles

### `composerHeaders` table (preferred for flags / workspace)

Columns: `composerId`, `workspaceId`, `createdAt`, `lastUpdatedAt`, `isArchived`, `isSubagent`, `recency`, `checkpointAt`, `value`

Probe counts (illustrative): hundreds of headers; dozens `isArchived=1`; dozens `isSubagent=1`.

**Headless rule candidate:** `isSubagent = 1` → spawned/nested IDE agent; user-facing Composer when `isSubagent` is 0/false/NULL.

**Archive:** `isArchived = 1` still ingest; same `composerId`.

**Workspace:** `workspaceId` often matches a `workspaceStorage/<hash>/` directory name (hex, length 32). On this machine: **no overlap** between those hashes and `~/.cursor/chats/<hash>/` directory names — Agent CLI chat hashes are a different id space. Slug v1: `cursor-<workspaceId[:12]>` when `workspaceId` resolves to workspaceStorage; document that Agent CLI alignment may need a second join (folder URI / #126) when hashes diverge.

## Per-workspace DB

`workspaceStorage/<hash>/state.vscdb` has `ItemTable` keys such as `composer.composerData` (association aid). Prefer `composerHeaders.workspaceId` when present.

## Loading strategy (locked from probe)

1. Enumerate sessions from `composerHeaders` when the table exists (flags + `workspaceId`); fall back to `composerData:%` keys.
2. `composerId` is a UUID (`bubbleId:<uuid>:<uuid>`).
3. Messages: load all `bubbleId:<composerId>:%` rows. Prefer order from `composerData.conversation[].bubbleId` when those ids match bubble rows; otherwise order by bubble `createdAt` if present, else key order.
4. `composerData.conversation` sometimes embeds partial bubble fields and sometimes is empty while `bubbleId:*` rows still exist — **always prefer full `bubbleId` rows for content**.
5. Headless: `composerHeaders.isSubagent == 1`.
6. Archived: `composerHeaders.isArchived == 1` (still ingest).
7. Project slug: `cursor-<workspaceId[:12]>` when `workspaceId` is a 32-char hex matching `workspaceStorage/<id>/`; Agent CLI `~/.cursor/chats/<hash>/` did **not** overlap those ids on the probe machine — document honestly for #126.
