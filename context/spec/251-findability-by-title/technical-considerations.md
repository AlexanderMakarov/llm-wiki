# Technical Specification: Findability by page title (#259)

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md)
- **Status:** Approved
- **Author(s):** Aleksandr Makarov

---

## 1. High-Level Technical Approach

Findability is keyed on **page title** (frontmatter `title` → search). Slug/filename stays link-resolution metainfo. `link_integrity` still owns broken links.

**Lint:** Keep title→page checks in `page_findability`. **Delete R2** (search-for-raw-wikilink-anchor). Do not soften title not-found / rank-past-cap errors.

**Offline migrate:** `llmwiki migrate wikilink-titles --vault PATH [--dry-run]` rewrites bare resolving `[[slug]]` → `[[slug|Title]]` from target frontmatter titles on disk — **zero LLM**.

**Docs:** Title vs slug contract in CLI / slash-command findability notes; migrate catalog + UPGRADING.

---

## 2. Proposed Solution & Implementation Plan

### Lint — drop R2

- `llmwiki/lint/rules/page_findability.py`: remove wikilink-anchor branch, `_is_phrase_anchor`, unused imports; narrow rule description to title-only.
- Keep `collect_wikilink_lookups` in `search/evaluate.py` (still useful; migrate may reuse).
- Update `docs/reference/cli.md` + `slash-commands.md` findability wording; CHANGELOG.

### Migrate — `wikilink-titles`

- New `llmwiki/migrate_wikilink_titles.py` (same shape as `migrate_topic_kinds`): slug→title map from wiki scan; rewrite bare links where anchor casefolds to resolved slug; preserve `#section`; skip display-pipe / unresolved / unsafe titles (`|`, `]]`); idempotent (second run skips).
- Register in `cli.py` `_MIGRATIONS` + subparser (`--vault`, `--dry-run`); no stamp JSON.
- Never import synth backends; never touch `raw/`.

### Docs

- Findability = title; slug = filesystem/link target; prefer `[[slug|Title]]`.
- UPGRADING: optional migrate after this release (cosmetic/readability; not required for lint green once R2 is gone).

---

## 3. Impact and Risk Analysis

| Risk | Mitigation |
| --- | --- |
| Hub pages still look “sluggy” after lint goes green | Optional migrate + docs |
| Title contains `\|` / `]]` | Skip + report |
| Alias-only `[[MergedAway]]` | Only rewrite when written anchor == resolved slug |
| Stem collisions | Same “later path wins” as graph |
| Accidental rewrite in code fences | Opt-in migrate; document; test if fixtures need it |

---

## 4. Testing Strategy

- **New** `tests/test_migrate_wikilink_titles.py`: rewrite / dry-run / skip cases / no LLM imports / CLI parse.
- **Update** `tests/test_lint_findability.py`: remove/invert bare-wikilink corpus-cap error; add “slug links do not error”; keep title-failure tests.
- Smoke: demo `lint --rules page_findability` has no wikilink-anchor errors; `ruff` + full pytest gate before push.
