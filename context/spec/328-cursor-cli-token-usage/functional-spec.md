# Functional Specification: Session token usage store + Cursor CLI capture

- **Roadmap Item:** [GitHub #325](https://github.com/AlexanderMakarov/llm-wiki/issues/325) — feat(cursor_cli): investigate and capture native token usage (persistence shaped for [#322](https://github.com/AlexanderMakarov/llm-wiki/issues/322))
- **Status:** Approved
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

People who use several coding agents want one **Tokens** figure that answers “how much session usage did my wiki capture?” That figure uses four usage categories — input, cache creation, cache read, and output — and treats cache as real consumption. It is a **usage** total, not a billing or plan-percentage dashboard, and not “how full was the context window.”

Aggregating those numbers by walking every raw session file (or one metrics file per session) does not scale: hot paths must care about **how many files** an operation opens, not only CPU. MCP already keeps a small usage tree; session Tokens should use **one** vault usage file that holds lifetime totals, per-day × per-agent buckets (ready for #322 / Analytics), and enough slim per-session stubs for correct re-upserts — not three files that can drift or deadlock.

Sessions can span midnight and can be resumed days later. This ticket uses a deliberate simplification: each session’s full four-bucket total is attributed to the **UTC calendar day of that session’s last activity**. When the session is updated later, counters are recomputed and re-attributed (move the whole contribution if the last-activity day changed). Per-turn time series are out of scope.

Synced sessions still expose Tokens on the static **session** page via raw frontmatter. Filtered or don’t-sync sessions can still contribute to the usage file and coverage hover when discoverable, without a wiki transcript page.

Success means: one usage file + frontmatter on synced pages; **named migrate** for one-time historical backfill (sync alone cannot reliably detect “never had token_totals” when origin fingerprints are unchanged); sync maintains new/changed sessions thereafter; last-activity day attribution with resume-safe re-upsert; Cursor CLI in the shared pipeline; docs and I/O rules; occupancy never feeds Tokens.

---

## 2. Functional Requirements (The "What")

- **One usage file is the Analytics / aggregate source of truth; synced session pages still use frontmatter for per-page Tokens.**
  - Persist under `<vault>/usage/session-tokens.json` (single file): lifetime totals, `by_agent` coverage (measured/known), and `days[YYYY-MM-DD][agent]` four-bucket totals. Day × agent growth is bounded (~3660 days × agent types over a decade) — small.
  - Keep slim per-session stubs in the **same** file only as needed for idempotent upsert and last-activity re-attribution (not a second file; not one file per session on disk).
  - Hot paths open a **bounded** number of Tokens-related files (that usage file + optional site sidecar), not one open per session.
  - Sync updates the usage file and refreshes a site data sidecar so Analytics can change without a full HTML rebuild.
  - Build reads the usage file for Analytics Tokens; it must not walk every raw session solely for that number.
  - When convert writes or updates a raw session page, write/update `token_totals` (four buckets) in that page’s frontmatter so the static session page can show Tokens.
  - Metrics-only sessions (no raw page) update the usage file only — no frontmatter.
  - **Acceptance Criteria:**
    - [ ] Given thousands of sessions, when sync/build refreshes Tokens aggregates, then Tokens file opens stay O(1) / small bound (not one metrics path per session).
    - [ ] Given a synced session with measured usage, when the user opens its static session page, then Tokens come from that page’s frontmatter.
    - [ ] Given new measurable usage on sync, when Analytics is opened on an existing site, then Tokens update without a full rebuild (sidecar).
    - [ ] Given the usage file’s `days` + `by_agent`, when #322 adds week/month UI later, then it can consume those buckets without a second persistence redesign.

- **Historical backfill is a named migrate; steady-state sync only touches new/changed sessions (fingerprint skip).**
  - **Why not sync-only backfill:** convert/sync skip state (`llmwiki-state.json` / origin mtime fingerprints) means “already synced, unchanged.” After upgrade, those sessions still match fingerprints even when raw frontmatter **lacks** `token_totals` and the usage file has no stub. A second sync would no-op and never backfill. Inferring “needs tokens” would require either reading every raw frontmatter (defeats skip) or a separate schema flag — a one-shot migrate is the reliable operator path (same pattern as other vault repairs).
  - **`llmwiki migrate <session-tokens-or-final-name>` (required after upgrade for existing vaults that want historical Tokens):** walk discoverable capable sessions (and/or existing raw pages), compute usage from origin when needed, write/patch raw `token_totals` where a raw page exists, upsert `usage/session-tokens.json`. Idempotent; `--dry-run`; documented in UPGRADING as the historical backfill step.
  - **Regular `sync` thereafter:** for new sessions or fingerprint-**changed** sessions (resume), compute usage → upsert usage file → write frontmatter when raw is written/updated. Unchanged fingerprint → skip (no full body re-parse, no usage rewrite for that session). If all skips, do not rewrite the usage file solely for Tokens.
  - Sync does **not** claim to backfill “old but fingerprint-unchanged” sessions; that is migrate’s job.
  - **Acceptance Criteria:**
    - [ ] Given a vault with pre-upgrade synced Cursor (or other) sessions whose origin fingerprints are unchanged and frontmatter lacks `token_totals`, when the user runs only sync, then those sessions are not required to gain Tokens; when they run the named migrate, then usage + frontmatter (where raw exists) are filled.
    - [ ] Given migrate has run (or a fresh vault), when sync sees only unchanged fingerprints, then Tokens path skips full body re-parse and does not rewrite the usage file for no-ops.
    - [ ] Given UPGRADING docs, when the user upgrades, then the named migrate is listed as the historical Tokens backfill step.

- **Attribute each session’s full total to the UTC day of last activity; re-upsert on resume/update.**
  - Day rule: `UTC date of last activity` for that session (documented in UI/docs as approximate session-day attribution).
  - Do not store per-turn token series in this ticket.
  - When a session is updated after further work (e.g. restored and continued days later), recompute totals and re-upsert: if the last-activity day changed, remove the session’s previous contribution from the old day and apply the new totals to the new day (and refresh lifetime/`by_agent` consistently).
  - **Acceptance Criteria:**
    - [ ] Given a multi-day session, when stored, then its full four-bucket total is attributed to exactly one UTC day — the last-activity day.
    - [ ] Given the same session gains new activity on a later UTC day, when sync runs, then day buckets and frontmatter (if synced) reflect the new totals and the new last-activity day attribution.
    - [ ] Docs/UI label period totals as last-activity session-day attribution (approximate).

- **Metrics for filtered / not-synced sessions.**
  - Discoverable sessions with computable usage may update the usage file and coverage even when raw is not written.
  - They count in measured/known hover and in totals when measured; they do not require a session list page.
  - **Acceptance Criteria:**
    - [ ] Given a filtered/don’t-sync session with measurable usage, when sync/metrics runs, then usage + coverage include it; wiki session list need not show a transcript page.

- **Capture Cursor CLI into the shared usage pipeline.**
  - Map verified per-turn usage into the four categories without double-counting; never use context-window occupancy as Tokens.
  - **Acceptance Criteria:**
    - [ ] Given real usage categories, when metrics are recorded, then four-bucket totals update usage (and frontmatter when raw is written).
    - [ ] Given only occupancy, when metrics run, then no fabricated Tokens usage is written.

- **User-facing docs: Tokens for all agents; usage vs billing; last-activity day rule; metrics-without-raw; migrate for history.**
  - **Acceptance Criteria:**
    - [ ] Docs cover four categories, cache counts, usage≠billing, last-activity attribution, metrics-only sessions, and that historical Tokens use the named migrate (sync only maintains new/changed).

- **On-hover coverage on the Analytics Tokens card.**
  - Form like `- measured/known Agent` (plus optional `(since YYYY/MM/DD)`); only agents with ≥1 measured session; include metrics-only in counts. Per-session / per-project Tokens cards stay frontmatter-only (no coverage hint).
  - **Acceptance Criteria:**
    - [ ] Analytics coverage control shows measured/known only for agents with ≥1 measured session.

- **Contributor/maintainer I/O scalability rules.**
  - Operations must care about **number of files** read/written; prefer one aggregate usage file over per-session files or raw walks on hot paths.
  - **Acceptance Criteria:**
    - [ ] CONTRIBUTING and/or maintainer docs state this with session Tokens / `usage/session-tokens.json` as the example.

---

## 3. Scope and Boundaries

### In-Scope

- Single `usage/session-tokens.json` + site sidecar; frontmatter `token_totals` on synced session pages.
- Named migrate for historical Tokens backfill (UPGRADING); sync maintains new/fingerprint-changed only.
- Last-activity UTC day attribution; resume-safe re-upsert.
- Metrics-without-raw; Cursor CLI capture; coverage hover; docs; CHANGELOG/UPGRADING; I/O rules.
- Store shaped for #322 (not the #322 UI itself).

### Out-of-Scope

- Full #322 expandable per-agent / week / month UI.
- Per-step / per-turn token time series as a required store.
- #321 Home redesign; billing/plan dashboards; occupancy-as-Tokens.
- Changing MCP compact semantics except where session Tokens parallel the “small usage files” idea.
