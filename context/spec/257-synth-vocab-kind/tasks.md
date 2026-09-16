# Tasks: Inject topic kind into per-page synth vocabulary (#257)

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md)
- **Technical Specification:** [`technical-considerations.md`](./technical-considerations.md)
- **Status:** Completed

---

- [x] **Slice 1: Shared kind map leaf + cache `kinds` + vocabulary `kind=`**
  - [x] Extract `build_kind_map` / `_KIND_FOLDERS` (and `_CONTEXT_FILE` if needed) from `llmwiki/migrate_topic_kinds.py` into leaf `llmwiki/topic_kinds.py`; update migrate to import from the leaf; keep migration behaviour and public `build_kind_map` import path working for existing tests. **[Agent: generalPurpose]**
  - [x] Extend `load_cache` in `llmwiki/topics_consolidate.py` to return `kinds: {canonical: entity|concept}` for topics with a valid kind. **[Agent: generalPurpose]**
  - [x] Update `_inject_vocabulary` in `llmwiki/synth/pipeline.py`: once per inject load cache kinds + `build_kind_map`; for each topic emit `kind=` when resolved (cache first, else unique page/pending filing; omit on dual filing / unknown). **[Agent: generalPurpose]**
  - [x] Add/extend tests in `tests/test_topics.py`: cache kind on vocab row; page-filing fallback; cache wins over page; ambiguous dual filing omits kind; existing desc/with/aka assertions still pass. Run focused pytest + ruff on touched files. **[Agent: generalPurpose]**
  - [x] Verify: from worktree, `python3 -m pytest tests/test_topics.py tests/test_migrate_topic_kinds.py -q` and `ruff check llmwiki/topic_kinds.py llmwiki/migrate_topic_kinds.py llmwiki/topics_consolidate.py llmwiki/synth/pipeline.py tests/test_topics.py` — all green. Delete any ephemeral verify artifacts. **[Agent: generalPurpose]**

- [x] **Slice 2: Prompt rules + docs**
  - [x] Update `llmwiki/synth/prompts/source_page.md` Existing topics comment + Rules: document `kind` attribute; parentheses must be exactly `entity` or `concept`; copy listed kind when linking a vocabulary topic. **[Agent: generalPurpose]**
  - [x] Docs: `docs/reference/cli.md` synth section — contrast job-1 known-names preparation vs candidates harvest / `--candidates-only`; point label-only catch-up at `migrate topic-kinds`. `CHANGELOG.md` Unreleased + release-note bullet; `docs/UPGRADING.md` one-liner if needed. **[Agent: generalPurpose]**
  - [x] Verify: assert prompt file contains free-form-kind prohibition and copy-kind guidance (pytest or shell grep); `ruff` N/A for md; spot-check cli.md wording. **[Agent: generalPurpose]**

- [x] **Slice 3: Feature testing & regression**
  - [x] Confirm FR1–FR5 coverage via tests + doc assertions; run `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q` from the worktree. Annotate new tests with `@spec` only if the project already does for similar cases. **[Agent: testing-expert]** *(orchestrator ran gates after testing-expert hit usage limit)*
