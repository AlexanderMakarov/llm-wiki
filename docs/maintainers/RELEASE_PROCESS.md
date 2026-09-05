# Release process

> **Audience:** whoever is cutting the next tag.
>
> **How to run the cut:** load the cross-agent skill [`.claude/skills/release/SKILL.md`](../../.claude/skills/release/SKILL.md) (Claude Code / Cursor: `/release <version>`). Wrappers live at `.claude/commands/release.md` and `.cursor/commands/release.md`. This document is the canonical checklist order; the skill is the operational walkthrough and must stay aligned with it.

llmwiki uses [semantic versioning](https://semver.org/). Past `1.0` / `2.x`, a normal `vX.Y.Z` tag is a full GitHub Release. Tags whose names contain `rc`, `alpha`, `beta`, or `dev` are marked prerelease by automation.

Minor bumps (`X.Y.0`) ship when a coherent feature batch lands. Patch bumps (`X.Y.Z`) ship when a fix cannot wait for the next minor.

## Pre-flight

- [ ] `main` is green — recent CI on `main` passed (`gh run list --branch main --limit 5`)
- [ ] `ruff check llmwiki tests scripts`
- [ ] `python3 -m pytest tests/ -q` on a clean checkout (local pass beats CI-only pass)
- [ ] No open `priority:critical` bugs (`gh issue list --label priority:critical --state open`)
- [ ] If a leftover gitignored `wiki/` exists at the repo root, warn / move it aside before relying on demo self-containment checks — do not delete user data without asking
- [ ] Optional when the site changed: `python3 -m llmwiki build` and a quick local click-through for new warnings or broken nav

## Bump version

The package version in `llmwiki/__init__.py` and `pyproject.toml` must match (`test_pyproject_version_matches_package`).

- [ ] Update `__version__ = "X.Y.Z"` in `llmwiki/__init__.py`
- [ ] Update `version = "X.Y.Z"` in `pyproject.toml`
- [ ] Update the version badge in `README.md` (keep current badge color/URL style)
- [ ] Update the tests badge in `README.md` only if the passing count changed
- [ ] Run `python3 -m llmwiki --version` and confirm it prints the new version
- [ ] Confirm version + Theme with the human before committing

## Update CHANGELOG and UPGRADING

- [ ] Move every entry from `## [Unreleased]` into a new `## [X.Y.Z] — YYYY-MM-DD` section
- [ ] Re-create an empty `## [Unreleased]` scaffold above the new section
- [ ] Group entries by `### Added` / `### Changed` / `### Fixed` / `### Removed`
- [ ] Add a one-line Theme at the top of the release section
- [ ] Rename/compact `docs/UPGRADING.md` headings that still say Unreleased / in-progress for this cut
- [ ] Spot-check every `#N` against merged PRs/issues
- [ ] Remember `tests/changelog_notes.shipping_section_text` — acceptance tests search Unreleased (when non-empty) **and** all versioned sections; emptying Unreleased is fine as long as shipping bullets remain under the new version section. Do not narrow that helper.

## Commit + tag (local only)

```bash
git add llmwiki/__init__.py pyproject.toml README.md CHANGELOG.md docs/UPGRADING.md
git commit -m "release(vX.Y.Z): bump version + CHANGELOG"
git tag vX.Y.Z
```

- [ ] Do **not** push yet — human gate next
- [ ] Do **not** force-push `main`
- [ ] Do **not** amend the release commit after tagging

## Human gate, then push

Direct push of the release commit to `main` is the maintainer path for a cut (distinct from normal PR flow). Still requires an explicit OK in the session.

- [ ] Show `git show` / version / Theme; wait for explicit approval
- [ ] Only then: `git push origin main` and `git push origin vX.Y.Z` (or both in one push)

## GitHub Release + PyPI (automation)

Pushing the `v*.*.*` tag triggers [`.github/workflows/release.yml`](../../.github/workflows/release.yml), which:

1. Builds sdist + wheel
2. Signs artifacts with Sigstore
3. Creates (or updates) the GitHub Release with notes + artifacts — **this is the happy path**; do not run a second `gh release create` unless automation is broken
4. Publishes to PyPI via OIDC **only when** repository variable `PYPI_PUBLISHING` is `true` (otherwise the publish job is skipped; the GitHub Release still ships)

Prerelease: the workflow passes `--prerelease` only when the tag name matches `rc` / `alpha` / `beta` / `dev`. Stable tags are full releases.

- [ ] Confirm the workflow: `gh run list --workflow=release.yml --limit=3` (watch the run for this tag)
- [ ] Open the GitHub Release for this repo and confirm title, notes, and assets
- [ ] If PyPI was expected, confirm `pip install llm-notebook==X.Y.Z`; if skipped, that is normal until publishing is enabled (see `docs/deploy/pypi-publishing.md`)
- [ ] Watch CI on the release commit SHA on `main`

**Manual fallback** (only if `release.yml` is broken):

```bash
gh release create vX.Y.Z --title "vX.Y.Z" --generate-notes
# add --prerelease only for rc/alpha/beta/dev tags
```

## Verify Pages deploy (optional)

- [ ] If Pages is configured to deploy for this push/tag, watch `.github/workflows/pages.yml` and confirm the demo site shows the new version badge
- [ ] If the deploy failed, fix `main` first; do not hotfix by rewriting the tag

## Announce (optional)

- [ ] Post with a link to the GitHub Release page
- [ ] Pin an issue-digest discussion for milestone releases when useful

## Rollback

If a release is broken, do not delete the tag. Do:

1. Cut a patch release (`vX.Y.Z+1`) that reverts the bad change
2. Mark the broken release superseded in the GitHub Release notes (use Pre-release only when appropriate)
3. Never delete tags — downstream packages may pin to them
4. Never force-push `main` to rewrite the cut

## Pitfalls (from recent cuts)

| Pitfall | What to do |
|---|---|
| Leftover root `wiki/` | Warn / move aside with approval; breaks demo self-containment style checks |
| Emptying Unreleased | Keep shipping bullets under the new version section; rely on `shipping_section_text` scanning versioned sections |
| Double-creating the GitHub Release | Trust `release.yml` after the tag push |
| Always marking prerelease | Only for rc/alpha/beta/dev tags — not every release past 1.0 |
| Pushing without approval | Human gate is mandatory; no unattended publish |
