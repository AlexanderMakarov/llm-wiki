---
title: "PyPI publishing — one-time setup"
slug: pypi-publishing-one-time-setup
project: deploy-pypi-publishing
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-07
source: "docs/deploy/pypi-publishing.md"
content_sha256: 062d38b5652e736fb9079a3565bc6a4571690877c80e3deb377b1824b594a7dc
---

# PyPI publishing — one-time setup

> Status: the Actions workflow (`/.github/workflows/release.yml`) is ready.
> This document is the checklist for **one-time PyPI configuration** that
> unblocks `pip install llm-wiki-plus` (#101, #210).

## How the pipeline works

Every time a version tag (`v*.*.*`) is pushed:

1. **`build`** — builds sdist + wheel with `python -m build` on Python 3.12.
2. **`publish`** — uploads to PyPI via OIDC trusted publisher. **Gated on
   `vars.PYPI_PUBLISHING == 'true'`**. That gate is an escape hatch for a
   fork with no trusted publisher, not a normal state here: the variable is
   set on this repo, so a skipped `publish` means someone turned releases off.
3. **`smoke`** — installs `llm-wiki-plus==<tag>` from real PyPI into a clean
   venv and asserts `llmwiki --version` reports that version. It runs even
   when `publish` was skipped, and its first step fails the run whenever
   `publish` didn't succeed — so a tag that publishes nothing (gate off) and
   a tag that publishes something uninstallable both turn the whole run red
   instead of passing quietly (#210). No `continue-on-error`.
4. **`sign`** — signs artifacts with Sigstore (`gh-action-sigstore-python`).
5. **`github-release`** — creates (or updates) the matching GitHub Release
   with `--generate-notes`, attaches all artifacts + signatures. Runs even
   if publish/sign fail so Releases always keep tracking tags.

## Why the distribution is called `llm-wiki-plus`

The package is uploaded as **`llm-wiki-plus`**. Two names were tried first and are unavailable:

| Candidate | Why it doesn't work |
|---|---|
| `llmwiki` | Registered on PyPI by another author (Hosuke). |
| `llm-wiki` | Rejected by PyPI's [name-similarity rule](https://peps.python.org/pep-0503/#normalized-names) — it normalises to the same string as `llmwiki`. |

Only the *distribution* name carries the suffix. The CLI command, the Python import (`import llmwiki`), and the GitHub repo (`AlexanderMakarov/llm-wiki`) are all unchanged — the same split as `pillow` → `import PIL`.

Earlier revisions of this document named `llm-notebook` as the distribution. That name was never published for this fork; treat any surviving `llm-notebook` reference in frozen CHANGELOG or release-note history as pointing at the upstream project, not at something you can install today.

## One-time setup (do this once, on pypi.org)

### 1. Reserve the project name on PyPI

1. Log in to [pypi.org](https://pypi.org) (create an account if you
   haven't yet — GitHub sign-in works).
2. Reserve **`llm-wiki-plus`**. PyPI lets you create a project directly via
   the pending-publisher flow below — no upload needed.

### 2. Add the GitHub repo as a trusted publisher

Inside the PyPI **"Your account → Publishing"** page (or the project's
own Publishing tab once it exists):

**Add a new pending publisher → GitHub**

| Field | Value |
|---|---|
| PyPI Project Name | `llm-wiki-plus` |
| Owner | `AlexanderMakarov` |
| Repository name | `llm-wiki` |
| Workflow name | `release.yml` |
| Environment name | `release` |

Save. This binds the GitHub OIDC identity to PyPI so the workflow can
upload without a long-lived API token.

### 3. Create the `release` GitHub environment

1. **[Repository settings → Environments → New environment](https://github.com/AlexanderMakarov/llm-wiki/settings/environments)**
2. Name: **`release`**
3. Optional protection rules:
   - **Required reviewers** — add your own handle so every PyPI upload
     requires an explicit click.
   - **Wait timer** — 5 minutes gives you time to abort a mis-tagged release.
   - **Deployment branches** — limit to `main` so only main-tagged
     releases can trigger the upload.

### 4. Flip the publishing gate on

```bash
gh variable set PYPI_PUBLISHING --body "true" --repo AlexanderMakarov/llm-wiki
# Verify
gh variable list --repo AlexanderMakarov/llm-wiki | grep PYPI_PUBLISHING
```

### 5. Cut a real release tag

```bash
# Make sure you are on main with everything merged
git checkout main && git pull

# Bump version if needed, update CHANGELOG, commit...

# Create a signed tag
git tag -s v2.1.1 -m "v2.1.1 release"
git push origin v2.1.1
```

Watch the workflow at:
<https://github.com/AlexanderMakarov/llm-wiki/actions/workflows/release.yml>

The `publish` job should run and show `uploading` + `success`, and `smoke`
should go green right after it.

### 6. Verify from a clean machine

The `smoke` job already does this on every tag; run it by hand when you want
to check a release that predates the job.

```bash
python3 -m venv /tmp/pypi-smoke && source /tmp/pypi-smoke/bin/activate
pip install llm-wiki-plus
llmwiki --version    # should match the tag
llmwiki adapters     # should list Claude Code, Codex, Cursor, Gemini, …
deactivate
```

## Troubleshooting

**`publish` skipped** — `PYPI_PUBLISHING` variable not set, or set to
something other than `"true"`. Fix:
`gh variable set PYPI_PUBLISHING --body "true"`.

**`publish` fails with "invalid-publisher"** — the OIDC binding on
pypi.org doesn't match what GitHub sent. Double-check: owner =
`AlexanderMakarov`, repo = `llm-wiki`, workflow = `release.yml`, environment
= `release`. Casing matters.

**`publish` fails with "403 Forbidden: User ... isn't allowed to upload
to project ..."** — the PyPI project exists but the trusted publisher
hasn't been added yet (or was added under a different project name).
Re-check step 2.

**`publish` fails with "The name ... is too similar to an existing
project"** — PyPI normalises `llm-wiki` and `llmwiki` to the same name, and
`llmwiki` is taken. Publish as `llm-wiki-plus`; don't retry the shorter names.

**`smoke` fails to install** — the tag published nothing, or published a
different version than the tag names. Check the `publish` job's log, then
`pip index versions llm-wiki-plus` to see what actually landed.

**`smoke` reports the wrong version** — `pyproject.toml` `version` and
`llmwiki/__init__.py` `__version__` disagree with the tag. Bump both, re-tag.

**Artifacts rejected for metadata** — check that `pyproject.toml`'s
`name`, `version`, and `description` are all present; `python -m build`
locally + `twine check dist/*` surface issues before a tag push.

**Second upload of the same version** — PyPI refuses to overwrite a
version. Bump to the next patch (`v2.1.2`), update the changelog, re-tag.

## Related

- `#101` — original publishing issue
- `#210` — distribution rename to `llm-wiki-plus` + post-publish smoke
- `.github/workflows/release.yml` — the pipeline
- `docs/deploy/homebrew-setup.md` — sibling doc for the Homebrew tap (#102)
