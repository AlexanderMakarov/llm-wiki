# Flow log — #370 re-synth crashes on a numeric tag in the existing source page

## fix-bug #370 — fetch, diagnose, classify (2026-10-26)
- Bug: [#370](https://github.com/AlexanderMakarov/llm-wiki/issues/370) — re-synthesizing a source whose existing wiki page carries a bare numeric tag (`10.3`) fails with `'float' object has no attribute 'strip'`; `llmwiki all` turns that synth error into exit 1, so the scheduled run reports failure daily.
- Branch `fix/370-numeric-tag-resynth`, worktree `.claude/worktrees/fix-370-numeric-tag-resynth`, throwaway vault `.worktree-vault/`.
- Spec: fix-as-spec directory (no functional spec owns synth tag merging). No functional-spec to amend.
- Root cause: `_build_source_page` reads the existing page's `tags` through `parse_frontmatter`, which types `10.3` as a float, and passes them un-coerced to `_merge_tags`, whose `_push` calls `tag.strip()`. Raw-meta tags were already coerced by `_derive_baseline_tags`.
- Classification: **conformance** — preserving curated tags on re-synthesize is existing behaviour; the code crashed instead.

## fix-bug #370 — fix, regression test, verify (2026-10-26)
- `llmwiki/synth/pipeline.py` `_build_source_page`: existing-page tags are coerced with `str()` at the read site, so `_merge_tags` keeps receiving `list[str]`.
- Regression test `tests/test_ai_suggested_tags.py::test_build_source_page_preserves_numeric_existing_tag_on_resynthesize` — failed on the old code with the production `AttributeError`, passes on the fix.
- Verify (throwaway vault, `--backend dummy`): a raw doc tagged `10.3` synthesized, then re-synthesized with `--force` over the page it wrote; both runs synthesized 1, the page keeps `10.3` in `tags:`.
- Out of scope, noted for a follow-up: writers emit tags unquoted, so a tag like `1.10` round-trips as `1.1`.
- Next: smoke confirm, local review.

## fix-bug #370 — local review keep/drop (2026-10-26)
- Independent review (session-only `review.md`): **Approve** — 0 blockers, 3 nits. Operator kept all three.
- N1: a scalar `tags:` on the existing page is wrapped in a list before coercion, so `tags: 10.3` no longer raises `TypeError` and `tags: foo` stays one tag. The regression test is parametrized over list / numeric scalar / string scalar; each case fails on `origin/main`'s `pipeline.py` (`AttributeError`, `TypeError`, letter split) and passes on the fix.
- N2: CHANGELOG narrowed — the `1.10` → `1.1` round-trip loss is filed as [#371](https://github.com/AlexanderMakarov/llm-wiki/issues/371).
- N3: `flow-log.md` is staged with the code; `review.md` stays untracked.
- Next: static gate, smoke confirm, commit-push.

## fix-bug #370 — smoke, commit-push (2026-10-26)
- Static gate: `ruff check` clean; full `pytest tests/` exit 0.
- Smoke (agent-run at operator request, backups taken first): worktree `synth --vault <live> --backend claude --sources-only --path <the failing raw doc>` — synthesized 1, rc 0; the page keeps `10.3` in `tags:`.
- PR link keyword: `Closes #370` — the issue owns the re-synth crash on a numeric tag, which this delivers (plus the scalar `tags:` shape of the same crash); the lossy `1.10` round-trip belongs to #371.
