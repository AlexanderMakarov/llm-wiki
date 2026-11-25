# Flow log — #371 numeric-looking tags lose text on frontmatter round-trip

## fix-bug #371 — fetch & workspace (2026-11-22)
- Bug: [#371](https://github.com/AlexanderMakarov/llm-wiki/issues/371) — tag `1.10` writes unquoted and parses as float `1.1`; `str()` (#370) cannot recover original text.
- Branch `fix/371-numeric-tag-roundtrip`, worktree `.claude/worktrees/fix-371-numeric-tag-roundtrip`, throwaway vault `.worktree-vault/`.
- MAIN=/home/i4ellendger/code/llm-wiki
- Spec: fix-as-spec `371-numeric-tag-roundtrip` (related follow-up to `370-numeric-tag-resynth`; no functional-spec owns tag YAML quoting).
- Next: diagnose.

## fix-bug #371 — diagnose & classify (2026-11-22)
- Repro: unquoted `tags: [..., 1.10, ...]` → parse yields float `1.1`; quoted `"1.10"` round-trips. Same damage for `007`, `1e3`.
- Root cause: `_frontmatter._parse_scalar` int/float-coerces bare list items; writers emit unquoted `', '.join(tags)` in `synth/pipeline._build_source_page`, `add_doc._frontmatter`, `migrate_whole_document_storage._canonical_page_text`, and `tags._apply_op` (rename/add).
- No existing YAML quote helper for tags; titles already use `json.dumps`.
- Classification: **conformance** (orphan) — tags must read back as written; no functional-spec to amend (`SPEC_NAME=371-numeric-tag-roundtrip`). Related prior: `370-numeric-tag-resynth`.
- Fix-shape decision pending operator (write-side quote vs reader raw-text vs both).
- Next: fix after shape choice.

## fix-bug #371 — fix shape chosen (2026-11-22)
- Operator chose **1: write-side quoting** (format_inline_list / _quote_list_item via _parse_scalar round-trip check; json.dumps).
- Next: fix, then regression test.

## fix-bug #371 — fix (2026-11-22)
- Added `_quote_list_item(s)` and `format_inline_list(items)` to `llmwiki/_frontmatter.py`: an item is JSON-quoted when `_parse_scalar(s, coerce_bool=False) != s`, or it contains `,`, or has surrounding whitespace; otherwise it stays bare.
- Wired writers: `llmwiki/synth/pipeline.py` (`_build_source_page`), `llmwiki/add_doc.py` (`_frontmatter`), `llmwiki/migrate_whole_document_storage.py` (`_canonical_page_text`), `llmwiki/tags.py` (`_rewrite_frontmatter_tags`: `rename_to` / `add_tag` quoted for inline, block, seeded and appended fields).
- Docs: `CHANGELOG.md` — the existing `[Unreleased]` #370 entry already described the numeric-tag surface (still unreleased), so it was edited to the final behaviour (and its "still reads back as 1.1" caveat removed) instead of adding a new *Fixed* entry. No docs/reference page documents the tag YAML form.
- Known follow-up for tests: `tests/test_ai_suggested_tags.py::test_build_source_page_preserves_numeric_existing_tag_on_resynthesize` (`numeric-in-list`, `numeric-scalar`) asserts the old unquoted `10.3` / `2026` output and must expect `"10.3"` / `"2026"` quoted. Full suite otherwise green; `ruff check` clean.
- Next: regression tests (testing-expert).

## fix-bug #371 — regression tests (2026-11-22)
- Updated `tests/test_ai_suggested_tags.py::test_build_source_page_preserves_numeric_existing_tag_on_resynthesize` (`numeric-in-list`, `numeric-scalar`): expects quoted `"10.3"` / `"2026"` on the written `tags:` line and asserts the parsed tag list equals the original strings.
- Added: `test_build_source_page_resynthesize_keeps_trailing_zero_tag_text` (`1.10` survives re-synthesize, never `1.1`); `tests/test_frontmatter_shared.py::test_format_inline_list_round_trips_tag_text` (`1.10`, `007`, `1e3`, `2026`, padded) and `test_format_inline_list_quotes_numeric_but_keeps_plain_tags_bare`; `tests/test_tags.py` `add_tag_to_page` (`1.10`/`007`/`1e3`) and `rename_tag` round-trips; `tests/test_add_doc.py::test_frontmatter_numeric_looking_user_tags_read_back_as_text`.
- RED check: with `_quote_list_item` patched to the identity in memory (no source edit), all new/updated cases fail (14 failures across the four modules); with the fix they pass.
- Out of scope, observed: a tag containing a comma is quoted by the writer but the inline-list reader still splits on `,`, so it does not round-trip; not asserted by these tests.
- Next: verify / PR.

## fix-bug #371 — verify criteria (2026-11-22)
- Touched criterion: numeric-looking tags (`1.10`) read back exactly as written after add + synth writers.
- Evidence (throwaway vault): `llmwiki add … --tag 1.10` wrote `tags: [wiki-add, raw-doc, "1.10", probe]`; dummy synth source page kept parsed `1.10` and quoted form on the tags line (`CRITERION_PASS`).
- Targeted pytest (frontmatter/ai_suggested_tags/tags/add_doc): exit 0.
- Classification remains conformance; amend-spec skipped.
- Next: smoke confirm, then local review.

## fix-bug #371 — smoke confirm (2026-11-22)
- Operator asked agent to run smoke. RO `format_inline_list` pass; throwaway vault source still has quoted `"1.10"`.
- Live: `python3 -m llmwiki add … --tag 1.10 --no-build` (worktree) wrote `tags: [wiki-add, raw-doc, "1.10", 371-smoke]`; parsed back as `1.10`. Probe dir removed; `llmwiki-state.json` restored from backup. (`llmwiki tag` is not a CLI command — library-only.)
- Next: local review (amend-spec skipped).

## fix-bug #371 — local review keep/drop (2026-11-22)
- Independent review: Comment — 0 blockers, 3 nits (`review.md`, session-only).
- Operator: N1 keep as **do not support commas inside tags** (drop comma-quoting clause + pin test); N2 keep (CHANGELOG caveat for pre-existing bare `1.10`); N3 keep (stage `flow-log.md` at commit; do not commit `review.md`).
- Applied in worktree; next: static gate, commit-push.

## fix-bug #371 — commit-push (2026-11-22)
- Static gate: `ruff check` clean; full `pytest tests/` exit 0 after review findings applied.
- PR link keyword: `Closes #371` — issue owns the lossy `1.10` frontmatter round-trip; write-side quoting delivers it (comma-in-tag unsupported by design).
- Stage: code + tests + CHANGELOG + `context/spec/371-numeric-tag-roundtrip/flow-log.md`. Exclude `review.md`, vault, `config.json`.
- Next: remote gates (no further tracked flow-log appends after PR open).

## post-merge CI fix-forward (2026-11-25)
- Post-merge on #428 failed: `content_freshness` warned on fixture pages with fixed `last_updated: 2026-08-26` (now >90 days). Unrelated to tag quoting; calendar drift.
- Fix: `tests/test_lint_vault_settings.py` and `tests/test_all_min_refs.py` use `date.today() - 7 days` for fixture `last_updated`.
- Link check failure updates tracking #221 (not a required branch check).
