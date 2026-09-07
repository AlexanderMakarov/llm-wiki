# Flow log — 223-analytics-avg-session-divisor

## fetch-bug
- BUG_ID: 223
- Title: Analytics avg-tokens-per-session uses a different divisor than the session count on the same page
- URL: https://github.com/AlexanderMakarov/llm-wiki/issues/223
- State: OPEN; labels: bug, important; no comments; no linked PR
- Symptom: Analytics "avg / session" divisor ≠ session-count tile; implied ~483 vs 706 sessions; raw non-empty token_totals ~724
- Suspected cause: `compute_site_stats` in `llmwiki/viz_tokens.py` counts only sessions under `metas_by_project` with ≥1 non-zero token category
- Preferred option (issue): Option 2 — keep narrower population but label it (e.g. "15.2M / session (483 sessions with token data)"); also clarify cumulative billed throughput vs context occupancy
- Next: resume-detection

## resume-detection
- Not closed; no merged/open PR for #223
- No pre-existing owning functional-spec for avg-token Analytics tiles → orphan fix-as-spec `223-analytics-avg-session-divisor`
- Dirty primary tree (unrelated): behind origin/main 9; local mods under 200-release-skill, docs; untracked screenshots/.automation — not a blocker
- Next: workspace

## workspace
- BRANCH: fix/223-analytics-avg-session-divisor
- WT: /home/i4ellendger/code/llm-wiki/.claude/worktrees/fix-223-analytics-avg-session-divisor
- TMP_VAULT: /home/i4ellendger/code/llm-wiki/.claude/worktrees/fix-223-analytics-avg-session-divisor/.worktree-vault (recreated after nested-path mistake)
- base: origin/main @ 309580a
- Next: diagnose

## diagnose
- Reproduction: yes — synthetic 7 sessions in TMP_VAULT; hero 7 mains; Tokens 40.0K with 10.0K / session avg → divisor 4 hidden
- Root cause: `llmwiki/viz_tokens.py:compute_site_stats` — avg divisor = sessions with ≥1 non-zero token category; `render_site_token_stats` hides N; hero in `build.py:render_analytics` uses `len(all_sources)`
- Note: narrowing is token filter more than project-attribution gap for this avg; MCP unattributed card is separate
- Next: classify

## classify
- Verdict: orphan / intentional UX honesty (Option 2) — no pre-existing functional-spec for Analytics avg-token tile labeling
- SPEC_NAME: 223-analytics-avg-session-divisor
- Amend-spec: skip — "no functional-spec to amend"
- Still ship CHANGELOG + any user-facing docs that describe the tile if present
- Next: fix

## fix
- Option 2: keep token-bearing divisor; sub-label `{avg} / session ({N} with token data)`; muted note under grid for billed throughput vs context occupancy
- Touched: `llmwiki/viz_tokens.py`, `tests/test_viz_tokens.py` (assert pattern only), `CHANGELOG.md`, `docs/reference/ui.md`, this flow-log
- Out of scope here: hero session count; Option 1/3; dedicated regression suite (testing-expert)
- Next: verify / PR

## regression-test
- Added `test_site_stats_labels_token_bearing_divisor_count` in `tests/test_viz_tokens.py`
- pytest tests/test_viz_tokens.py: 48 passed
- Next: verify-criteria

## verify-criteria
- Criteria checked (Option 2 / #223):
  1. Avg keeps token-bearing divisor — PASS (40.0K total → 10.0K avg with N=4 of 7)
  2. Sub-label surfaces N — PASS: `10.0K / session (4 with token data)`; bare `/ session avg` absent
  3. Throughput clarification note — PASS on analytics.html under token-stat grid
  4. Hero still wider population — PASS: `7 main sessions` unchanged alongside labeled avg
- Evidence: `python3 -m llmwiki build --vault .worktree-vault` + rg on site/analytics.html; regression test green
- Amend-spec: skipped (orphan)
- Next: smoke confirm from operator, then local-review

## verify-criteria (smoke)
- Operator confirmed LGTM on live vault Analytics after worktree build; authorized merge with --admin
- Live evidence: hero 505 mains; Tokens 7.5B → 15.4M / session (487 with token data); billed-throughput note present
- Next: local-review → commit-push → PR → merge --admin

## local-review
- Verdict: Approve; Blockers 0; Nits 1 (stale module docstring pointing at site/index.html — dropped for this PR)
- Review file: context/spec/223-analytics-avg-session-divisor/review.md (session-only, not committed)
- ruff: all checks passed; pytest tests/: green
- Next: commit-push (last flow-log write)

## commit-push
- Staging code + docs + CHANGELOG + flow-log; excluding review.md, config.json, .worktree-vault
- Conventional commit referencing #223
- Next: remote-gates (stop appending flow-log after PR opens)
