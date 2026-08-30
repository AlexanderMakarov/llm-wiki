# Functional Specification: Durable sync lookback per session source

- **Roadmap Item:** GitHub [#192](https://github.com/AlexanderMakarov/llm-wiki/issues/192) — durable sync lookback so bare sync does not ingest years of history
- **Status:** Completed
- **Author:** Aleksandr Makarov

---

## 1. Overview and Rationale (The "Why")

Some coding agents keep years of chat history. A plain sync can pull that entire backlog into the wiki. The date cut-off already exists as a temporary command option, but bare sync ignores it, and operators often learn about the problem only after a huge first import.

Operators need durable shared and per-source lookbacks, early pruning so excluded history is not loaded, clear per-source sync numbers, lookback-tied cleanup of sync memory in the vault state file, and a first-run configure interview that **suggests** a sensible window (today minus 30 days), shows how many sessions that implies, and teaches how to change it later — without forcing a lookback when someone syncs without configuring.

After lookback ships, **configure-sources is the only adapter-side gate for bare sync**: Enable in the quiz means the source runs on the next bare `llmwiki sync`. There is no second “active / ingest_ready” surprise. One-off sources use `sync --adapter <name>`.

**Success:** Unconfigured sync still means full history; configured lookbacks are respected on every bare sync; setup makes a 30-day suggestion easy and informed; sync hints how to change dates; state sync memory is pruned to the active lookback; Cursor IDE and other ready sources that the operator Enabled in configure-sources are included on bare sync; the adapters roster shows **enabled yes/no** (not a separate active column).

---

## 2. Functional Requirements (The "What")

### R1 — Shared lookback in settings (optional; default unlimited)

- **As an** operator, **I want** an optional shared “earliest session date” in wiki settings, **so that** every bare sync skips older chats once I’ve chosen a floor.

- **Acceptance Criteria:**
  - [x] Given no shared lookback (missing or empty) and no one-run date, when I run sync, then there is **no** date gate — full history for each source (unless that source has its own lookback).
  - [x] Given a shared lookback of a valid calendar day (YYYY-MM-DD), when I run a bare sync, then sessions whose last activity is before that day are not collected (for sources that inherit the shared date).
  - [x] Given an invalid shared lookback string, when I start sync, then the command exits with failure status 2 and an error consistent with a bad one-run date option.

### R2 — Per-source lookback override

- **As an** operator with mixed sources, **I want** each session source to optionally override the shared lookback, **so that** small stores can keep full history while long stores stay bounded.

- **Acceptance Criteria:**
  - [x] Given a shared lookback and no per-source override, when I sync, then that source uses the shared date.
  - [x] Given a per-source lookback set to a valid day, when I sync, then that source uses the per-source date instead of the shared one.
  - [x] Given a per-source lookback explicitly empty / “no override,” when I sync, then that source inherits the shared lookback if any; if shared is also unset, that source has no date gate.
  - [x] Given only a per-source lookback (no shared), when I sync, then only that source is date-gated.
  - [x] Default for every source: no per-source lookback set.

### R3 — One-run date option overrides settings

- **As an** operator, **I want** the existing one-run sync date option to override both shared and per-source lookbacks for that run.

- **Acceptance Criteria:**
  - [x] Given settings lookbacks and a one-run date, when I sync with that option, then every source in the run uses the one-run date.
  - [x] Given an invalid one-run date, when I sync, then exit status 2 with the same style of error as today.

### R4 — Early prune, then exact check (hybrid)

- **As an** operator of a long-retention store, **I want** sync to avoid loading excluded history when a lookback applies.

- **Acceptance Criteria:**
  - [x] File-based sources: files with modification time before the effective lookback are not candidates.
  - [x] Database-backed sources with last-activity fields (e.g. Cursor IDE Composer): lookback applied in store query / header load so excluded threads are not candidates.
  - [x] Candidates that still load still get the post-load last-activity date check (same meaning as today’s one-run date option).
  - [x] Lookback-only skips are **not** written into `llmwiki-state.json` sync memory (`sync.files`), so widening lookback later can reconsider them on a normal sync.

### R5 — Per-source sync report + hint to change lookback

- **As an** operator reading sync output, **I want** two numbers per source (after early filter → synced) and a short hint on how to change the start date, **so that** I am not surprised and I know where to tune the window.

- **Acceptance Criteria:**
  - [x] Per source: **(1)** sessions after early lookback/mtime filter (“what we have”), **(2)** how many were synced this run — no full-store total required or printed.
  - [x] Sync output includes a concise hint on how to set or change the shared and/or per-source start date (settings and/or re-run configure), including when no lookback is configured (so a large unlimited run is explainable).
  - [x] Overall run summary stays understandable without advertising a pre-filter corpus size.

### R6 — Lookback garbage collection for sync memory

- **As an** operator with a large vault state file, **I want** `sync.files` entries outside the active lookback pruned when a lookback applies.

- **Acceptance Criteria:**
  - [x] After a successful sync with an effective lookback for a source, remove that source’s `sync.files` entries whose recorded time is before that lookback.
  - [x] Sources with no effective lookback are not GC’d by this feature.
  - [x] GC does not delete queue, synth map, quarantine, or ops as part of this feature.
  - [x] Later syncs still convert new/changed sessions inside the lookback correctly.
  - [x] Docs note lookback GC and that lookback-only skips are never added to the map.

### R7 — Configure / setup quiz: suggest today−30, show counts

- **As a** new (or re-configuring) operator, **I want** the source-configuration interview to start with a shared start date (default today minus 30 days), then for each source show session count and earliest session time before asking enable / path / start date, **so that** I can estimate sync and synthesis cost before the first big run — without forcing a lookback if I never run configure.

- **Acceptance Criteria:**
  - [x] Interactive configure asks for a **shared** earliest-session date first. Enter accepts **today − 30 days** (or keeps a date already stored). Typing `YYYY-MM-DD` sets a custom shared date.
  - [x] Each session source is then interviewed in turn: a facts block (path found or not, **session count**, **earliest session time**, in last 30 days) → Enable (`[Y/n]` when a default path exists, `[y/N]` when not) → path (suggested only if found) → start date (Enter = use shared, or `YYYY-MM-DD`).
  - [x] Facts are shown **before** Enable so the operator can see how large the store is.
  - [x] Per-source Enter on start date inherits the shared date (no per-source override key).
  - [x] Chosen dates are written to local settings; non-interactive / skipped interview invents no dates.
  - [x] Re-running the interview can update dates; Enter on shared keeps the stored date when one exists.

### R8 — Documentation and upgrade note

- **Acceptance Criteria:**
  - [x] Configuration reference and example settings show shared + per-source lookback, inheritance, and “unset = unlimited.”
  - [x] CHANGELOG `[Unreleased]` + short UPGRADING note: set lookback before enabling long stores; configure suggests 30 days; next sync with a lookback prunes sync memory outside the window.
  - [x] Docs state lookback-skipped sessions are not remembered as done.

### R9 — Configure Enable = bare sync; adapters table is enabled yes/no

- **As an** operator, **I want** Enable in `configure-sources` to be sufficient for bare `llmwiki sync` for every ready session source (including Cursor IDE), **so that** I never need a second hidden gate or a separate “active” column.

- **Acceptance Criteria:**
  - [x] Given Cursor IDE’s store is present and configure-sources wrote `adapters.cursor_ide.enabled: true` (with a lookback set), when I run bare `llmwiki sync`, then the `cursor_ide` adapter runs (no `--adapter` required).
  - [x] `cursor_ide.ingest_ready` is `True` so selection no longer skips IDE on bare sync.
  - [x] The `llmwiki adapters` / post-configure roster columns are **name · present · enabled · description** only — **enabled** is **yes** or **no** (whether the next bare sync includes that source). There is **no** `active` column and no `auto` / `explicit` / `off` labels in that table.
  - [x] Quiz Enable for a present, ready store defaults to yes (`[Y/n]`); unfinished adapters (`ingest_ready=False`) still default to no with a short note.
  - [x] One-off / forced runs still use `llmwiki sync --adapter <name>` (bypasses the enabled roster).

---

## 3. Scope and Boundaries

### In-Scope

- Optional shared + per-source lookback (absolute YYYY-MM-DD); unset = unlimited.
- Configure quiz suggests today−30; shows per-source session counts for the chosen/suggested window.
- Sync: hybrid early prune; per-source after-filter + synced; hint how to change start dates.
- No lookback-only writes to `sync.files`; lookback-tied GC of `sync.files`.
- Cursor IDE `ingest_ready=True`; configure Enable ⇒ bare sync; adapters table **enabled yes/no** only (no active column).
- Docs, examples, CHANGELOG, UPGRADING, tests covering the above.

### Out-of-Scope

- Relative forms as stored config (`90d`) — quiz may *compute* a suggested absolute day from “today − 30.”
- Deleting already-synced raw sessions; vault TTL; product retention changes.
- Broader state diet (queue capping, synth map redesign, legacy `.llmwiki-state.json` removal) beyond lookback GC of `sync.files`.
- Unrelated filter redesign (headless / temp cwd / subagents) beyond lookback interaction.
- Requiring configure-sources before *any* AI adapter runs (Claude Code and similar stay auto when the store is present and not explicitly off).
