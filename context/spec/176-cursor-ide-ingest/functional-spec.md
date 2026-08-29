# Functional Specification: Cursor IDE composer ingest via `cursor` adapter

- **Roadmap Item:** GitHub [#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2) — Cursor IDE sessions not ingested (`state.vscdb` / `cursorDiskKV`)
- **Status:** Approved
- **Author:** Aleksandr Makarov
- **Related:** [#180](https://github.com/AlexanderMakarov/llm-wiki/issues/180) skip-automated policy (this change fills the Cursor **IDE** spawned-agent gap left there); [#182](https://github.com/AlexanderMakarov/llm-wiki/issues/182) bare-sync adapter enablement (out of scope); [#126](https://github.com/AlexanderMakarov/llm-wiki/issues/126) one project / one page (this change only aligns Cursor IDE + Agent CLI identifiers so #126 can merge later); [`cursor_cli`](../../../docs/adapters/cursor-cli.md) Agent CLI adapter (separate store, already works)

---

## 1. Overview and Rationale (The "Why")

Cursor users accumulate substantial chat history inside the **IDE** (Composer threads), stored in SQLite `state.vscdb` files — especially the global `globalStorage/state.vscdb` table `cursorDiskKV`. The contrib `cursor` adapter today discovers `state.vscdb` paths but never parses them; the default JSONL loader returns zero records, so **every IDE session is silently dropped** into the sync `filtered` bucket.

Meanwhile the **`cursor_cli`** adapter already ingests Cursor **Agent CLI** (`cursor-agent`) chats from `~/.cursor/chats/…/store.db`. Users and docs must keep those two sources distinct — fixing Agent CLI does not close this issue. For later project aggregation ([#126](https://github.com/AlexanderMakarov/llm-wiki/issues/126)), both Cursor adapters should emit the **same project identifier** when they talk about the same workspace, even though each adapter still discovers its own sessions.

**Desired outcome.** Running `llmwiki sync --adapter cursor` converts real IDE composer threads into `raw/sessions/*.md` with usable user/assistant content, project identifiers that match Agent CLI for the same workspace, and timestamps — the same downstream wiki/build path other coding-agent adapters use.

**Success.** A developer with Cursor IDE installed sees composer threads convert instead of `N discovered, N filtered`; archived threads still convert as the same session; IDE and Agent CLI sessions for one workspace share a project id; docs and the adapter support map describe IDE ingest as working; CI proves parsing with synthetic SQLite fixtures (no real session data committed).

---

## 2. Functional Requirements (The "What")

### R1 — Discover IDE composer threads as sessions

- **As a** Cursor IDE user, **I want** each composer thread treated as one sync session, **so that** multi-thread history is not collapsed into one workspace file or dropped entirely.

- **Acceptance Criteria:**
  - [ ] Given Cursor's global `state.vscdb` contains `cursorDiskKV` rows with keys `composerData:<composerId>`, when I run `llmwiki sync --adapter cursor`, then each non-empty composer thread appears as a distinct discovered session (count ≥ number of threads with at least one user or assistant bubble).
  - [ ] Given a composer thread is archived (`isArchived` true in metadata), when I sync, then the thread is **still ingested** — archive status does not drop it and does not create a second identity; the same `composerId` before and after archive remains one session.
  - [ ] Given a composer thread has zero message bubbles after parsing, when I sync, then it lands in `filtered` (same as other empty sessions).
  - [ ] Discovery works on macOS, Linux, and Windows default Cursor paths (configurable `adapters.cursor.roots` still overrides workspace roots only; global store path follows platform conventions documented in the adapter).

### R2 — Parse bubbles and render conversation content

- **As a** wiki maintainer, **I want** IDE messages loaded from `bubbleId:<composerId>:<bubbleId>` rows and ordered correctly, **so that** raw markdown reflects the conversation the user saw in Composer.

- **Acceptance Criteria:**
  - [ ] Given a composer thread with ordered bubbles, when records are loaded, then message order matches `conversationMap` / `fullConversationHeadersOnly` when present, otherwise falls back to `createdAt` ascending.
  - [ ] Given bubble `type` `1` (user), when normalized, then output is a shared-schema user record with plain text from `text` (prefer `text`; use `richText` only when `text` is empty — strip tags if needed).
  - [ ] Given bubble `type` `2` (assistant), when normalized, then output is a shared-schema assistant record: `text` → text blocks; `allThinkingBlocks` → thinking blocks (same fidelity posture as `cursor_cli`: thinking kept in record shape, dropped by default renderer); `toolResults` → `tool_use`-style blocks where structure allows, otherwise appended as text.
  - [ ] Given thread metadata includes `createdAt`, when a session is converted, then `started` / filename timestamp reflects that value (unix ms heuristic, same as Agent CLI).
  - [ ] Given `composerId`, when frontmatter is rendered, then `sessionId` / slug derivation prefers composer id over filesystem stem.

### R3 — Shared project identity with Cursor Agent CLI (#126 prep)

- **As a** user who works in both Cursor IDE and Cursor Agent CLI on the same codebase, **I want** both adapters to attach the **same project identifier** to those sessions, **so that** a future “one project, one page” change (#126) can merge them without inventing a second ID scheme.

- **Acceptance Criteria:**
  - [ ] Given an IDE composer thread that can be associated with a Cursor workspace whose Agent CLI chats live under `~/.cursor/chats/<workspace-hash>/…`, when deriving the project slug, then the IDE adapter emits the **same** form Agent CLI already uses: `cursor-<first-12-chars-of-workspace-hash>`.
  - [ ] Given the IDE thread exposes a folder path (`workspaceProjectDir` / workspace URIs) but the workspace hash is not yet known, when deriving the slug, then the adapter still prefers a hash-aligned id when one can be resolved from Cursor’s workspace storage / workspace.json association — **not** a basename-only slug that would diverge from `cursor_cli`.
  - [ ] Given no workspace association at all, when deriving the slug, then fallback is `cursor-<composerId-prefix>` (stable, unique enough for filenames) — documented as “unmatched workspace,” not claimed identical to Agent CLI.
  - [ ] Absolute home paths and OS usernames never appear in emitted slugs or committed fixtures (privacy rules).
  - [ ] This change does **not** implement full #126 aggregation across clones/worktrees/adapters; it only makes Cursor IDE and Cursor Agent CLI **emit matching identifiers** when they share a workspace hash.

### R4 — Incremental sync / mtime behavior

- **As a** user who syncs repeatedly, **I want** unchanged composer threads skipped and updated threads re-converted, **so that** sync stays fast.

- **Acceptance Criteria:**
  - [ ] Given a composer thread whose latest bubble `createdAt` is unchanged since last sync, when I sync again without `--force`, then the session counts as `unchanged`.
  - [ ] Given new bubbles were appended to a thread (including after it was archived), when I sync, then the session is re-converted under the same session identity.
  - [ ] Session identity in sync state uses a portable key derived from adapter name + composer id (not a non-existent filesystem path).

### R5 — Do not break or conflate Agent CLI ingest

- **As a** reader of docs and sync output, **I want** IDE and Agent CLI adapters clearly separated, **so that** I enable the right source.

- **Acceptance Criteria:**
  - [ ] `cursor_cli` behavior and tests remain unchanged by this work except any shared private helpers that are behavior-neutral **or** an intentional, tested change that documents how both adapters share the `cursor-<12-char-hash>` project id form (R3).
  - [ ] Docs state: `cursor` = IDE Composer; `cursor_cli` = Agent CLI — with current enablement (`--adapter cursor` / `--adapter cursor_cli`), and that both use the same project-id form when the workspace hash is known.
  - [ ] Acceptance test #180 slice `test_support_map_distinguishes_cursor_cli_from_ide` still passes (IDE may move from "scaffold" to "working" wording).

### R5b — Skip spawned IDE agents (keep user-facing Composer)

- **As a** Cursor IDE user with the default skip-automated setting on, **I want** nested / spawned agents started from a main Composer session skipped, while my own Composer chats stay eligible, **so that** silent child runs do not flood the wiki the way Agent CLI auto-review already does not.

- **Acceptance Criteria:**
  - [ ] Given a user-facing Composer thread (no verified “spawned from parent” marker), when I sync with the default skip-automated setting, then the session is converted.
  - [ ] Given an IDE agent thread that is verifiably spawned from a parent Composer / main session (markers confirmed on a real Cursor install), when I sync with the default setting, then the session is skipped as automated/headless (same aggregate sync summary style as other adapters).
  - [ ] Given the skip-automated setting is off, when I sync, then those spawned threads are included.
  - [ ] Docs state what counts as automated for Cursor IDE once markers are locked; if a reliable marker cannot be confirmed in this change, document that gap explicitly rather than inventing fields.

### R6 — Clearer feedback when an adapter cannot parse (secondary)

- **As a** user who enabled a contrib adapter, **I want** a hint when **every** discovered session produced zero records, **so that** I know the adapter is a scaffold or misconfigured — not that my chats are empty.

- **Acceptance Criteria:**
  - [ ] Given an adapter discovers ≥1 session paths and **all** yield zero records after `load_records` + `normalize_records` + `filter_records`, when sync completes, then stderr prints a one-line warning naming the adapter (e.g. "cursor: discovered N sources but parsed 0 records — adapter may not implement this store format").
  - [ ] Given at least one session converts successfully, when sync completes, then no such warning is printed for that adapter.
  - [ ] Warning is **not** emitted per file (aggregate per adapter per run only).

### R7 — Documentation and changelog

- **Acceptance Criteria:**
  - [ ] `docs/adapters/cursor.md` updated from Limited/scaffold to working IDE ingest (with caveats: archived threads are included; schema pinned to tested Cursor version; project id aligns with Agent CLI when workspace hash is known).
  - [ ] `CHANGELOG.md` `[Unreleased]` entry and release-note bullet for IDE ingest.
  - [ ] `context/` note under this spec directory documents delivery decisions for AWOS CI gate.

---

## 3. Scope and Boundaries

### In-Scope

- Implement SQLite read-only parsing in `llmwiki/adapters/contrib/cursor.py` for global `cursorDiskKV` (+ workspace DB joins for workspace-hash / slug association when needed).
- Composer-per-session discovery with stable session keys and mtime strategy (R4).
- `normalize_records` mapping IDE bubble types to shared Claude-style schema.
- Align IDE project slug with `cursor_cli`’s `cursor-<12-char-workspace-hash>` when the workspace hash can be resolved (R3 / #126 prep).
- First-class non-file session discovery support on the adapter base (so DB-backed agents can sync without fake files) — Cursor IDE is the first consumer.
- Skip spawned IDE agents under the default skip-automated setting (R5b); markers confirmed against a real Cursor install.
- Tests: probe local Cursor first, then commit synthetic fixtures derived from that schema (no real transcripts).
- Docs + CHANGELOG + context spec artifacts.
- Optional aggregate zero-parse warning in `convert.py` (R6).

### Out-of-Scope

- **`cursor_cli` behavioral changes** beyond shared helpers or documented project-id alignment (R3 / R5).
- **Full #126** (merging clones, worktrees, and cross-agent project pages) — only Cursor IDE ↔ Agent CLI identifier alignment.
- **Enabling `cursor` on bare `llmwiki sync`** ([#182](https://github.com/AlexanderMakarov/llm-wiki/issues/182)).
- **Skipping archived composer threads** — they are in scope and must be ingested (R1).
- **Full HTML fidelity for `richText`** — plain-text extraction is enough for v1; perfect rendering is a follow-up.
- **Migrating or rewriting already-filtered historical sync state** — users re-sync with `--force` if needed.
- **Committing real Cursor session content** — local probe only; fixtures stay synthetic/redacted.

---

## 4. Open Questions (for tech spec)

1. **Non-file session contract:** How convert/watch discover and track DB-row sessions without creating stub files — answered in tech (`SessionRef` / `discover_session_refs`).
2. **Workspace-hash resolution:** Exact join from IDE workspace storage to Agent CLI’s chat hash — confirm on the operator’s install during implementation.
3. **Spawned-agent markers:** Which Composer / bubble fields mean “spawned from parent” — confirm on the operator’s install; do not invent.
4. **Tool result shape:** Exact mapping for IDE `toolResults` — mirror Agent CLI tool-call blocks or flatten to text when schema varies.

---

## 5. Verification (high level)

- Local Cursor probe informs fixtures; `python3 -m pytest tests/ -k cursor -v` green (parser, `SessionRef`, slug alignment, headless when markers known).
- Manual smoke: `python3 -m llmwiki sync --adapter cursor` → converted > 0; archived kept as same session; spawned agents skipped under default skip-automated; project slug matches Agent CLI for a known shared workspace.
- Docs: IDE ingest working; no stale “does not parse” / “always not headless” claims once markers are locked.
