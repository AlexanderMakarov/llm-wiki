# Tasks: Loop ready issue (herdr) (#296)

- [ ] **Slice 1: Queue math + work-for-today (no herdr)**
  - [ ] Add `scripts/loop_ready_issue_herdr.py` with stdlib argparse scaffold (`--label` required, `--poll-seconds` default 300, `--repo`, `--agent-kind`, `--once`, `--dry-run`) and pure helpers: `work_for_today_counts`, `candidates_assigned`, `eligible_after_blocked_by`, `sort_key`, `pick_next` per technical-considerations.md. No live network in helpers. **[Agent: general-purpose]**
  - [ ] Add `tests/test_loop_ready_issue_herdr.py` loading the script by path: counts; assignee+label filter; blockedBy applied only to candidates; sort (`important` then ascending number); `pick_next`. **[Agent: general-purpose]**
  - [ ] Verify: `python3 -m pytest tests/test_loop_ready_issue_herdr.py -q` and `ruff check scripts/loop_ready_issue_herdr.py tests/test_loop_ready_issue_herdr.py`. **[Agent: general-purpose]**

- [ ] **Slice 2: GitHub adapters (minimal calls) + dry-run CLI**
  - [ ] Implement gh adapters: viewer login; one labeled open-issue list; batched `blockedBy` GraphQL **only for assignee candidates**; merge+post-merge-CI status fetch for a single issue number; wire `--dry-run` to print work-for-today counts and the next eligible issue (or none) then exit 0. **[Agent: general-purpose]**
  - [ ] Add pure `advance_ready` helper + unit tests over fixture status shapes; monkeypatch subprocess for one dry-run selection test if cheap. **[Agent: general-purpose]**
  - [ ] Verify: pytest for this module + `python3 scripts/loop_ready_issue_herdr.py --help`; optional operator `--dry-run --label …` against real repo (not required for CI). **[Agent: general-purpose]**

- [ ] **Slice 3: herdr worker lifecycle + α wait loop**
  - [ ] Implement serial worker spawn (`tab create` → `agent start` → `agent prompt` with **inlined** skill text), event-driven `agent wait` / hold on `blocked`, GitHub α poll every `--poll-seconds`, retire worker on advance, empty-queue idle, Ctrl+C clean exit. Early worker disappearance: WARNING + restore instructions; do not advance as success. **[Agent: general-purpose]**
  - [ ] Add `.claude/skills/loop-ready-issue-herdr/SKILL.md` with `disable-model-invocation: true` and the one-ticket route contract (`bug` → `/fix-bug`, else `/implement-feature`; never advance queue). No `.claude/commands/` wrapper. **[Agent: general-purpose]**
  - [ ] Verify: unit tests still pass; dry-run path unchanged; document that live herdr smoke is manual. `ruff check scripts tests` for touched files. **[Agent: general-purpose]**

- [ ] **Slice 4: Maintainer docs + CHANGELOG**
  - [ ] Add `docs/maintainers/LOOP_READY_ISSUE_HERDR.md` (opt-in, herdr required, `--label` + assignee, α advance, poll default 300, hard-stop/restore, no custom notifier) and a row in `docs/maintainers/README.md`; `CHANGELOG.md` Unreleased entry; ensure no personal vault paths/usernames. **[Agent: general-purpose]**
  - [ ] Verify: markdown links resolve relative to the note; CHANGELOG under Unreleased; `ruff`/pytest still green for the feature tests. **[Agent: general-purpose]**

- [ ] **Slice 5: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic; mocked I/O where needed). No live herdr/GitHub mutation in CI. Annotate with `@spec: 303-loop-ready-issue-herdr` and `@regression` where suitable. **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
