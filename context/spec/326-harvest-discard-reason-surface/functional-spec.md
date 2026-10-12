# Functional Specification: Surface prior discard reasons for near-match candidates

- **Roadmap Item:** Harvest respects a dismissal (#146) — remaining scope after #282
- **Status:** Approved
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

When a reviewer discards a candidate, they record why. Exact re-proposals of that same subject already stay out of the queue. What still fails: a *similar* name can appear as a brand-new candidate with no hint that a related dismissal already happened — so the reviewer either re-litigates the same decision or promotes something they meant to keep out.

This change keeps near-match names in the review queue (so a deliberate change of mind stays possible) but makes the prior dismissal and its recorded reason visible at review time on both the command-line list and the candidates review page.

**Success:** A reviewer who discarded something once does not have to rediscover that decision when a close spelling shows up again; they see the old reason and can keep, promote, merge, or discard with eyes open.

---

## 2. Functional Requirements (The "What")

### FR1 — Near-match candidates stay in the queue and are marked

When harvest proposes a new candidate whose name is an obvious variant of a previously *dismissed* subject (differing mainly by spelling, spacing, or punctuation — not the same folded name already excluded today), that candidate still appears in the review queue. It must be clearly marked as related to a prior dismissal.

- **Acceptance Criteria:**
  - [ ] Given a subject was dismissed earlier, when harvest proposes a close spelling variant that is not the same settled name, then that variant appears in the pending candidates list (it is not silently omitted).
  - [ ] Given that near-match candidate is pending, when the reviewer opens the candidates list (CLI) or the candidates review page, then the row is visibly marked as related to a prior dismissal (not indistinguishable from an ordinary new candidate).

### FR2 — The recorded dismissal reason is shown to the reviewer

For a marked near-match, the free-text reason from the earlier dismissal is shown alongside the mark, on both review surfaces the product already uses for candidates.

- **Acceptance Criteria:**
  - [ ] Given a dismissal was recorded with a reason (for example, “hosting detail, not subject matter”), when a near-match candidate appears in `candidates list` output, then that reason text is visible on or next to that candidate’s entry.
  - [ ] Given the same situation, when the reviewer opens the candidates review page in the site, then that reason text is visible on or next to that candidate’s row without opening the archive by hand.
  - [ ] Given the prior dismissal had no usable free-text reason, when a near-match appears, then the mark that a prior dismissal existed still appears, and the reason area shows `(discarded without explanation)` rather than inventing a rationale.

### FR3 — Matching uses the dismissed name, not the reason text

Which pending names get the mark is decided only by closeness of the *name* to a previously dismissed subject. The reason text is for display only; it does not pull unrelated candidates into the “prior dismissal” mark just because their summaries sound similar.

- **Acceptance Criteria:**
  - [ ] Given two unrelated pending names that do not resemble any dismissed name, when their descriptions happen to sound like an old discard reason, then neither is marked as related to that dismissal.
  - [ ] Given a pending name that is an obvious spelling/spacing/punctuation variant of a dismissed name, when the reviewer reviews the queue, then it is marked and shows that dismissal’s reason even if the new stub’s body is unrelated.

### FR4 — Exact settled dismissals remain excluded (no regression)

Subjects already treated as settled dismissals (same name under the product’s existing name folding) continue not to re-enter the queue. This feature does not reopen that path.

- **Acceptance Criteria:**
  - [ ] Given a name was dismissed and would already be excluded as the same subject, when harvest runs again with no stronger or different spelling, then that exact subject still does not appear as a new pending candidate.

### FR5 — Merges are not treated as dismissals for this mark

A candidate that was *merged* into another page is not a dismissal. Near-match marking and reason display for this feature apply only to subjects the reviewer discarded (rejected), not to merges.

- **Acceptance Criteria:**
  - [ ] Given a name was merged into another page (not discarded), when a close spelling variant is later proposed, then it is not marked with a “prior dismissal” reason from that merge.

### FR6 — Prior dismissals remain available after upgrade, and review stays fast

A vault that already has dismissed candidates from before this change still shows near-match marks and reasons after upgrade, without the reviewer re-discarding those subjects. Going forward, listing and related “what was dismissed / merged” checks use one consolidated record of those decisions — not a separate file per old dismissal on every review.

- **Acceptance Criteria:**
  - [ ] Given a vault with older dismissals and recorded reasons, when the reviewer upgrades and opens the candidates list or review page without re-discarding, then near-match marks and reasons still appear for those older dismissals.
  - [ ] Given many prior dismissals, when the reviewer lists candidates or rebuilds the review page, then the experience remains a normal list/build (no multi-second stall attributable to opening one file per historical dismissal).
  - [ ] Given the reviewer discards or merges a candidate after upgrade, when they later list candidates or run the existing discarded-topic cleanup migrate, then those tools still see the new decision without relying on a new per-candidate reason sidecar file.

---

## 3. Scope and Boundaries

### In-Scope

- Marking pending candidates that are name-near-matches of previously dismissed subjects
- Showing the recorded free-text dismissal reason on `candidates list` and the candidates review page, with empty reasons shown as `(discarded without explanation)`
- Keeping those near-matches in the queue so the reviewer can change their mind deliberately
- Preserving existing exact-name exclusion for settled dismissals
- Rewriting discarded-candidate decision storage onto one consolidated archive file (`dismissals.json`), including migration from older per-dismissal reason files and updating the tools that previously read those files (topic exclusion, discarded-topic-links migrate, merge-target lookup)

### Out-of-Scope

- Using discard-reason wording to auto-suppress or auto-flag unrelated candidates (semantic / rationale matching)
- Silently skipping near-matches without offering them for review
- An automatic “reopen when evidence is much stronger” threshold (may be a later issue)
- Changing how discard writes or requires the reason at discard time (#109 and related) — only where that reason is stored after the decision
- Batch apply order (#149) and other open roadmap items
- Analytics or tuning advice derived from aggregating discard reasons (e.g. judging the minimum-references threshold)
- Deleting historical sibling reason files from disk automatically (import into the ledger is enough; optional cleanup can be a later chore)
