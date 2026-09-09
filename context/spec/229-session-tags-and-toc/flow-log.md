# Flow log — #229 session tags + TOC

## fetch-bug
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/229 (OPEN)
- Title: bug(ui/convert): Claude local-command tags leak into session pages; session TOC overlaps hero unlike Raw/Docs sidebars
- Scope override (operator): fix **both** bugs in **one PR** (issue suggested split; user chose combined)

## resume-detection
- Issue open; no merged PR for #229; no prior `context/spec/229-*`
- SPEC_NAME: `229-session-tags-and-toc`

## workspace
- BRANCH: `fix/229-session-tags-and-toc`
- WT: `.claude/worktrees/fix-229-session-tags-and-toc` (absolute under repo)
- TMP_VAULT: `$WT/.worktree-vault`
- Next: diagnose


## diagnose
- Bug1: `derive_description` + `render_user_prompt` in `llmwiki/convert.py` pass Claude control tags through; HTML escape makes them visible
- Bug2: `js.py` mounts `.toc-sidebar` on `body` with fixed `top:88px`; overlaps hero. Prefer Raw doctree sticky-in-grid below hero
- Spec ownership: none (fix-as-spec dir only)

## classify
- Verdict: **conformance** (orphan) — code violates issue acceptance; no pre-existing `functional-spec.md` to amend
- SPEC_NAME: `229-session-tags-and-toc`
- Next: fix

## fix
- Bug1: added `normalize_claude_control_content()` in `convert.py`; wired into `render_user_prompt` + `derive_description`; Conversation skips empty control-only turns; command envelopes collapse to `/name`
- Bug2: `render_session` wraps article in `.doctree-layout.session-toc-layout` with `[data-toc-mount]`; `js.py` fills that aside (not `body`); `css.py` sticky like `.doctree-sidebar`
- Docs: CHANGELOG Unreleased + UPGRADING Unreleased note (`sync --force` for already-converted sessions)
- Minimal tests appended to `tests/test_session_description.py`; layout hook in session render tests left for testing-expert to expand


## fix
- convert.py: `normalize_claude_control_content`; wired into prompt + description; skip empty control turns
- build/js/css: session TOC sticky-in-grid via `.session-toc-layout` + `[data-toc-mount]` (Raw pattern)
- Docs: CHANGELOG + UPGRADING; context flow-log

## regression-test
- Extended `tests/test_session_description.py`; added `tests/test_session_toc.py`
- 26 related tests green (description + toc); resume_cwd still green

## verify-criteria
- TMP_VAULT demo raw: `description: "install Zoom on my machine"`; Conversation shows `/clear` then real prompt; no control tags
- Built HTML: `.doctree-layout.session-toc-layout` + `[data-toc-mount]` under section after hero subtitle
- Awaiting operator smoke confirm
- Next: local-review after confirm


## verify-criteria (live vault Playwright)
- Rebuilt live site with worktree `python3 -m llmwiki build --vault <LIVE> --out <LIVE>/site` (756 sessions)
- Playwright (CLI screenshot + Chromium evaluate) on wide session + raw.html
- TOC: sticky `top:88`, parent `.session-toc-layout`, not `body`; `overlapsHero: false` — **PASS** (layout theme)
- Tag leak in live `description:` still present until `sync --force` (raw not re-converted) — expected without force sync
- Screenshots: `/tmp/pw-229/session-top.png`, `session-toc-sticky.png`, `raw-top.png`
- Operator also checking independently; awaiting smoke yes for local-review

## smoke-fix (TOC threshold/breakpoint + system-notification)
- Problem A: JS threshold `headings.length < 3` → `< 2`; CSS drop `min-width: 1340` gate; show `.toc-ready` by default, hide/collapse at `@media (max-width: 860px)` like Raw
- Problem B: extend `normalize_claude_control_content` for `[SYSTEM NOTIFICATION` + `<task-notification>` (omit notification-only turns; keep trailing prose)
- Docs: CHANGELOG + UPGRADING force-sync bullet extended
- Tests: `test_session_toc.py` + `test_session_description.py` regressions


## smoke-feedback (operator Playwright)
- Missing TOC: short pages used heading threshold `<3` + CSS gate `min-width:1340` (Raw collapses only at 860). Fixed: threshold `<2`, show TOC ≥861px like Raw.
- SYSTEM NOTIFICATION leak: convert now strips `[SYSTEM NOTIFICATION…]` + `<task-notification>`; re-synced llm-wiki Claude since 2026-09-08; rebuilt live site.
- User page a11fab: notification gone; Conversation empty (notification-only session) → 1 heading → no TOC (expected). Longer sessions show On this page at 1200px.

## smoke-fix (description dump + command-args + newlines)
- A) `derive_description` skipped injected `# Title`/`## Arguments` and `@path.md` dumps via `is_injected_command_dump`
- B) `normalize_claude_control_content` keeps non-empty `<command-args>` on slash label
- C) `preserve_prompt_newlines` in `render_user_prompt` → markdown hard breaks (`  \n`)
- Docs: CHANGELOG + UPGRADING re-sync note extended; tests in `test_session_description.py`


## smoke-confirm (operator)
- TOC + convert tag/notification/args/newlines accepted
- Hero `description:` placement: must be inside `.hero .container` (not sibling)
- Selection quality of description text → filed #246; hero subtitle restored pending that policy
- Next: local-review


## local-review
- Verdict: Comment; Blockers 0; Nits 3 — all accepted and applied (dead LABEL_RE removed; #36 cwd assertions restored; orphan-tag docstring + incomplete-open leave-alone test)
- review.md session-only (not staged)
- Next: commit-push

## commit-push
- Preparing conventional `fix:` commit referencing #229; description selection follow-up #246
- Last flow-log write before PR open

