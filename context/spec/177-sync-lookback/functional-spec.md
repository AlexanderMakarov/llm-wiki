# Functional Specification: Durable sync lookback per session source

- **Roadmap Item:** GitHub [#192](https://github.com/AlexanderMakarov/llm-wiki/issues/192) — durable sync lookback so bare sync does not ingest years of history
- **Status:** Approved
- **Author:** Aleksandr Makarov

---

## 1. Overview and Rationale (The "Why")

Some coding agents keep years of chat history. A plain sync can pull that entire backlog into the wiki. The date cut-off already exists as a temporary command option, but bare sync ignores it, and operators often learn about the problem only after a huge first import.

Operators need durable shared and per-source lookbacks, early pruning so excluded history is not loaded, clear per-source sync numbers, lookback-tied cleanup of sync memory in the vault state file, and a first-run configure interview that **suggests** a sensible window (today minus 30 days), shows how many sessions that implies, and teaches how to change it later — without forcing a lookback when someone syncs without configuring.

**Success:** Unconfigured sync still means full history; configured lookbacks are respected on every bare sync; setup makes a 30-day suggestion easy and informed; sync hints how to change dates; state sync memory is pruned to the active lookback.

---

## 2. Functional Requirements (The "What")

### R1 — Shared lookback in settings (optional; default unlimited)

- **As an** operator, **I want** an optional shared “earliest session date” in wiki settings, **so that** every bare sync skips older chats once I’ve chosen a floor.

- **Acceptance Criteria:**
  - [ ] Given no shared lookback (missing or empty) and no one-run date, when I run sync, then there is **no** date gate — full history for each source (unless that source has its own lookback).
  - [ ] Given a shared lookback of a valid calendar day (YYYY-MM-DD), when I run a bare sync, then sessions whose last activity is before that day are not collected (for sources that inherit the shared date).
  - [ ] Given an invalid shared lookback string, when I start sync, then the command exits with failure status 2 and an error consistent with a bad one-run date option.

### R2 — Per-source lookback override

- **As an** operator with mixed sources, **I want** each session source to optionally override the shared lookback, **so that** small stores can keep full history while long stores stay bounded.

- **Acceptance Criteria:**
  - [ ] Given a shared lookback and no per-source override, when I sync, then that source uses the shared date.
  - [ ] Given a per-source lookback set to a valid day, when I sync, then that source uses the per-source date instead of the shared one.
  - [ ] Given a per-source lookback explicitly empty / “no override,” when I sync, then that source inherits the shared lookback if any; if shared is also unset, that source has no date gate.
  - [ ] Given only a per-source lookback (no shared), when I sync, then only that source is date-gated.
  - [ ] Default for every source: no per-source lookback set.

### R3 — One-run date option overrides settings

- **As an** operator, **I want** the existing one-run sync date option to override both shared and per-source lookbacks for that run.

- **Acceptance Criteria:**
  - [ ] Given settings lookbacks and a one-run date, when I sync with that option, then every source in the run uses the one-run date.
  - [ ] Given an invalid one-run date, when I sync, then exit status 2 with the same style of error as today.

### R4 — Early prune, then exact check (hybrid)

- **As an** operator of a long-retention store, **I want** sync to avoid loading excluded history when a lookback applies.

- **Acceptance Criteria:**
  - [ ] File-based sources: files with modification time before the effective lookback are not candidates.
  - [ ] Database-backed sources with last-activity fields (e.g. Cursor IDE Composer): lookback applied in store query / header load so excluded threads are not candidates.
  - [ ] Candidates that still load still get the post-load last-activity date check (same meaning as today’s one-run date option).
  - [ ] Lookback-only skips are **not** written into `llmwiki-state.json` sync memory (`sync.files`), so widening lookback later can reconsider them on a normal sync.

### R5 — Per-source sync report + hint to change lookback

- **As an** operator reading sync output, **I want** two numbers per source (after early filter → synced) and a short hint on how to change the start date, **so that** I am not surprised and I know where to tune the window.

- **Acceptance Criteria:**
  - [ ] Per source: **(1)** sessions after early lookback/mtime filter (“what we have”), **(2)** how many were synced this run — no full-store total required or printed.
  - [ ] Sync output includes a concise hint on how to set or change the shared and/or per-source start date (settings and/or re-run configure), including when no lookback is configured (so a large unlimited run is explainable).
  - [ ] Overall run summary stays understandable without advertising a pre-filter corpus size.

### R6 — Lookback garbage collection for sync memory

- **As an** operator with a large vault state file, **I want** `sync.files` entries outside the active lookback pruned when a lookback applies.

- **Acceptance Criteria:**
  - [ ] After a successful sync with an effective lookback for a source, remove that source’s `sync.files` entries whose recorded time is before that lookback.
  - [ ] Sources with no effective lookback are not GC’d by this feature.
  - [ ] GC does not delete queue, synth map, quarantine, or ops as part of this feature.
  - [ ] Later syncs still convert new/changed sessions inside the lookback correctly.
  - [ ] Docs note lookback GC and that lookback-only skips are never added to the map.

### R7 — Configure / setup quiz: suggest today−30, show counts

- **As a** new (or re-configuring) operator, **I want** the source-configuration interview to suggest today minus 30 days, show how many sessions that implies per source, and let me choose dates, **so that** I can estimate sync size and later synthesis (LLM) cost before the first big run — without forcing a lookback if I never configure.

- **Acceptance Criteria:**
  - [ ] Interactive configure (offered from setup) asks for an optional shared earliest-session date, with **today − 30 days** offered as the suggested default answer (user can accept, pick another calendar day, or leave unset for unlimited).
  - [ ] For each session source I enable, ask for an optional per-source date (default: none / inherit shared), again with a clear way to leave unset.
  - [ ] While choosing dates, show **current candidate counts** for that source under the suggested/chosen lookback (and, when useful, under unlimited), so I can estimate how much would sync and later need synthesis — without requiring a full convert.
  - [ ] Blank / skip leaves that scope unset (unlimited for that scope, subject to inheritance rules in R2).
  - [ ] Chosen dates are written to local settings like other source settings; non-interactive / skipped interview invents no dates.
  - [ ] Re-running the interview can update dates and refresh the count hints.

### R8 — Documentation and upgrade note

- **Acceptance Criteria:**
  - [ ] Configuration reference and example settings show shared + per-source lookback, inheritance, and “unset = unlimited.”
  - [ ] CHANGELOG `[Unreleased]` + short UPGRADING note: set lookback before enabling long stores; configure suggests 30 days; next sync with a lookback prunes sync memory outside the window.
  - [ ] Docs state lookback-skipped sessions are not remembered as done.

---

## 3. Scope and Boundaries

### In-Scope

- Optional shared + per-source lookback (absolute YYYY-MM-DD); unset = unlimited.
- Configure quiz suggests today−30; shows per-source session counts for the chosen/suggested window.
- Sync: hybrid early prune; per-source after-filter + synced; hint how to change start dates.
- No lookback-only writes to `sync.files`; lookback-tied GC of `sync.files`.
- Docs, examples, CHANGELOG, UPGRADING, tests covering the above.

### Out-of-Scope

- Relative forms as stored config (`90d`) — quiz may *compute* a suggested absolute day from “today − 30.”
- Deleting already-synced raw sessions; vault TTL; product retention changes.
- Broader state diet (queue capping, synth map redesign, legacy `.llmwiki-state.json` removal) beyond lookback GC of `sync.files`.
- Unrelated filter redesign (headless / temp cwd / subagents) beyond lookback interaction.
