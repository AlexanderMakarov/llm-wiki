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
- [ ] **Demo corpus before the cut (#225) — default ON:** refresh locally and commit **before** tagging unless the human **explicitly** opts out this session (CI never regenerates `demo/`). Silence means refresh; do not treat “optional” as the default. Incomplete / rate-limited synth is a **hard stop** — lint/build green and “proceed with delivery” do not waive it; only an explicit opt-out (`skip demo refresh`, `version-only`, `ship with unfinished synth`) does.
  - Sessions (no LLM): `python3 scripts/generate_demo_sessions.py --dry-run`, then regenerate with a **release-day** `--today` (not the frozen `2026-08-10` anchor). A new `--today` changes filenames.
  - Re-synth: update wiki for changed session filenames and for any docs refresh plan — prefer session sources that moved plus path-scoped `synth --docs-only` / `refresh_demo.py`, not a blind full-vault re-synth of unchanged pages. When the human will run synth (token budget), stop after session regen + `refresh_demo.py --dry-run` and wait for them; do not spend synthesis tokens without that go-ahead.
  - Product docs drift: `python3 scripts/refresh_demo.py --dry-run`, then a real refresh when the plan is non-empty (needs a synthesis backend; see [REFRESH_DEMO.md](REFRESH_DEMO.md); use `--force` when `demo/.demo-source-rev` is missing). The script fails (and does not advance the pin) when plan-added raw docs still lack wiki pages.
  - Completeness (local): `python3 scripts/refresh_demo.py --verify-slugs <slug>,…` for every slug this cut’s plan added must exit 0; regenerated non-headless sessions need matching `demo/wiki/sources/` pages. Do not require clearing the historical vault-wide docs backlog.
  - Spot-check newest session dates under `demo/raw/sessions/` and that `demo/` builds clean: `python3 -m llmwiki lint --vault demo --fail-on-errors` and `python3 -m llmwiki build --vault demo --out /tmp/demo-site --local-root /home/user`, then commit `demo/raw/sessions/` + updated `demo/wiki/` (+ `.demo-source-rev` when written)
  - Human gate before push must state demo synth as `complete`, `explicitly opted out`, or `blocked` (do not present a tag push when blocked)

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
5. Runs a post-publish `smoke` job that installs `llm-wiki-plus==X.Y.Z` from real PyPI and asserts `llmwiki --version` matches the tag — it also fails the run outright when `publish` was skipped, so a gate-off tag can't pass quietly

Prerelease: the workflow passes `--prerelease` only when the tag name matches `rc` / `alpha` / `beta` / `dev`. Stable tags are full releases.

- [ ] Confirm the workflow: `gh run list --workflow=release.yml --limit=3` (watch the run for this tag)
- [ ] Open the GitHub Release for this repo and confirm title, notes, and assets
- [ ] Confirm the `smoke` job went green — it is the check that the tag actually reached users as `pip install llm-wiki-plus==X.Y.Z`. `PYPI_PUBLISHING` is enabled on this repo, so a **skipped** `publish` is no longer normal: it means releases were turned off and the tag shipped nothing to PyPI, which `smoke` now fails on rather than skipping alongside it (see `docs/deploy/pypi-publishing.md`)
- [ ] Watch CI on the release commit SHA on `main`

**Manual fallback** (only if `release.yml` is broken):

```bash
gh release create vX.Y.Z --title "vX.Y.Z" --generate-notes
# add --prerelease only for rc/alpha/beta/dev tags
```

## Verify Pages deploy (expected, not optional)

The same tag push that triggers `release.yml` also triggers [`.github/workflows/pages.yml`](../../.github/workflows/pages.yml) (#213). The demo site is part of what a release ships — treat a failed or missing Pages run the way you'd treat a failed PyPI upload, not as cosmetic. Skipping this check is how the live demo ended up four releases stale.

- [ ] Confirm the run exists and went green: `gh run list --workflow=pages.yml --limit=3`
- [ ] Confirm its post-deploy assert passed — the deploy job fetches `manifest.json` from the live URL and fails when the served version isn't the tagged `__version__`, so a green run means the site really serves this release
- [ ] Spot-check the live demo shows the new version **and**, unless demo refresh was explicitly skipped, that session dates match what you committed (version-only green is not a content refresh — #225)
- [ ] If the deploy failed, fix `main` first and re-run the workflow from **Actions → Deploy demo site to GitHub Pages → Run workflow**; do not hotfix by rewriting the tag

There is no separate scheduled freshness workflow — the post-deploy assert on `pages.yml` is the version gate. Session/docs corpus freshness is still a pre-tag maintainer step (#225; see pre-flight above and [docs/uptime.md](../uptime.md)).

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
| Shipping without regenerating demo sessions | Default is refresh; skip only on an explicit human opt-out (#225). Pages version assert does not rewrite session dates |
| Emptying Unreleased | Keep shipping bullets under the new version section; rely on `shipping_section_text` scanning versioned sections |
| Double-creating the GitHub Release | Trust `release.yml` after the tag push |
| Always marking prerelease | Only for rc/alpha/beta/dev tags — not every release past 1.0 |
| Pushing without approval | Human gate is mandatory; no unattended publish |
