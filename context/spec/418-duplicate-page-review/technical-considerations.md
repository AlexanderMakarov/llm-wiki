# Technical Specification: Review possible duplicate curated pages in one batch

- **Functional Specification:** `context/spec/418-duplicate-page-review/functional-spec.md`
- **Status:** Approved
- **Author(s):** 4ellendger

---

## 1. High-Level Technical Approach

Extend the existing candidates review pipeline with a **read-only duplicate-pair detector** over vocabulary + live curated pages, a **Candidates HTML/CLI section**, and two **new batch actions** for live-page merge and durable keep-distinct. Harden the **existing** known-names consolidation call (prompt constraints + deterministic post-process) so curated titles stay fixed. **No new LLM call; no new runtime dependencies.**

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Architecture / modules

| Concern | Location |
|---|---|
| Pair detection + shared fold helpers | `llmwiki/topics.py` (or thin `llmwiki/topics_duplicates.py` if topics grows too large) — extract internals from `_keep_curated_names_on_their_pages`; add `detect_duplicate_pairs` |
| Live page merge | New `merge_pages` in `llmwiki/candidates.py` or `llmwiki/page_merge.py` — do **not** reuse stub `merge()` |
| Keep-distinct SoT | `llmwiki/dismissal_ledger.py` — `keep_distinct[]` on `dismissals.json` |
| Batch UI/CLI | `llmwiki/candidates_site.py`, `llmwiki/cli.py` `cmd_candidates` |
| Consolidation constraints | `llmwiki/topics_consolidate.py` + `llmwiki/synth/prompts/topic_consolidation.md` |
| Doctor / lint / agent kit | `doctor/checks.py`, `doctor/heal_kb.json`, new lint rule module, `llmwiki/agent_kit/commands/wiki-candidates.md` |

Detection kinds = entities + concepts + **projects** (per issue). Graph’s narrower `CURATED_KIND_FOLDERS` (entities/concepts) stays unchanged unless product later asks otherwise.

### Data model — ledger `keep_distinct`

Durable record in `wiki/archive/candidates/dismissals.json` (same file as dismissals/merges; ledger version stays 1; coerce learns the new array):

| Field | Purpose |
|---|---|
| `key` | Stable unordered pair id (`norm_page_key(a)|norm_page_key(b)` sorted) |
| `a`, `b` | Display names |
| `decided_at` | ISO UTC |
| `why` | Optional |

Helpers: `upsert_keep_distinct`, `iter_keep_distinct`, `is_keep_distinct_pair`. Archive rebuild does **not** invent these rows.

Ledger is SoT (survives every topics-cache rewrite). Cache `distinct_from` may mirror; ledger wins. Not cache-only or page frontmatter.

### Batch action contracts (stubs unbroken)

Existing stub actions unchanged: `promote` | `flip-promote` | `discard` | `merge` (+ `slug`, etc.).

New:

```json
{"action":"merge-pages","from":"<loser title or slug>","into":"<survivor title or slug>"}
{"action":"keep-distinct","a":"<name>","b":"<name>"}
```

- Validators branch on `action` first; new actions must not require stub `slug`.
- Conflict rules: cannot keep-distinct and merge-pages the same pair in one batch; cannot chain conflicting losers/survivors.
- Apply: `merge-pages` → `merge_pages(...)`; `keep-distinct` → ledger upsert only.

### `merge_pages` behaviour

Resolve both live pages across kinds; survivor path/kind unchanged; union `sources:` and `## Connections`; append loser prose under a dated section; record loser name under `## Aliases`; rewrite inbound `[[wikilinks]]` (reuse existing rewrite helpers); archive loser; `upsert_merge`; reconcile index. No LLM. Cross-kind allowed; survivor keeps kind/folder.

### Consolidation — same single call

1. **Prompt:** inject `<fixed_curated_titles>` and `<keep_distinct>` from disk/ledger.
2. **Post-process:** after `parse_and_cache` / on `load_cache`, detach any alias_map fold that maps one curated title onto another curated title or a keep-distinct partner.
3. Keep `_keep_curated_names_on_their_pages` as derive-time belt-and-suspenders when prepare skips on fingerprint match.

Fingerprint skip still skips the LLM; constraints still apply via post-process/load + derive keep — **never a second call**.

### Surfaces

- `candidates_payload` / `render_candidates_body`: “Possible duplicate pages” with titles, kinds, links, session counts, cache description, decision controls → same Apply command.
- `llmwiki candidates list`: print pairs (and JSON if list already supports it).
- Doctor: sibling of `candidates.review_pending` → pending duplicate pair count + fix text.
- Lint: **new** rule (do not overload body-similarity `duplicate_detection`).
- Agent kit: update `wiki-candidates.md`.

### Docs / changelog

User-visible CLI/site behaviour → `CHANGELOG` Unreleased + reference docs as CONTRIBUTING requires; heal_kb row if doctor strings land.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** candidates batch apply, dismissal ledger, topics vocabulary, known-names prepare, site build candidates page, doctor/lint registries.
- **Potential Risks & Mitigations:**
  - False-positive review noise → durable keep-distinct forever.
  - Cross-kind merge UX → document survivor kind wins on the Candidates page.
  - Silent drop of `keep_distinct` if coerce not updated → extend `_coerce_ledger` with tests.
  - Stub `merge` collision → new verbs only.
  - Prepare skip without post-process → repair on load + derive keep.
  - Batch partial failure mid-merge → order merges carefully; fail closed on I/O for merge-pages if needed.

---

## 4. Testing Strategy

- Pair detection: fold cases, undirected dedupe, skip keep-distinct, include projects — extend topics tests or `tests/test_duplicate_page_pairs.py` (no issue number in filename).
- Ledger keep-distinct: upsert / idempotency / coerce — `tests/test_dismissal_ledger.py`.
- `merge_pages`: same-kind, cross-kind, aliases, links, archive, ledger — candidates or dedicated merge tests.
- Batch validate/apply mix of stub + page actions — candidates_site + CLI tests.
- HTML/payload section + Apply JSON shape — render/candidates site tests.
- Consolidation: prompt contains fixed titles; post-process undoes curated fold; keep-distinct honored — topics_consolidate tests (**assert no extra synthesize call**).
- Doctor/lint/agent-kit string/coverage as applicable.
