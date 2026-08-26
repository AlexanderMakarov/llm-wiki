# Functional Specification: Offline topic-kind stamp for older source summaries

- **Roadmap Item:** GitHub Issue [#174](https://github.com/AlexanderMakarov/llm-wiki/issues/174) — stamp person/product vs idea labels onto older source connection lines from pages already in the wiki, without calling a language model. Complements the #147 catch-up path; does not replace full re-synthesis when facts are needed.
- **Status:** Approved
- **Author:** Alexander Makarov

---

## 1. Overview and Rationale (The "Why")

Upgrading past the one-pass topic shape marks almost every older source summary as out of date. Today the only way to clear that is a full re-synthesis — one paid model read per source against the raw conversation. On a large vault that can mean thousands of sources and tens of dollars of estimate, even when the summaries themselves are fine and only lack a small kind label next to each named link.

Measured on a real large vault, most of those labels are already known because the same name already has a page among people/products, ideas, or pending review stubs. Stamping those known labels offline clears the “needs rewrite” flag for the large majority of pages without inventing facts and without contacting a provider.

**Desired outcome:** an operator can run a one-time migration (with a dry-run first) that fills missing kind labels from the wiki’s own pages, leaves ambiguous or unknown names alone, prints an honest report (including that no facts were produced), records which pages were stamped for a later forced re-synthesis if desired, and documents the one-way trade-off in the upgrade guide next to the #147 catch-up note.

**Success is measured by:** a vault that needed a mass rewrite can clear most of that backlog with no model calls; remaining pending pages are only those that still lack any usable kind; dry-run changes nothing; ambiguous dual filings are never guessed; upgrade docs state the lock-in and the missing facts.

---

## 2. Functional Requirements (The "What")

### FR1 — Stamp known kinds onto source connection lines without a model

- **As an** operator upgrading a vault whose source summaries predate the topic-kind shape, **I want** a migration command that adds person/product or idea labels to connection lines whose targets already have matching pages in the wiki (including pending review pages), **so that** most of the catch-up bill does not require a paid re-synthesis.

- **Acceptance Criteria:**
  - [ ] Given a vault with source summaries whose connection lines name pages that already exist as people/products, ideas, or pending stubs of those kinds, when the operator runs the topic-kind migration, then those lines gain the matching kind label and no language-model or network provider call is made.
  - [ ] Given pending review pages for a name, when the migration runs, then those pending pages count as a kind source the same way promoted pages do.
  - [ ] Given a name later promoted from pending to a live page, when the operator looks at already-stamped source lines, then they do not need to be stamped again solely because of that promote.

### FR2 — Dry-run and empty vaults are safe

- **As an** operator, **I want** a dry-run that shows the plan without writing, and a clear no-op message when nothing needs stamping, **so that** I can preview impact and scripts stay quiet on already-clean vaults.

- **Acceptance Criteria:**
  - [ ] Given dry-run mode, when the operator runs the migration, then the report describes what would change and the vault files are unchanged.
  - [ ] Given a vault with nothing to stamp, when the operator runs the migration (with or without dry-run), then the command prints a “nothing to migrate” style line and exits successfully.

### FR3 — Never guess when a name is claimed twice

- **As an** operator, **I want** names that appear as both a person/product and an idea to be skipped and listed, **so that** the migration never invents a kind.

- **Acceptance Criteria:**
  - [ ] Given the same name filed under both kinds, when the migration runs, then connection lines for that name are left unchanged and the name is reported as ambiguous/skipped.

### FR4 — Leave already-labeled lines and unrelated sections untouched

- **As an** operator, **I want** lines that already carry a kind, and all non-connection content, left exactly as they are, **so that** the migration is a narrow annotation pass.

- **Acceptance Criteria:**
  - [ ] Given a connection line that already declares a usable kind, when the migration runs, then that line is byte-identical afterward.
  - [ ] Given source pages with key claims, key quotes, and other sections, when the migration runs, then those sections are unchanged; only eligible connection lines may gain a kind label. Descriptions on those lines stay as they were.

### FR5 — Honest report: shape only, no facts

- **As an** operator, **I want** the run summary to state how many pages and lines were stamped, how many lines stayed unresolved, how many pages are still pending rewrite, and that no facts were derived, **so that** I do not believe the #147 catch-up is fully complete.

- **Acceptance Criteria:**
  - [ ] Given a migration that stamps some pages, when it finishes, then the printed report includes pages stamped, bullets/lines stamped, bullets left unresolved, pages still pending rewrite, and a plain statement that no facts were derived.
  - [ ] Given that report, when the operator reads the closing guidance, then it indicates that a forced re-synthesis is still needed on stamped pages if fact lines are desired.

### FR6 — Remember which pages were stamped for later forced re-synthesis

- **As an** operator, **I want** the list of stamped pages recorded in a way a later forced re-synthesis can target exactly those pages, **so that** I can buy facts later without re-processing the whole vault by hand.

- **Acceptance Criteria:**
  - [ ] Given a successful (non-dry-run) migration that stamps pages, when it finishes, then a machine-readable record of those stamped pages is available for a later forced re-synthesis of exactly that set.
  - [ ] Given dry-run, when it finishes, then that record is not written as if the migration had applied.

### FR8 — Plain synth must not re-bill rewrite-clear pages

- **As an** operator who just stamped kinds offline, **I want** a normal `synth` / cost estimate to treat those sources as already done (including when many raw files share one wiki page name), **so that** clearing kinds does not leave a second full-model bill from missing synth state.

- **Acceptance Criteria:**
  - [ ] Given a non-dry-run migration after which a source page no longer needs a topics rewrite, when the operator runs `synth --estimate` or plain `synth`, then raw sessions/docs that resolve to that page are not counted as new solely for missing synth state.
  - [ ] Given many raw files that share one synth filename pointing at a rewrite-clear page, when migration finishes, then each of those raw files is marked done in synth state (not only the page's `source_file` entry).

### FR7 — Upgrade docs explain the trade-off

- **As an** operator reading the upgrade guide next to the #147 catch-up note, **I want** this migration’s cheap-shape / one-way / facts-still-missing trade-off spelled out, **so that** I choose it knowingly.

- **Acceptance Criteria:**
  - [ ] Given the upgrade documentation covering the #147 catch-up, when the operator reads the new migration note, then it explains that stamping is cheaper and offline, that one usable kind clears the rewrite flag permanently unless force is used, and that fact lines are still missing until a forced re-synthesis.

---

## 3. Scope and Boundaries

### In-Scope

- Opt-in offline migration command with dry-run
- Kind sources: live people/products and ideas pages, plus pending review pages of those kinds
- Stamping missing kinds on source connection lines only; skip ambiguous dual filings; leave already-kinded lines alone
- Operator-facing report and stamped-page record for later forced re-synthesis
- Upgrade-guide documentation of the trade-off

### Out-of-Scope

- Producing fact lines, or any language-model call
- Changing the rule that decides whether a source summary still needs rewrite, or changing the #147 page shape itself
- Unattended-spend guards for synthesis (#162) and estimate/run divergence (#163)
- A cheaper model retrofit that rewrites kinds *and* facts from the existing summary page (called out in the issue as a separate future feature)
- Relaxing the rewrite rule so unlabeled lines are acceptable, or guessing kind from name shape
