# Tasks: Findability by page title (#259)

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md)
- **Technical Specification:** [`technical-considerations.md`](./technical-considerations.md)
- **Status:** In Progress

---

- [x] **Slice 1: Offline `wikilink-titles` migration (library + tests)**
  - [x] Implement `llmwiki/migrate_wikilink_titles.py`: build slug→title map from wiki scan; rewrite bare resolving `[[slug]]` / `[[slug#section]]` → `[[slug|Title]]` / `[[slug#section|Title]]`; skip display-pipe, unresolved, non-bare-slug, empty/unsafe titles; `run_migration` / `print_report`; dry-run no writes; never import synth backends; never touch `raw/`. Add `tests/test_migrate_wikilink_titles.py` covering rewrite, section preserve, skips, dry-run, no-LLM-import. **[Agent: generalPurpose]**

- [x] **Slice 2: CLI registration + reference docs for migrate**
  - [x] Register `wikilink-titles` in `llmwiki/cli.py` `_MIGRATIONS` + `cmd_migrate_wikilink_titles` + subparser (`--vault`, `--dry-run`). Document in `docs/reference/cli.md`. Update `tests/test_112_acceptance.py` expected migration name set. CLI parse/dry-run smoke in migrate tests. **[Agent: generalPurpose]**

- [x] **Slice 3: Drop page_findability R2 (title-only findability)**
  - [x] Remove wikilink-anchor search branch and `_is_phrase_anchor` from `llmwiki/lint/rules/page_findability.py`; narrow rule description to title-only. Update `tests/test_lint_findability.py` (invert/remove bare-wikilink corpus-cap failure; add slug-links-do-not-error; keep title failure tests). Update findability wording in `docs/reference/cli.md` and `docs/reference/slash-commands.md`. **[Agent: generalPurpose]**

- [x] **Slice 4: UPGRADING + CHANGELOG**
  - [x] `docs/UPGRADING.md`: optional offline `migrate wikilink-titles` (zero LLM); title vs slug contract. `CHANGELOG.md` Unreleased: R2 drop + migrate + docs. **[Agent: generalPurpose]**

- [x] **Slice 5: Feature testing & regression**
  - [x] Run `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q` from worktree; confirm demo `python3 -m llmwiki lint --vault demo --rules page_findability` emits no wikilink-anchor errors. Fix any regressions. **[Agent: testing-expert]**
