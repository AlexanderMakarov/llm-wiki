# Technical Specification: Surface prior discard reasons for near-match candidates

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Completed
- **Author(s):** 4ellendger

---

## 1. High-Level Technical Approach

Rewrite **discarded-candidate handling** around one vault file, `wiki/archive/candidates/dismissals.json`, as the source of truth for both pure dismissals and merge intents. List/site near-match marks, vocabulary exclusion, and discarded-topic-links migration all read that file through a **single shared helper module** — no scattered open/parse of sibling `*.reason.txt` in the hot path.

New discards and merges **update the JSON ledger only** (plus moving the stub into the archive as today). A migrate path imports legacy sibling `*.reason.txt` files once so existing vaults converge. Near-match annotation still runs at list/site-payload time (`SequenceMatcher` at `0.90`).

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Architecture Changes

Consolidate the archive decision ledger. Stop treating per-stub `*.reason.txt` as the runtime contract for #282 (or this feature). Keep stub markdown under `wiki/archive/candidates/` as cold storage of the dismissed/merged page body; decision metadata lives in `dismissals.json`.

### `dismissals.json` (name + format — approved)

**Path:** `wiki/archive/candidates/dismissals.json`

**Shape (illustrative — versioned object, not a bare array):**

```json
{
  "version": 1,
  "dismissals": [
    {
      "key": "<norm_page_key>",
      "name": "<display name>",
      "reason": "<free text or empty>",
      "discarded_at": "<UTC ISO>",
      "stub": "<posix path relative to wiki/archive/candidates/>"
    }
  ],
  "merges": [
    {
      "key": "<norm_page_key>",
      "name": "<display name>",
      "into": "<survivor slug>",
      "merged_at": "<UTC ISO>",
      "stub": "<posix path relative to wiki/archive/candidates/>"
    }
  ]
}
```

One file read supplies both dismissal reasons (this feature) and merge targets (`merged_intents` / discarded-topic-links). Merges are co-located for I/O, not treated as dismissals by near-match (FR5).

### Shared helpers (hard requirement)

**All** read/write/rebuild/migrate I/O for `dismissals.json` goes through **one** module (suggested name: `llmwiki/dismissal_ledger.py`). Other packages must not open, parse, or write that path themselves.

Public surface (names illustrative):

| Helper | Used by |
|---|---|
| `load_ledger` / `save_ledger` | internal + migrate |
| `upsert_dismissal` / `upsert_merge` | `discard` / `merge` in `candidates.py` |
| `iter_dismissals` / `iter_merges` | near-match, `discarded_names`, `merged_intents` |
| `rebuild_ledger_from_archive` | migrate + auto-repair when missing |

`candidates_near_match.py`, `candidates.py` (`discarded_names` / `merged_intents` implementations), `migrate_discarded_topic_links.py`, and CLI migrate wiring **call these helpers only**. Near-match logic stays separate from I/O; it receives dismissal records from the ledger API.

### Component Breakdown

| Path | Responsibility |
|---|---|
| **`llmwiki/dismissal_ledger.py` (new)** | **Sole owner of `dismissals.json`.** Load/save (atomic), upsert dismissal/merge, rebuild from legacy `*.reason.txt` + stubs, schema version. |
| `llmwiki/candidates_near_match.py` (new) | Pure near-match + `prior_dismissal` attach; takes dismissal records from ledger helpers (no file I/O). |
| `llmwiki/candidates.py` | `discard` / `merge` archive the stub, then call ledger upserts (**do not** write sibling `*.reason.txt` going forward). Reimplement `discarded_names` / `merged_intents` as thin wrappers over ledger iterators (preserve call sites in `topics.py` / migrate). |
| `llmwiki/migrate_discarded_topic_links.py` | Use ledger `iter_merges` / dismissal keys instead of scanning reason files. |
| Migrate CLI entry | `llmwiki migrate …` to rebuild/import ledger from legacy reason files; `--dry-run`; idempotent. List/build may call rebuild when ledger missing. |
| `llmwiki/cli.py` | List formatting per mockups; register migrate; no direct ledger path strings beyond calling helpers. |
| `llmwiki/candidates_site.py` | Payload + Name-cell secondary line per mockups. |
| `llmwiki/candidates_harvest.py` | Exact exclusion unchanged at call-site level (`archived_candidate_names` / resolved set); ensure it still agrees with ledger-backed dismissals (no near-match at harvest). |
| Docs / CHANGELOG / UPGRADING | Ledger format, migrate, list/UI copy, removal of runtime dependency on sibling reason files. |

### Write path (rewritten)

1. Move stub into archive (existing behavior).
2. Upsert `dismissals[]` or `merges[]` via ledger helpers; atomic JSON replace.
3. **Do not** create new sibling `*.reason.txt` for new discard/merge operations.
4. Legacy `*.reason.txt` files may remain on disk until migrate/rebuild has imported them; they are input to rebuild only, not a second runtime source of truth after a successful ledger exists.

### Read path

- Near-match / list / site: `iter_dismissals` → match → attach `prior_dismissal`.
- `discarded_names` / topic vocabulary: dismissal keys from ledger (still intersect live aliases as today).
- `merged_intents` / discarded-topic-links: `iter_merges` from ledger.

### Data shape (`prior_dismissal` on list/site)

| Field | Semantics |
|---|---|
| `prior_dismissal` | Absent/`null` = ordinary candidate |
| `prior_dismissal.name` | Dismissed display name |
| `prior_dismissal.reason` | Free text; empty → UI **`(discarded without explanation)`** |
| `prior_dismissal.ratio` | Optional; omit from human CLI if noisy |

### UI / CLI presentation (approved)

**CLI:**

```text
[entities ] FooBar  (2d)  — FooBar
    prior dismissal: Foobar — hosting detail, not subject matter
[concepts ] ApiClient  (0d)  — ApiClient
    prior dismissal: API Client — (discarded without explanation)
[entities ] Unrelated  (5d)  — Unrelated
```

**Site Name cell:**

```text
FooBar
  slug · 2d
  Prior dismissal: Foobar — hosting detail, not subject matter
```

### Near-match algorithm

Unchanged from prior draft: `norm_page_key` + `SequenceMatcher` ≥ `0.90`; skip exact key; skip folded length &lt; 4; optional length prefilter; one best match; dismissals only (never merge records).

### Configuration

None. Threshold `0.90`. Ledger path fixed relative to the archive.

---

## 3. Impact and Risk Analysis

### System Dependencies

- Touches every consumer of archive decision metadata: discard, merge, `discarded_names`, `merged_intents`, discarded-topic-links migrate, topics vocabulary, candidates list/site.
- Broader than “annotate near-matches only” — intentional rewrite for performance and one source of truth.

### Potential Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Ledger missing after upgrade | Migrate command + auto-rebuild from legacy reason files on first use. |
| Dual truth if something still writes reason.txt | Remove write path; tests assert no new `*.reason.txt` after discard/merge. |
| Modules bypassing helpers | Code review + tests import path; document “ledger I/O only via `dismissal_ledger`”. |
| False-positive near-matches | Length floor; 0.90 threshold; best-match only. |
| Corrupt JSON | Fail loud on read; rebuild from archive when migrate/`--force` appropriate; atomic writes. |
| Empty reason | Mark + `(discarded without explanation)`. |

---

## 4. Testing Strategy

| File | Focus |
|---|---|
| `tests/test_dismissal_ledger.py` (new) | Upsert dismissal/merge; atomic save; rebuild from fixture reason files; idempotent migrate; no sibling reason written on new discard. |
| `tests/test_candidates_near_match.py` (new) | Match rules; merges excluded; empty → display string; ledger-fed records. |
| `tests/test_candidates.py` | `list_candidates` + `discarded_names` / `merged_intents` via ledger; discard/merge rewrite. |
| `tests/test_migrate_discarded_topic_links.py` | Still correct when intents come from ledger. |
| `tests/test_candidates_harvest.py` / topics | Exact settled exclusion (FR4). |
| CLI + `tests/test_candidates_site.py` | Mockup strings including `(discarded without explanation)`. |
