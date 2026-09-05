---
name: release
argument-hint: "<version>"
description: Maintainer skill for cutting a tagged llmwiki release. Use when the user invokes /release, says "cut a release", "tag vX.Y.Z", "ship the next version", or asks to bump version + CHANGELOG and push a release tag. Walks preflight → bump → editorial → commit/tag → human gate → push → watch release.yml. Not part of the end-user install-agent-kit wiki pack.
---

# Release — scripted tagged cut

Cut a deliberate `vX.Y.Z` release for this repository. Available wherever `.claude/skills/release` is installed (Cursor and Claude Code read that tree; Codex and peers via skill install that mirrors it).

**Canonical checklist order** lives in `docs/maintainers/RELEASE_PROCESS.md`. Load that doc first; this skill is the operational walkthrough and must not contradict it. Pass `$ARGUMENTS` (or the version the human confirms) as `X.Y.Z` without a leading `v` in file bumps; tags use `vX.Y.Z`.

## Hard rules

- **No force-push** of `main` (or any shared branch) as part of a release.
- **No amend** of the release commit after the tag exists.
- **No unattended publish** — never `git push` of `main` or the version tag until the human explicitly approves in this session.

There is no `scripts/release-*.sh`; run the commands below with `gh`, `ruff`, `pytest`, `git`, and file edits.

## Scripted steps

### 1. Load the process doc

Read `docs/maintainers/RELEASE_PROCESS.md` end to end before changing anything.

### 2. Preflight

Confirm all of the following; stop and fix before bumping if any fail:

1. Default branch CI is green: `gh run list --branch main --limit 5` (recent runs succeeded).
2. No open critical bugs: `gh issue list --label priority:critical --state open` is empty.
3. Lint: `ruff check llmwiki tests scripts`.
4. Tests: `python3 -m pytest tests/ -q`.
5. **Root `wiki/` pitfall:** if a gitignored leftover `wiki/` exists at the repo root, warn the human — demo self-containment / acceptance checks can fail against it. Do **not** delete user data without asking; rename/move aside only with explicit approval.
6. Propose the version (`X.Y.Z`) and a one-line Theme; wait for the human to confirm or correct before editing files.

Optional when the release touches the static site: `python3 -m llmwiki build` and a quick local preview (no new unexpected warnings).

### 3. Version bump

Keep these in sync (tests enforce package ↔ pyproject):

- `llmwiki/__init__.py` → `__version__ = "X.Y.Z"`
- `pyproject.toml` → `version = "X.Y.Z"`
- `README.md` version badge — keep the current badge color/URL style (`Version-vX.Y.Z-…svg`)

Then: `python3 -m llmwiki --version` must print the new version. Update the README tests badge count only if you re-ran the full suite and the count changed.

### 4. Editorial — CHANGELOG and UPGRADING

Agent judgment; human can correct before the commit:

1. Promote everything under `## [Unreleased]` into a new `## [X.Y.Z] — YYYY-MM-DD` section (today’s date).
2. Add a one-line `Theme:` at the top of that section.
3. Leave an empty Unreleased scaffold above it (`### Added` / `### Changed` / `### Fixed` / `### Removed`).
4. Rename or compact `docs/UPGRADING.md` Unreleased / in-progress headings to the new version as needed.
5. Spot-check `#N` issue/PR references against merged work (`gh pr list --state merged --limit 30` or `gh issue view`).

**Changelog pitfall:** emptying Unreleased must not break acceptance tests that search shipping notes. `tests/changelog_notes.shipping_section_text` already scans Unreleased (when it still has bullets) **and** every versioned section — do not narrow that helper. Older feature bullets must remain discoverable under the new `## [X.Y.Z]` section (and prior versions).

### 5. Commit and tag locally

Stage the bump + editorial files (typically `__init__.py`, `pyproject.toml`, `README.md`, `CHANGELOG.md`, `docs/UPGRADING.md`, and any other files this cut intentionally includes). Commit with a conventional message, then tag:

```bash
git add llmwiki/__init__.py pyproject.toml README.md CHANGELOG.md docs/UPGRADING.md
git commit -m "release(vX.Y.Z): bump version + CHANGELOG"
git tag vX.Y.Z
```

Do not push yet.

### 6. Human gate (mandatory)

Stop. Show the human:

- `git show --stat HEAD` (or equivalent)
- Confirmed version and Theme
- Intended push: `git push origin main` and `git push origin vX.Y.Z` (or `git push origin main vX.Y.Z`)

Push **only** after explicit approval in the session. Direct push of the release commit to `main` is the maintainer path for this cut (distinct from normal PR flow) — still requires that approval.

### 7. Post-push — watch automation

1. Watch the tag workflow: `gh run list --workflow=release.yml --limit 3` (or `gh run watch` on the run for `vX.Y.Z`). `.github/workflows/release.yml` builds artifacts, signs with Sigstore, creates/updates the GitHub Release, and publishes to PyPI only when `vars.PYPI_PUBLISHING == 'true'`.
2. Report the public GitHub Release URL for this repo (or failure logs). Do **not** run `gh release create` as the happy path — automation owns that. Manual `gh release create` is fallback only if the workflow is broken.
3. Prerelease flag is automatic for tags whose name matches `rc` / `alpha` / `beta` / `dev`; stable `vX.Y.Z` tags are full releases.
4. Watch CI on the release commit SHA (`gh pr checks` is N/A for a direct `main` push — use `gh run list --branch main` / the commit’s Actions tab).
5. Note when PyPI was skipped because publishing is not enabled.

### 8. Optional follow-ups

Pages deploy and social announce are optional; follow `RELEASE_PROCESS.md` if the human wants them this cut.

## Rollback (after a bad tag is public)

Do not delete the tag. Cut a forward patch that reverts the bad change; mark the broken GitHub Release superseded. Never force-push `main` to rewrite history.
