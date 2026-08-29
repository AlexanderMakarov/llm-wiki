# Technical Specification: Cursor IDE composer ingest (`cursor` adapter)

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** Aleksandr Makarov
- **Issue:** [#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2)

---

## 1. High-Level Technical Approach

Finish the contrib `cursor` adapter by reading Cursor IDE’s **global** SQLite store (`…/User/globalStorage/state.vscdb`, table `cursorDiskKV`), treating each `composerData:<composerId>` thread as one session — including archived threads — and mapping bubbles into the shared Claude-style record schema already used by `cursor_cli`.

**First-class non-file sessions.** Composer threads are DB rows, not files. This change adds a reusable `SessionRef` discovery contract on `BaseAdapter` so adapters whose stores are SQLite (or other non-file) databases can participate in sync/watch/state without fake files or one-off `stat` hacks. File-backed adapters keep today’s path-based behavior via a default that wraps `discover_sessions()` + `path.stat()`. Future agentic tools that store chats in DBs reuse the same contract.

Project slugs use the **same** `cursor-<workspace-hash[:12]>` form as `cursor_cli` when the IDE thread can be associated with a workspace hash — preparing [#126](https://github.com/AlexanderMakarov/llm-wiki/issues/126) without implementing full aggregation.

**IDE headless:** distinguish user-facing Composer threads from nested / spawned IDE agents (children of a main composer) via verified markers from a local Cursor install; default `filters.exclude_headless` skips the latter (same policy as #180 / `cursor_cli`).

Secondary: one aggregate stderr warning when an adapter discovers sessions but parses zero records for all of them.

**Testing:** probe the operator’s local Cursor install first to lock schema and headless markers; then commit **synthetic** fixtures derived from that shape (never real transcripts or personal paths).

No new runtime dependencies (stdlib `sqlite3` + `json` only). No materializing stub/sidecar files on disk.

---

## 2. Proposed Solution & Implementation Plan

### Architecture — `SessionRef` (reusable non-file support)

Introduce a small immutable session handle (name may be `SessionRef`; live in `llmwiki/adapters/base.py` or adjacent module):

| Field | Role |
|---|---|
| `key` | Portable identity fragment for sync state: final state entry is `\<adapter>::\<key>` (no absolute home path required). File adapters: home-relative path string (today’s `_portable_state_key` relative part). IDE: e.g. `composer/\<composerId>`. |
| `mtime` | Unix seconds; **always adapter-provided** (file `st_mtime` or max row `createdAt`). |
| `locator` | Opaque string the adapter understands in `load_records` / `derive_project_slug` / logging (real filesystem path for JSONL/`store.db`, or a logical locator such as `cursor-ide:composer:\<id>` — **not** a fake file to create). |

**BaseAdapter API:**

- `discover_session_refs(self) -> list[SessionRef]` — **preferred** discovery entry. Default implementation: call existing `discover_sessions()`, wrap each existing `Path` as `SessionRef(key=home-relative-or-str, mtime=stat, locator=str(path))`.
- Keep `discover_sessions() -> list[Path]` for file adapters and backward compatibility; IDE overrides **`discover_session_refs`** (and may leave `discover_sessions` empty or unused by convert).
- `load_records(self, locator: str | Path)` / `derive_project_slug(self, locator: …)` — accept locator from `SessionRef` (Path still works for file adapters).
- **No** one-off `session_mtime(path)`-only escape hatch as the design center; mtime lives on `SessionRef` so every future DB adapter gets identity + freshness together.

**`convert_all` / `watch`:** iterate `adapter.discover_session_refs()`; use `ref.mtime` and `ref.key` for unchanged detection / state; pass `ref.locator` into load/slug. Do not require `Path(locator).stat()` for non-file refs.

This is **support for DB-row (and other non-file) sessions**, not a Cursor-specific hack.

### Cursor IDE adapter

| Piece | Change |
|---|---|
| `llmwiki/adapters/contrib/cursor.py` | `discover_session_refs` from global `cursorDiskKV`; `load_records` / `normalize_records`; workspace-hash slug; `is_headless_session` from verified IDE markers |
| `llmwiki/adapters/base.py` (+ maybe tiny `session_ref.py`) | `SessionRef` + default `discover_session_refs` |
| `llmwiki/convert.py` | Drive off `SessionRef`; R6 zero-parse warning |
| `llmwiki/watch.py` | Drive off `SessionRef.mtime` / keys |
| Docs / CHANGELOG / support map | IDE → working; headless rule; shared project-id form |

No changes to synth, build, or MCP beyond any frontmatter fields already written by convert.

### Session discovery & identity (IDE)

1. Resolve **global** DB paths (platform defaults):
   - macOS: `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb`
   - Linux: `~/.config/Cursor/User/globalStorage/state.vscdb`
   - Windows: `~/AppData/Roaming/Cursor/User/globalStorage/state.vscdb`
2. Open read-only (`file:…?mode=ro`). Enumerate `composerData:%`. Keep every thread with ≥1 loadable bubble (**archived included** — same `composerId` before/after archive).
3. Emit `SessionRef(key=f"composer/{composerId}", mtime=…, locator=f"cursor-ide:composer:{composerId}")` (exact locator scheme locked in code + docs; no files created).
4. `load_records(locator)`: open global DB; load metadata + `bubbleId:<id>:*`; order by `conversationMap` / `fullConversationHeadersOnly` then `createdAt`; inject meta record (`type: cursor_ide_meta`) with `sessionId`, `slug`, `timestamp`, optional `isArchived` (never filters), workspace hints, and **headless-relevant fields** once identified.

**Assumption:** Per-workspace `state.vscdb` files are **not** sessions; used only for workspace-hash / composer association. Stop treating bare `state.vscdb` paths as discoverable sessions.

### Normalize / render

| IDE field | Shared schema |
|---|---|
| bubble `type` 1 | `user` + string content (`text`, else stripped `richText`) |
| bubble `type` 2 | `assistant` blocks: text; `allThinkingBlocks` → `thinking`; `toolResults` → `tool_use` when structured, else text |
| meta `createdAt` | ISO `timestamp` for `started` / filename |
| `composerId` | `sessionId` + short `slug` |

Keep meta through `normalize_records` (same pattern as `cursor_cli_meta`).

### Project slug (R3 / #126 prep)

| Priority | Rule |
|---|---|
| 1 | Associate composer → workspace hash (per-workspace `composer.composerData`, `workspace.json`, bubble `workspaceProjectDir` / `workspaceUris`). Emit **`cursor-<hash[:12]>`** — same form as `cursor_cli`. |
| 2 | Folder path known but hash unresolved → **do not** use basename-only slug; fall through to (3). |
| 3 | Unmatched: `cursor-<composerId[:12]>` (documented as unmatched). |

Optional shared helper `_cursor_workspace_slug(hash: str) -> str` if it avoids duplication without coupling stores. `cursor_cli` behavior otherwise unchanged.

**Research on local install:** confirm Agent CLI `~/.cursor/chats/<hash>/` matches IDE `workspaceStorage/<hash>/` when possible.

### IDE headless (spawned vs user-facing)

- **Goal:** user-facing Composer stays eligible; agents **spawned from** a main session/composer are headless under default `filters.exclude_headless`.
- **Method:** probe the operator’s local Cursor DB for parent/child / subagent / nested-agent markers on `composerData` and bubbles (names TBD from evidence — do **not** invent fields).
- Map verified markers into meta + `is_headless_session` (presence-based, similar spirit to `cursor_cli`’s `subagentInfo`).
- If local probe finds **no** reliable marker in this PR’s window: implement the hook returning `False`, document “markers not yet verified,” and leave a tracked follow-up — but the **intent** of this change is to land detection when evidence exists (in-scope for #2, extending #180’s IDE gap).
- Docs / support map: update Cursor IDE from “N/A until detect” to the concrete rule once locked.
- Precedence: same as other adapters — `exclude_headless` gates these; do not overload Claude’s `include_subagents` path unless evidence shows they are the same concept.

### R6 zero-parse warning

Per-adapter: if discovered ≥1 and all yield empty after load/normalize/filter, one stderr line naming the adapter. Do not warn for headless/temp/subagent skips of non-empty sessions.

### Files (expected)

- `llmwiki/adapters/base.py` (and/or `session_ref.py`) — `SessionRef`, default `discover_session_refs`
- `llmwiki/adapters/contrib/cursor.py` — IDE parser + headless
- `llmwiki/convert.py`, `llmwiki/watch.py` — `SessionRef` loop
- `tests/test_session_ref.py` — default wrap + convert with non-file ref
- `tests/test_cursor_ide_adapter.py` — fixtures derived from local probe
- Graduation / cross-platform / #180 support-map tests updated
- Docs + `CHANGELOG.md`

### Config

Keep `adapters.cursor.roots` for workspaceStorage override. Global DB: platform defaults; tests use tmp fixtures / monkeypatch.

---

## 3. Impact and Risk Analysis

| Risk | Mitigation |
|---|---|
| Schema / headless marker drift | Local probe first; pin observed fields in docstring; synthetic fixtures; empty → filtered + R6 |
| Convert/watch breakage for file adapters | Default `discover_session_refs` preserves path+stat behavior; regression tests |
| Workspace hash ≠ Agent CLI hash | Local confirm; unmatched fallback; docs honesty |
| Over-filtering “headless” | Only verified markers; filter-off escape; document rule |
| Privacy | Probe locally; never commit real transcripts, bubble text, or absolute homes in fixtures/PRs |
| Broader BaseAdapter surface | Intentional reusable contract; Cursor is first consumer |

**Dependencies:** convert, watch, render/frontmatter. No synth/build redesign.

---

## 4. Testing Strategy

1. **Local probe (first):** read-only inspect operator Cursor `globalStorage/state.vscdb` (+ a workspace DB if needed) to lock: key shapes, bubble fields, archive flag, workspace association, and **spawned-agent / parent markers**. Capture structure notes in the worktree only (or ephemeral); redacted field inventory may land in adapter docstring — no personal content in git.
2. **Synthetic fixtures:** build minimal `cursorDiskKV` DBs in tests from the probed shape (user/assistant/archived/headless/interactive; shared workspace hash).
3. **Contract:** `SessionRef` default path wrap; convert unchanged-detection via `ref.mtime`; IDE discover/load/normalize/slug/headless.
4. **Regression:** `cursor_cli`, #180 map (IDE wording may change), graduation/cross-platform paths.
5. **Manual smoke:** `python3 -m llmwiki sync --adapter cursor` → converted > 0; archived kept; headless skipped when markers present; project slug matches Agent CLI for a known shared workspace.

---

## 5. Open questions locked for implement (assumptions)

1. **`SessionRef` + `discover_session_refs`** — first-class non-file support; no stub files; not a Cursor-only `session_mtime` hack.
2. **Archived** — ingest; same `composerId`; optional meta flag only.
3. **Slug** — hash-aligned with `cursor_cli` when resolvable; no basename-only friendly slug in v1.
4. **Headless** — in scope for IDE spawned agents; markers from local probe; `exclude_headless` applies.
5. **Bare sync enablement** — still `#182` / `--adapter cursor`.
6. **Full #126 aggregation** — out of scope (identifier alignment only).
