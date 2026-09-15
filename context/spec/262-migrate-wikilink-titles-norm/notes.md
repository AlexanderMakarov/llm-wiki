# Notes — migrate wikilink-titles case/punct variants (#262)

## Problem

After #259, bare `[[LLM-Wiki]]` stayed unrewritten when the page slug was `llm-wiki`. Exact `resolve_wikilink_target` missed variants that `link_integrity` already accepts via page-identity folding.

## Fix

Migrate resolves exact first, then unique `norm_page_key` match (same folding as `link_integrity` / harvest). Same-identity variants rewrite to `[[canonical-slug|Title]]` (section kept). True aliases (different norm) and ambiguous collisions stay skipped.

`rewrite_wikilink_titles` always builds the page-key index from the passed `slugs` set — no optional `by_norm` / opt-out. Page identity folding is not caller-configurable.

## DRY (#259 / #262 follow-up)

`norm_page_key` lives in `llmwiki.wikilinks` (leaf module). Consumers: `link_integrity`, `candidates_harvest`, `migrate_wikilink_titles`. This folds the **wikilink target / page stem**, not topic vocabulary labels (`topics.topic_slug` stays separate). Review bar: `docs/maintainers/REVIEW_CHECKLIST.md` Code quality → Follows DRY.

## Verify

- `tests/test_wikilinks.py` — `norm_page_key` folds
- `tests/test_migrate_wikilink_titles.py` — case variant, punct variant, section, ambiguous, alias skip
- Live: re-run `migrate wikilink-titles --dry-run` and confirm araratbank (and similar) `[[LLM-Wiki]]` lines would rewrite
