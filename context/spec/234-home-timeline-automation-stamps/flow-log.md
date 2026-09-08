# Flow log — #234 Home Timeline + automation stamps

## 2026-09-08 — fetch-ticket + resume-detection + workspace

- **Ticket:** [#234](https://github.com/AlexanderMakarov/llm-wiki/issues/234) — feat: Home Timeline + automation should make sync/synth/build timing unambiguous (OPEN, enhancement)
- **Done check:** issue open; no matching `context/spec/*234*`; no merged PR for this work (search hit #131 unrelated)
- **Workspace:** branch `feat/234-home-timeline-automation-stamps`; worktree `/home/USER/code/llm-wiki/.claude/worktrees/feat-234-home-timeline-automation-stamps`; throwaway vault `$WT/.worktree-vault`
- **Note:** primary checkout dirty (unrelated lint/cli/test edits) — work isolated in worktree
- **Next:** `/awos:spec` (functional-spec approval gate)

## 2026-09-08 — specs (functional-spec draft)

- **Product choices (revised):** lint surface = Home; **do not** revert build on lint-fail — keep newly built site + Last lint/error note; standalone lint refreshes lint on existing site; continue pipeline after stage failure unless `--fail-fast` (synth fail → still build); Ingest unchanged; shrink Automation panel (drop lint-fail reminder + Updated; merge hooks+watch, cost+backend)
- **Artifact:** `context/spec/234-home-timeline-automation-stamps/functional-spec.md` (Status: Draft) — awaiting user approval
- **Next:** user accepts functional-spec → `/awos:tech`

## 2026-09-08 — specs (functional approved → tech draft)

- **functional-spec.md:** Status → Approved
- **technical-considerations.md:** Draft written — ops stamps (`last_synth_at`, `last_build_at`, lint status/error); lint syncs `site/llmwiki-state.js`; no build revert; fail-fast docs/tests; Automation panel shrink
- **Next:** user accepts technical-considerations → `/awos:tasks`

## 2026-09-08 — tech draft revisions (pre-approval)

- **§2.2 clarified:** lint updates JSON state (+ existing JS data wrapper / copy into `site/`) only — **never** edits HTML
- **`last_lint_error`:** console-format multiline (+ ellipsis); Home shows up to ~6 lines
- **`--fail-fast`:** console-required; static-site issue surfacing optional/not required for early-abort automation
- **Next:** user accepts technical-considerations → `/awos:tasks`

## 2026-09-08 — tech + functional UX amendments (pre-approval)

- **Lint banner:** required above Pipeline state when `last_lint_error` non-empty (not optional)
- **Stage stamps:** Last sync/synth/build/lint live under **Pipeline state**; Automation = settings only
- **DRY:** mandatory shared helpers for stamps / sidecar copy / lint text — no parallel per-CLI copies
- **functional-spec.md** amended in place (still Approved) to match placement + banner + DRY
- **Next:** user accepts technical-considerations → `/awos:tasks`

## 2026-09-08 — tech approved + tasks

- **technical-considerations.md:** Status → Approved (user: lgtm)
- **tasks.md:** written — 4 impl slices + Feature Testing & Regression (`testing-expert`)
- **Next:** commit specs → `/awos:implement`

## 2026-09-08 — commit-specs

- **Commit:** `be4aed5` `docs: add spec for #234 Home pipeline stamps and lint banner` (rebased onto origin/main)
- **Branch:** `feat/234-home-timeline-automation-stamps`
- **Next:** `/awos:implement` Slice 1

## 2026-09-08 — smoke feedback UI tweak

- Automation: short Synth backend line; drop `(recommended)`; Watch on its own line
- Stage stamps moved into **Timeline**; lint-error note under **Candidates** table
- Specs/docs/CHANGELOG amended; live site rebuilt for re-check
- **Next:** user re-confirm smoke → local review

## 2026-09-08 — implement Slice 3 (Automation panel settings-only)

- **Code:** `render_automation_panel` — drop lint-fail reminder + Updated; merge cost/backend and hooks/watch; Maintain one-liner (site once after summarization); no stage stamps
- **Docs:** `docs/reference/cli.md`, `ui.md`, `state-persistence.md`, `UPGRADING.md`, `CHANGELOG.md` Unreleased
- **Tests:** `tests/test_automation_install.py` panel assertions
- **Next:** Slice 4 (continue / lint-fail keeps build acceptance)



## 2026-09-08 — local review
- **review.md:** session-only; Verdict Request changes; Blockers 1, Nits 3
- **Next:** user keep/drop

## 2026-09-08 — commit-push (pre-PR final)
- Applied local-review keep-all: B1 custom --out sidecar; N1 grammar; N2 spec alignment; N3 skip-preamble truncation
- Static gate: ruff + targeted #234 tests green
- **Next:** push + gh pr create; stop appending tracked flow-log after PR opens
