# Flow log — 323-total-tokens-coverage-hint

## fetch-bug
- BUG_ID: 323
- Title: fix(ui): explain Total tokens coverage and missing agents on hover
- URL: https://github.com/AlexanderMakarov/llm-wiki/issues/323
- Labels: bug, important, self-heal
- State: OPEN; no linked PR; no comments
- Symptom: Analytics/Home "Total tokens" looks like complete all-agent usage but mainly reflects Claude Code (and conditional OpenClaw/OpenCode); Codex/Cursor/etc. missing capture reads as zero usage.
- Requested fix: hover/focus/touch-accessible hint beside the label explaining counted categories, included/excluded/conditional agents; keep counting semantics; reusable for #321 Home counter.
- Next: resume-detection → workspace

## resume-detection
- Not already fixed (issue open, no merged PR).
- SPEC_NAME: 323-total-tokens-coverage-hint (orphan fix-as-spec; no owning functional-spec found for token-coverage UI copy).
- Next: workspace

## workspace
- BRANCH: fix/323-total-tokens-coverage-hint
- WT: /home/USER/code/llm-wiki/.claude/worktrees/fix-323-total-tokens-coverage-hint
- TMP_VAULT: <worktree>/.worktree-vault (absolute path in local config.json only)
- Next: diagnose

## diagnose
- Reproduction: Analytics `Tokens` label via `viz_tokens.render_site_token_stats`; footer note omits agent coverage; Codex/Cursor sessions contribute 0 because `compute_token_totals` only reads Claude-shaped `message.usage`.
- Root cause: missing coverage disclosure in `render_site_token_stats` (UI); underlying capture limited to Claude-shaped usage in `convert.compute_token_totals`.
- Fix shape: shared `render_token_coverage_hint` + constant in `viz_tokens.py`; CSS show on hover/focus-within/aria-expanded; small JS toggle for touch; wire Analytics now; Home deferred to #321 (helper reusable).
- Home: no Total tokens counter in current main.
- Next: classify

## classify
- Verdict: orphan UX gap — no pre-existing `functional-spec.md` for token-coverage UI copy.
- SPEC_NAME: 323-total-tokens-coverage-hint
- Action: fix code + regression test; skip amend-spec (no functional-spec to amend). Update maintainer surface docs / CHANGELOG as product docs, not AWOS functional-spec amendment.
- Next: fix

## fix
- Added `TOKEN_COVERAGE_LINES` + `render_token_coverage_hint(hint_id)` in `llmwiki/viz_tokens.py`; wired into the Analytics Tokens label in `render_site_token_stats` (counting semantics unchanged). Home counter deferred to #321 (helper is reusable via a distinct `hint_id`).
- CSS in `llmwiki/render/css.py` (`.token-coverage-*`: show on hover, focus-within, `aria-expanded="true"`; `data-dismissed` suppresses after Escape); JS in `llmwiki/render/js.py` (click toggle, Escape, outside click, viewport clamp).
- Docs: CHANGELOG Fixed entry; `docs/reference/ui.md` Analytics paragraph. No `docs/maintainers/surfaces/analytics.md` exists, so no surface doc added.
- Suggested test targets: coverage text contains each required agent/category phrase; helper emits `type="button"`, `aria-expanded="false"`, `aria-describedby` equal to panel `id`, `role="tooltip"`; distinct `hint_id` gives distinct ids and unsafe chars are sanitized; Tokens card contains the hint and the total/avg text is unchanged; CSS has the three reveal selectors; JS bundle contains `token-coverage-hint` and an Escape handler.
- Next: tests

## regression-test
- Delegating to testing-expert; suggested targets recorded by fix stage.
- Next: verify-criteria (after tests land)

## regression-test (done)
- Extended tests/test_viz_tokens.py + tests/test_build_analytics.py; RED confirmed when helper call removed; pytest green.

## verify-criteria
- AC hover/focus/touch access: markup has focusable button + role=tooltip; CSS reveals on :hover, :focus-within, [aria-expanded=true]; JS toggles aria-expanded on click and closes on Escape/outside (touch path). Headless Chromium unavailable in this environment (playwright browser binary missing; MCP headed needs X); no live browser interaction evidence.
- AC Codex/Cursor-only not implied zero: copy states missing usage excluded / not evidence of zero; not a complete all-agent total.
- AC total stays visible / counting unchanged: Tokens value + "/ session" + "with token data" still rendered; no change to compute_site_stats.
- AC light/dark + narrow: panel uses theme CSS vars; max-width min(300px, 100vw - 24px) + JS clamp present (visual clip check deferred to smoke confirm).
- AC adapter-aligned copy: TOKEN_COVERAGE_LINES single source; Home helper reusable, not wired (#321).
- Pytest regression suite green on worktree.
- Next: smoke-confirm with user, then local-review (amend-spec skipped).

## smoke-confirm
- Operator confirmed fix looks good.
- Next was local-review; also folding CONTRIBUTING cleanup into this PR per operator.

## amend-spec
- Skipped (orphan; no functional-spec).

## cleanup (operator request)
- Removed `.cursor/rules/no-local-vault-in-prs.mdc`; updated `.gitignore` allowlist, CONTRIBUTING agent map + Privacy §7 (chat paste blocks may use real paths); CHANGELOG Changed entry.
- Rationale: CONTRIBUTING is agent-neutral source of truth; Cursor-only alwaysApply duplicate caused over-redaction in smoke chat.
- Next: local-review

## local-review / B1
- Operator: address B1 properly — separate PR for Cursor-rule drop; restore CHANGELOG entry on that PR (file was tracked; earlier "no CHANGELOG" request based on wrong memory).
- #323 branch restored to Tokens-hint-only (mdc / gitignore / CONTRIBUTING cleanup reverted here).
- Chore lives on branch chore/drop-no-local-vault-cursor-rule.
- Remaining review nits N2–N5 still await keep/drop for #323.

## local-review keep/drop
- B1: kept — split; chore PR https://github.com/AlexanderMakarov/llm-wiki/pull/334
- N1: kept — applied on chore PR (contributing.mdc privacy enumeration)
- N2: kept — click-close sets data-dismissed
- N3: kept — panel positioned on .token-coverage-hint
- N4: kept — cascade + click-handler assertions
- N5: kept — stage flow-log at commit-push (not review.md)
- Next: commit-push #323
