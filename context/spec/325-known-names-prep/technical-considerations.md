# Technical Specification: Bound and speed up known-names preparation (#264)

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** 4ellendger

---

## 1. High-Level Technical Approach

Extend job 1 (`prepare_known_names` in `llmwiki/topics_consolidate.py`) so each LLM synth run: (1) caps candidates by session reach, (2) skips or shrinks the consolidation call using a fingerprint over name / aliases / reach bucket, (3) uses a synthesis-root dedicated timeout via an optional `timeout=` on `synthesize_source_page`, and (4) reports candidates sent, prompt/reply sizes, duration, and backend usage when available. Keep the existing JSON wire format and a single `parse_and_cache` (or successor merge path) into `.llmwiki-topics.json`, always preserving `kind` on reuse (#257). Config and “how to choose the cap” docs land under a new `synthesis.known_names` group in `docs/configuration-reference.md` (plus CLI/CHANGELOG pointers). No new runtime deps.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Architecture Changes

None at the product-architecture level. Same #147 jobs: job 1 writes `.llmwiki-topics.json`; job 2 injects vocabulary. This change only bounds and caches job 1.

### 2.2 Configuration (`synthesis.known_names`)

Cross-backend synth policy (same layer as `synthesis.concurrency` / `overview_model`), **not** under `synthesis.claude` / `cursor_cli` / `ollama`.

| Key | Type | Default | Purpose |
| --- | --- | --- | --- |
| `synthesis.known_names.candidate_cap` | int | `150` | Max candidates sent to the model (highest `sessions` first; stable tie-break by name). |
| `synthesis.known_names.timeout` | int (seconds) | resolve as `max(600, active_backend_page_timeout)` when unset | Dedicated wait for the known-names call only. |

Loader: small helpers next to other synth resolvers (e.g. in `topics_consolidate.py` or `pipeline.py`) reading `_load_sessions_config()` / passed `cfg`. Invalid / non-positive ints → warn and fall back to defaults (same spirit as concurrency clamping).

**Docs (FR5):** In `docs/configuration-reference.md` (and a short CLI synth pointer), document both keys **and** the “how to choose `candidate_cap`” guidance from the functional spec: what the number bounds (not article size), cost/time, quality effect, and that exceeding ~150 usually means a very large or poorly curated vault — prefer cleanup over raising the cap forever.

### 2.3 Candidate cap

- After `build_candidates`, sort by `sessions` descending, then `name` ascending; take `[:cap]`.
- `render_consolidation_prompt` accepts an explicit candidate list (or capped list) so tests do not depend on re-scanning the graph.
- Topics below the cut: untouched cache entries remain in `.llmwiki-topics.json` and stay available via `load_cache` / `_inject_vocabulary`; names with no cache entry keep today’s heuristic vocabulary path.

### 2.4 Incremental reuse (fingerprint + merge)

**Reach bucket** (invalidate only on meaningful growth, not every +1 session):

| `sessions` | bucket id |
| --- | --- |
| 2–3 | `2-3` |
| 4–7 | `4-7` |
| 8–15 | `8-15` |
| 16–31 | `16-31` |
| ≥32 | `32+` |

**Per-candidate signature:** `casefold(name) | sorted(casefold(aka)) | bucket`.  
**Run fingerprint:** stable hash (e.g. SHA-256 hex) over the sorted signatures of the **capped** candidate list.

**Cache schema:** bump to `"version": 2`. Add:

- `inputs_fingerprint`: last successful prep fingerprint (capped set).
- Optional per-topic `source_sig` (same signature string) for the candidates that produced / last refreshed that entry — used to decide delta membership without re-asking unchanged names.

v1 files without fingerprint: treat as cold (full capped call once), then rewrite as v2. `load_cache` continues to expose `kinds` / descriptions / aliases for all stored topics.

**Prepare flow:**

1. Build + cap candidates.
2. If cache present, fingerprint matches, and every capped candidate’s signature is covered by an existing topic/`source_sig` (or equivalent coverage rule): **skip LLM**; print skip/reuse report; return.
3. Else compute **delta** = capped candidates whose signature is new or changed vs cache.
4. If delta non-empty: render prompt with **delta only** (same XML shape); call model with dedicated timeout; merge reply into existing `topics` / `dropped` without dropping untouched entries (preserve `description`, `aliases`, `kind`, `distinct_from` for names not in the reply).
5. Update fingerprint + `source_sig` for processed candidates; write cache.

**Must keep:** every cached topic that already has `kind` retains it across skip and merge (#257 §2.9).

### 2.5 Dedicated timeout on backends

Owner shape from the issue thread, adapted to a nested key:

- Add kw-only `timeout: float | None = None` to `BaseSynthesizer.synthesize_source_page` and LLM backends (`claude_cli`, `cursor_cli`, `ollama`) + Dummy (accept/ignore).
- When `timeout` is set, use it as the call bound **instead of** `page_timeout_seconds(self.timeout, body_len)` (known-names body is empty anyway).
- When `None`, keep today’s per-page behaviour (including #311 scaling for documents).
- `prepare_known_names` resolves `synthesis.known_names.timeout` once and passes it in. Failure behaviour unchanged: warn + heuristic fallback; `BackendUsageLimitError` still propagates (#181).

Do not rely on automation wrappers alone — the CLI child timeout is what kills the call.

### 2.6 Reporting

Extend the existing progress `print` / warning path in `prepare_known_names`:

- Always: mode (`full` / `delta` / `skip`), candidates considered, candidates sent (0 on skip), prompt bytes (0 on skip), reply bytes (0 on skip/fail), duration seconds.
- When the backend exposes run usage for that call (Claude already aggregates tokens/cost on the instance): include tokens and/or cost if attributable; otherwise omit those fields without failing the step.
- Skip path must be visibly distinct (“reusing cached known names…”) so FR4’s zero-call case is obvious in logs.

### 2.7 Parse path

Keep **one** authoritative parse → cache path. Prefer extending `parse_and_cache` with an optional `merge_into: dict | None` (existing cache) rather than a second wire-format parser. Tests: happy path, truncated/malformed reply (no silent corrupt write), merge-into-existing preserves untouched entries including `kind`.

Wire format stays JSON (leaner formats out of scope).

### 2.8 Docs / CHANGELOG

- `docs/configuration-reference.md` — `synthesis.known_names` rows + how-to-choose prose for `candidate_cap`.
- `docs/reference/cli.md` — short synth note pointing at the new keys / skip behaviour.
- `CHANGELOG.md` `[Unreleased]` — user-visible behaviour (cap default 150, incremental skip, dedicated timeout, reporting).
- This spec dir + flow-log satisfy the context/ product-PR gate.

### 2.9 Out of scope

- Leaner reply format / short keys (#264 optional item 5).
- Changing candidates harvest / promote / rewrite detectors.
- Changing `_inject_vocabulary` beyond continuing to read `load_cache()["kinds"]`.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** `build_topic_graph` / `build_candidates`; `.llmwiki-topics.json` consumers (`load_cache`, graph merge, `_inject_vocabulary`); Claude/Cursor/Ollama backends; #181 usage-limit path; #257 kind injection.
- **Cache schema bump:** v1 → v2 with fingerprint; one cold call after upgrade is acceptable; never drop `kind` on merge.
- **Over-aggressive delta:** if reach buckets are too coarse, stale descriptions linger — mitigated by buckets above and by operators re-running after major topic cleanup; document that raising the cap without cleanup hurts quality (FR5).
- **Under-aggressive skip:** fingerprint mismatch every run would erase the steady-state win — cover with tests that a second identical capped set makes zero calls.
- **Timeout vs page timeout confusion:** document clearly; default `max(600, page)` avoids regressing backends whose page timeout is already >600.
- **Test doubles:** kw-only `timeout=` with default keeps existing 3-arg spies working.

---

## 4. Testing Strategy

Prefer extending `tests/test_topics.py` and the job-1 blocks in `tests/test_synth_pipeline.py` / `tests/test_181_synth_clean_stop.py` (feature-slug names for any new file; no issue-number filenames). Use Dummy / spy backends — no live paid model.

- [ ] Cap: more candidates than cap → exactly `candidate_cap` sent, highest reach first (spy records prompt or candidate list).
- [ ] Skip: second `prepare_known_names` with unchanged capped set → zero `synthesize_source_page` calls; `load_cache` still has prior `kind`s.
- [ ] Delta merge: add one new candidate → one call whose prompt contains only the delta (or at least not the full prior set); untouched cache entry keeps description/aliases/kind.
- [ ] Timeout: `prepare_known_names` passes resolved known-names timeout into `synthesize_source_page`; page path still uses baseline when `timeout` omitted (unit on backend or spy kwargs).
- [ ] Reporting: skip and success paths emit candidate count / sizes / duration (stdout capture, same style as #181 progress tests).
- [ ] `parse_and_cache` / merge: malformed reply raises and does not corrupt on-disk cache; merge preserves untouched topics.
- [ ] Config defaults: unset keys → cap 150 and timeout `max(600, backend.timeout)`.
- [ ] Docs presence: configuration-reference mentions how-to-choose guidance and both keys (lightweight content assertion or maintainer checklist — prefer a small test only if the repo already greps docs for keys).
- [ ] `ruff check llmwiki tests scripts` + `python3 -m pytest tests/ -q` before push.
