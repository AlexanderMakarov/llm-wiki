# Notes — migrate wikilink-titles case/punct variants (#262)

## Problem

After #259, bare `[[LLM-Wiki]]` stayed unrewritten when the page slug was `llm-wiki`. Exact `resolve_wikilink_target` missed variants that `link_integrity` already accepts via `_norm_slug`.

## Fix

Migrate resolves exact first, then unique `_norm_slug` match (same folding as `link_integrity`). Same-identity variants rewrite to `[[canonical-slug|Title]]` (section kept). True aliases (different norm) and ambiguous collisions stay skipped.

`rewrite_wikilink_titles` always builds the norm index from the passed `slugs` set — no optional `by_norm` / opt-out. Page identity folding is not caller-configurable.

## Verify

- `tests/test_migrate_wikilink_titles.py` — case variant, punct variant, section, ambiguous, alias skip
- Live: re-run `migrate wikilink-titles --dry-run` and confirm araratbank (and similar) `[[LLM-Wiki]]` lines would rewrite
