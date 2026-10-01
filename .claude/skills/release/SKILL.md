---
name: release
argument-hint: "<version>"
description: Use when a maintainer invokes /release or asks to cut, tag, or ship the next llmwiki version (vX.Y.Z) — including bumping the version and CHANGELOG for a release, or resuming a release cut that stopped part-way. Maintainer-only; not part of the end-user agent kit.
---

# Release — tagged cut

Cut a `vX.Y.Z` release of this repository. `vMAJOR.MINOR.PATCH` is the only tag format; `release.yml` and the GHCR workflow reject anything else, and there are no prerelease tags. `docs/maintainers/RELEASE_PROCESS.md` is the canonical checklist — read it first; this skill is the operational walkthrough and must not contradict it. Use `$ARGUMENTS` (or the confirmed version) as `X.Y.Z` in file bumps; tags are `vX.Y.Z`.

## Hard rules

- **No force-push** of `main`; **no amend** of the release commit after tagging.
- **No unattended publish:** never push `main` or the tag without the human's explicit approval in this session.
- **No tagging on incomplete demo synth.** Lint, build or CI green does not prove the demo refresh finished. "Proceed with delivery", "ship anyway" and "lint is green" do not waive it; only an explicit opt-out does (`skip demo refresh`, `version-only`, `ship with unfinished synth`). Incomplete → stop, report the gaps, wait.
- **No tagging without local demo review** when the refresh is on (#240): `release_demo_gate.py` exit 0, then the human's explicit OK on its `file://` site.

There is no script that bumps, tags or pushes. The demo has scripts; everything else is `gh`, `ruff`, `pytest`, `git` and file edits.

## Steps

### 1. Preflight

Stop and fix before bumping if any fail:

1. CI on `main` is green: `gh run list --branch main --limit 5`.
2. No open critical bugs: `gh issue list --label priority:critical --state open`.
3. `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q`.
4. Root `wiki/` pitfall: a gitignored leftover `wiki/` at the repo root breaks demo self-containment checks. Warn; move it aside only with approval — never delete it.

### 2. Demo refresh (#225) — default on

Refresh the public demo before the bump. Do not offer it as an open choice; skip only on an explicit opt-out in this session. The refresh is the **last content change before the cut**: merge every feature and docs PR first, since a later docs change re-stales the demo.

1. **Sessions** (no LLM): `python3 scripts/generate_demo_sessions.py --dry-run`, then a real run with `--today <release-day>`. It re-dates sessions in place, re-homes their source pages, and records the date in `demo/.demo-sessions-date`; the gate holds the rest of the cut to that date, even past midnight.
2. **Docs:** `python3 scripts/refresh_demo.py --dry-run`, then a real run when the plan is non-empty (`--force` when `demo/.demo-source-rev` is missing). See `docs/maintainers/REFRESH_DEMO.md`.
3. **Synth** the moved sessions and plan-added docs against `demo/` — the narrow path, never a full-vault re-synth. Do not spend synthesis tokens unless the human asked you to; otherwise stop after the dry runs and wait for them. Start long runs detached with a log outside the session scratchpad (`setsid nohup … > /tmp/<name>.log 2>&1 &`), and judge the synth's own exit code and the pages on disk, not a wrapper's. Do not run `pytest` while anything is writing `demo/`.
4. **Interrupted docs synth:** `python3 scripts/refresh_demo.py --resume` (needs `demo/.demo-refresh-pending`). Never re-run the refresh itself — its removes already ran.
5. **Completeness:** `python3 scripts/refresh_demo.py --verify-slugs <plan slugs>` exits 0. Only this cut's slugs count, not the historical docs backlog.
6. **Gate:** `python3 scripts/release_demo_gate.py` (`--dry-run` first). Non-zero is a hard stop. It checks freshness (docs changed since the pin, sessions without a source page), regenerates usage, builds, prints the `file://` URL, and runs the demo-content tests and strict lint. `--skip-usage` / `--allow-stale-demo` only after an explicit version-only opt-out.
7. **When the gate's tests or lint fail, fix the demo, not the test.** A search-baseline drop means two pages share a title or a stale page survived (#298); lint errors after the refresh's removes are references to removed pages (#277); stale candidate siblings need removal (#299). Re-record `tests/fixtures/demo_search_baseline.json` only once the change is explained. A privacy hit on a demo copy of a product doc means the product doc is wrong — fix it there, never allowlist the copy.
8. **Review:** show the `file://` URL and wait for the human's explicit OK (Home Timeline, Analytics MCP window, newest session dates, candidates). Gate exit 0 is not visual OK.
9. **Commit** `demo/` (sessions, wiki, `usage/`, `llmwiki-state.*`, `.demo-source-rev`, `.demo-sessions-date`) before the tag, so Pages builds the refreshed vault (#255). Run `synth --estimate` against `demo/` only if you discard its state write afterwards: it records every checked-out source as pending.

### 3. Propose version and Theme

Run `python3 scripts/release_contents.py` and send its output — Breaking first, then Added / Changed / Fixed / Removed, maintainer-only entries on one line, and what semver implies. Add the two concrete version choices (semver, and this repo's precedent: 2.1.0 shipped Breaking entries as a minor) and a one-line Theme. Wait for the human to pick and confirm before editing any file.

### 4. Version bump

Keep in sync (tests enforce package ↔ pyproject): `llmwiki/__init__.py` `__version__`, `pyproject.toml` `version`, and the `README.md` version badge (same style). `python3 -m llmwiki --version` must print the new version. Touch the tests badge only if the count changed.

### 5. CHANGELOG and UPGRADING

1. Promote `## [Unreleased]` into `## [X.Y.Z] — YYYY-MM-DD` (the actual release date) with a one-line `Theme:`.
2. Leave an empty Unreleased scaffold (`### Added` / `### Changed` / `### Fixed` / `### Removed`).
3. Rename `docs/UPGRADING.md` Unreleased headings to the new version.
4. Spot-check `#N` references against merged work.

Emptying Unreleased must not break acceptance tests that search shipping notes: `tests/changelog_notes.shipping_section_text` scans Unreleased and every versioned section — do not narrow it.

### 6. Commit and tag locally

```bash
git add llmwiki/__init__.py pyproject.toml README.md CHANGELOG.md docs/UPGRADING.md
git commit -m "release(vX.Y.Z): bump version + CHANGELOG"
git tag vX.Y.Z
```

Do not push yet.

### 7. Human gate (mandatory)

Show `git show --stat HEAD`, the confirmed version and Theme, and:

- **Demo synth status:** `complete` (plan slugs, `--verify-slugs` exit 0, session coverage), `explicitly opted out` (quote the phrase), or `blocked` (gaps — do not offer the push).
- **Demo local-review status:** `complete` (human OK'd the gate's site), `explicitly opted out`, or `blocked`.
- The intended push: `git push origin main vX.Y.Z`.

Push only on explicit approval. The direct push to `main` is the maintainer path; if the human prefers a PR for the release commit, open one and push only the tag after it merges — a PR touching `llmwiki/` or `tests/` also needs a `context/` note for the AWOS check.

### 8. After the push

1. Watch `release.yml` for the tag (`gh run list --workflow=release.yml --limit 3`): it builds, signs, creates the GitHub Release, and publishes to PyPI when `PYPI_PUBLISHING` is on. Report the GitHub Release URL. `gh release create` is a fallback only when the workflow is broken.
2. Watch CI on the release commit and `pages.yml` for the tag; its post-deploy assert checks `manifest.json` against `__version__`. Wait for every run to reach a terminal state — a silent watcher is not green.
3. Unless the demo refresh was opted out, spot-check the live demo's session dates.

## Rollback

Never delete a public tag or force-push `main`. Cut a forward patch that reverts the bad change and mark the broken GitHub Release superseded.
