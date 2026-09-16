# Technical Specification: Inject topic kind into per-page synth vocabulary (#257)

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** Alexander Makarov

---

## 1. High-Level Technical Approach

Extend `_inject_vocabulary` so each `<topic …/>` row can carry `kind="entity|concept"` when known, and tighten `source_page.md` so the model must use only those two labels and copy a listed kind. Kind resolution matches the functional order: known-names cache first, else the same folder→kind map used by offline `migrate topic-kinds` (entities/concepts + candidates mirrors). Extract that map builder into a leaf module so synth does not import `migrate_topic_kinds` (which already imports `synth.pipeline` — a cycle today). Docs contrast job-1 known-names preparation vs candidates harvest and keep pointing label-only catch-up at `migrate topic-kinds`. No new runtime deps; no CLI surface change beyond docs.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Architecture Changes

None at the product architecture level. Same synth jobs (#147): job 1 writes `.llmwiki-topics.json`; job 2 injects vocabulary into `source_page.md`. This change only completes the wiring of `kind` that job 1 already may store and that Connections already require.

### 2.2 Shared kind map (leaf module)

**Problem:** `llmwiki/migrate_topic_kinds.py` defines `build_kind_map` / `_KIND_FOLDERS` but imports `llmwiki.synth.pipeline`, so `pipeline._inject_vocabulary` cannot import migrate.

**Plan:** Move `build_kind_map`, `_KIND_FOLDERS`, and the small `_CONTEXT_FILE` constant into a leaf module (preferred name: `llmwiki/topic_kinds.py`). `migrate_topic_kinds` re-exports or imports from there unchanged for callers/tests. Behavior of the migration stays byte-compatible.

Folder → Connections kind (unchanged):

| wiki-relative folder | kind |
| --- | --- |
| `entities` | `entity` |
| `concepts` | `concept` |
| `candidates/entities` | `entity` |
| `candidates/concepts` | `concept` |

Ambiguous dual-filing stays out of the map (same as #174).

### 2.3 Cache exposure

Today `load_cache` returns `topics`, `alias_map`, `descriptions`, `dropped` but does **not** index `kind` even when `parse_and_cache` persisted it.

**Plan:** Add `kinds: dict[str, str]` to the `load_cache` return — map **canonical spelling → `entity`|`concept`** for topics that have a valid kind. Do not invent kinds in `load_cache`. Alias lookup for injection uses existing `alias_map` then `kinds[canonical]`.

Graph node `kind` (`entities` / `concepts` / `projects` / `other`) stays a viewer partition key and is **not** written into vocabulary XML as-is.

### 2.4 `_inject_vocabulary` (`llmwiki/synth/pipeline.py`)

For each graph node (same loop / `_VOCAB_LIMIT` as today):

1. Resolve display `name` as today.
2. Resolve Connections kind:
   - If cache `kinds` has an entry for this topic’s canonical (via node id / alias_map), use it.
   - Else look up `build_kind_map(wiki_dir)[name.casefold()]` when present.
   - Else omit `kind`.
3. Emit `kind="…"` after `name=` when resolved (`_vocab_attr` sanitize). Keep `desc` / `with` as today.

Call `build_kind_map` once per inject (not per node). `synth --estimate` already calls `_inject_vocabulary` — it inherits the change with no separate path.

### 2.5 Prompt (`llmwiki/synth/prompts/source_page.md`)

- In the Existing topics HTML comment: document optional `kind="entity|concept"`; when present, Connections parentheses for that name must copy it.
- In Rules: state that `(…)` on Connections must be exactly `entity` or `concept` (no free-form type nouns); prefer vocabulary kind when linking a listed topic; for a brand-new name not in the list, still choose only `entity` or `concept`.

Output template examples already show `(entity)` / `(concept)` — leave them; they become normative, not decorative.

### 2.6 Docs / CHANGELOG / context

- `docs/reference/cli.md` (`synth` section): one short contrast — job 1 known-names preparation (vocabulary incl. kind) vs later offline candidates harvest / `--candidates-only` (parses Connections; no classify LLM).
- `docs/UPGRADING.md` and/or CHANGELOG Unreleased: note that vocabulary now carries kind; label-only backlog still uses `llmwiki migrate topic-kinds` (#174) — do not force full re-synth for kinds alone.
- Touch `context/` (CONTRIBUTING product-PR rule) — this spec dir + flow-log satisfies the gate; amend product notes only if a durable architecture sentence is needed (optional one-liner under synth in `context/product/architecture.md` is nice-to-have, not required).

### 2.7 Out of scope (explicit)

- #264 candidate cap / incremental known-names / separate timeout.
- Changing harvest, promote, or rewrite-detector predicates.
- Changing `migrate topic-kinds` behaviour beyond the extract/import of `build_kind_map`.

### 2.8 Source-vs-source kind disagreement (operator decision)

When different source pages label the same name as both `entity` and `concept`, **#257 does not resolve the fight in vocabulary injection.** Resolution stays where it already lives:

- Job 1 cache: one LLM-chosen kind per canonical (when present, injected as-is).
- Candidates harvest: `_majority_kind` (majority of usable citing bullets; tie → first usable; else `entity`).
- Page map / migrate: omit only on **dual disk filing** (entities + concepts), not on disagreeing Connections alone.

Vocabulary: cache → else unique page filing → else omit. No unanimous/majority scan of Connections for inject.

### 2.9 #264 compatibility

#264 may later stop calling the model when the cache is unchanged and must **keep** persisting/reusing `kind` on cached topics. Vocabulary injection will keep reading `load_cache()["kinds"]` and the page map fallback, so a capped or timed-out job-1 run still gets kinds from filings (FR1). Do not remove `kind` from the cache schema in #264 without amending this spec.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** `build_topic_graph` / `derive_vocabulary` (unchanged contract); `.llmwiki-topics.json`; `source_page_needs_topics_rewrite`; `migrate topic-kinds`; estimate path sharing `_inject_vocabulary`.
- **Circular import:** Mitigated by leaf `topic_kinds` module.
- **Wrong kind from folder vs cache:** Cache wins (job 1 is authoritative when present). Dual-filed names stay omitted from the page map (never guess).
- **Prompt-only compliance:** Models can still misbehave; FR3 is proven with Dummy/fixture prompt inspection + injected `kind=` attribute tests, not a live paid model. Offline stamp remains the safety net for existing bad pages (FR4).
- **Projects:** Graph `projects` folders do not map to Connections `entity|concept`; those rows omit `kind` unless cache says otherwise — intentional.

---

## 4. Testing Strategy

Extend `tests/test_topics.py` (and a thin migrate import-smoke if the extract moves symbols):

- [ ] Cache kind appears as `kind="entity"` (or concept) on injected vocabulary when `.llmwiki-topics.json` has kind and no conflicting need for pages.
- [ ] Page-filing fallback: no cache kind, but `wiki/entities/Foo.md` (or candidates mirror) → `kind="entity"` on the Foo row.
- [ ] Cache kind wins over a conflicting page filing if both exist (document expected winner = cache).
- [ ] Ambiguous dual filing → no `kind=` from the map path.
- [ ] Prompt fixture / string check: `source_page.md` contains the free-form-kind prohibition and copy-listed-kind guidance (file content assertion is enough; no LLM).
- [ ] Existing `_inject_vocabulary` tests still pass (`desc` / `with` / no `aka`).
- [ ] `migrate topic-kinds` unit suite still green after `build_kind_map` moves.
- [ ] `ruff check llmwiki tests scripts` + `python3 -m pytest tests/ -q` before push.

Optional: Dummy synth end-to-end only if a fixture backend can echo vocabulary kinds into Connections without a real model — prefer prompt + inject unit tests unless an existing Dummy path makes E2E cheap.
