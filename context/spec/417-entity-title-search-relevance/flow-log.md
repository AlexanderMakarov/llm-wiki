# Flow log — 417-entity-title-search-relevance (#417)

## fetch-bug
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/417
- Title: search: short common entity titles lose to incidental mentions (relevance / findability)
- Labels: bug, important, self-heal
- State: OPEN; no comments; no merged PR for this fix
- Symptom: short common entity/concept titles (Cursor, React, Compose, …) rank far past page_findability cap (~200) behind session/source mention flood; lint reports error though page exists and is correctly titled
- Related: page_findability (#197), title-keying (#259), title_ambiguity; optional hybrid/BM25 (#392); not provenance/#277

## resume-detection
- Not already fixed. No matching merged PR.
- Owning completed specs for findability/search health: `197-search-quality-eval`, `251-findability-by-title` (do not soften rank-past-cap). Note: `context/spec/417-synth-tests-consolidate` is #318 layout work — unrelated AWOS index collision.
- Allocated fix-as-spec: `417-entity-title-search-relevance`

## workspace
- BRANCH=`fix/417-entity-title-search-relevance`
- WT=`<repo>/.claude/worktrees/fix-417-entity-title-search-relevance`
- MAIN=`<repo>`
- TMP_VAULT=`<worktree>/.worktree-vault`
- Next: diagnose

## diagnose
- Repro: synthetic vault under TMP_VAULT/repro417 — entity `Cursor.md` (~6.4KB with sessions list) + 250 source pages titled `Cursor session N`; `page_findability` → rank 251 > cap 200; entity score 124.745 vs sources 127.5
- Root cause: `llmwiki/search/scoring.py::score_extract` — title scoring is substring-only (+100 phrase / +20 token); no exact whole-title bonus; short pages with title substring beat longer curated entity via body length normalisation
- Site Ctrl+K uses `match_page` (term mode) — not this scorer; CLI/MCP extract + findability share `score_extract`
- Fix shape: exact whole-title bonus (≥100) in `score_extract`; optional title-coverage; no kind boost unless needed; do not soften lint / PAGE_CAP
- Touch: scoring.py, test_search_package.py, test_lint_findability.py (+ regression), demo_search_baseline.json re-record, docs/reference/cli.md, CHANGELOG
- Classification hint from diagnosis: **Conformance**

## classify
- Verdict: **Conformance**
- Spec 197 R3: titled page must be returned for its own title on a healthy vault; rank-past-cap on a correctly titled entity is the code violating that intent
- Spec 251: do not soften title not-found / rank-past-cap; browser ranking overhaul out of scope (site term mode untouched)
- No functional-spec amendment required; docs/CHANGELOG describe the scoring fix; re-record demo baseline deliberately (197 R6)
- SPEC_NAME remains fix-as-spec `417-entity-title-search-relevance` (no invent functional-spec.md)
- Next: fix

## fix
- `score_extract`: `EXACT_TITLE_BONUS = 200.0` when casefolded trimmed title == query.lower (not query.raw — lint keys)
- No title-coverage / kind boost; PAGE_CAP and severities unchanged
- Docs: `docs/reference/cli.md` phrase-mode ranking note; CHANGELOG Unreleased *Fixed* #417
- Demo baseline re-recorded (extract MRR/rank1 → 1.0)

## regression-test
- Unit: `tests/test_search_package.py` (exact-title ordering + casefold)
- Lint: `tests/test_lint_findability.py` flood regression + title_ambiguity quiet when exact wins
- Fixture updates: feature regression + outranker case-variant
- Mutation: bonus=0 fails the three new behaviour tests
- Full suite in WT: green

## verify-criteria
- Synthetic repro417: page_findability + title_ambiguity → 0 errors / 0 warnings (251/251)
- Targeted pytest green
- Next: **user smoke confirm** (required before local-review)

## verify-criteria (smoke)
- Operator: **lgtm / continue** (2026-11-20)
- Live phrase search: `wiki/entities/Cursor.md` rank 1 (~325 vs ~127 stubs)
- Live lint page_findability+title_ambiguity: 0 errors (Cursor absent from warnings)
- Synthetic repro417 + targeted pytest green earlier in run
- Classification still **Conformance** → skip amend-spec
- Next: local-review

## local-review
- Review file: `review.md` (session-only, not committed). Verdict: Request changes (1 Blocker, 2 Nits)
- keep/drop: **keep all** (operator chose 1)
- Applied: B1 placeholder paths in this log; N1 drop duplicate diagnose/classify; N2 commit/PR reminders at commit-push
- Static gate: ruff + full pytest green

## commit-push
- Issue link keyword for PR: `Closes #417` — ticket owns the findability/relevance symptom fully; hybrid/BM25 (#392) is a separate track named only as optional related work
- Next: push + open PR (stop appending this tracked log once the change request is open)
