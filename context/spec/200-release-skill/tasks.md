# Tasks: Cross-agent release skill (#209)

Spec: [`functional-spec.md`](./functional-spec.md) · [`technical-considerations.md`](./technical-considerations.md)

Worktree: `.claude/worktrees/feat-209-cross-agent-release-skill`. Drive `python3 -m llmwiki` from the worktree. Mutating vault commands use `$TMP_VAULT` (`.worktree-vault`) only.

Hired specialists: none required — **general-purpose** for implementation; **testing-expert** for the acceptance slice.

---

- [ ] **Slice 1: Canonical release skill + thin `/release` wrappers**

  > End state: `.claude/skills/release/SKILL.md` scripts the full cut; Claude and Cursor `/release` wrappers only load it; skill has no “don’t invoke from implement-feature” line.

  - [ ] Write `.claude/skills/release/SKILL.md` (`name: release`, description triggers `/release` / cut / tag, optional `argument-hint: "<version>"`). Numbered scripted steps: load `RELEASE_PROCESS.md` → preflight (`main` CI, critical bugs, ruff, pytest, root `wiki/` warning) → version bump files → CHANGELOG/UPGRADING editorial → commit+tag → **human gate before push** → watch `release.yml` + CI. Hard rules in skill: no force-push, no amend after tag, no unattended publish. Spec-only boundary for `/implement-feature` stays out of the skill body. **[Agent: general-purpose]**
  - [ ] Replace `.claude/commands/release.md` with a thin wrapper (Usage `/release <version>`; follow the skill + process doc; pass `$ARGUMENTS`). Add `.cursor/commands/release.md` with the same thin wrapper for Cursor slash discovery. **[Agent: general-purpose]**
  - [ ] Verify: skill file exists with frontmatter `name: release`; wrappers mention the skill path; wrappers do not say `git push origin master` or always `--prerelease`. **[Agent: general-purpose]**

- [ ] **Slice 2: Align RELEASE_PROCESS + maintainer / slash docs**

  > End state: process doc and maintainer pointers match `main` + `release.yml`; required one-liner points at the skill.

  - [ ] Rewrite `docs/maintainers/RELEASE_PROCESS.md`: default branch `main`; tag push → `release.yml` (GitHub Release + Sigstore; PyPI if enabled); prerelease only for rc/alpha/beta/dev tags; human approval before push; pitfalls (root `wiki/`, `shipping_section_text`); intro points at `.claude/skills/release/SKILL.md` and `/release`. Drop stale `master` / always-prerelease happy path. **[Agent: general-purpose]**
  - [ ] Update `docs/maintainers/README.md`, `docs/reference/slash-commands.md` (`/release` blurb), and `docs/reference/cli.md` contributor-only note if needed so they name the skill. **Required** maintainer pointer to the skill. **[Agent: general-purpose]**
  - [ ] CHANGELOG.md Unreleased: Added skill + wrappers; Changed process-doc alignment. **[Agent: general-purpose]**

- [ ] **Slice 3: Packaging / docs-currency tests**

  > End state: CI guards skill existence and no stale `push … master` happy path.

  - [ ] Add tests: `.claude/skills/release/SKILL.md` exists with `name: release`; `RELEASE_PROCESS.md` (and/or skill) mentions `main` and does not instruct `git push origin master` as the happy path; no “always `--prerelease` until 1.0” as the default path. Keep slash parity (`release` in governance lists — already present). **[Agent: testing-expert]**
  - [ ] Run new tests + `tests/test_slash_cli_parity.py` + `tests/test_reference_coverage.py` + `tests/test_skill_installer.py::test_real_skills_have_SKILL_md`; `ruff check` on touched Python. **[Agent: testing-expert]**

- [ ] **Slice 4: Feature Testing & Regression**

  > Verifies the whole feature against functional-spec.md after slices 1–3.

  - [ ] Read functional-spec.md acceptance criteria. Add or extend `@spec: 200-release-skill` acceptance coverage for FR1–FR5 (skill scripts cut; wrappers; docs match reality; pitfalls named; no implement-feature line required in skill). RED-then-green where practical. **[Agent: testing-expert]**
  - [ ] Full `python3 -m pytest tests/ -q` on the worktree (aside root `wiki/` if present); fix failures. **[Agent: testing-expert]**
