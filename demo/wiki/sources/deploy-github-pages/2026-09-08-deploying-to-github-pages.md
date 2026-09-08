---
title: "Deploying to GitHub Pages"
type: source
tags: [wiki-add, raw-doc, session-transcript, deploy-github-pages, github-actions, static-site, release-deploy, manifest-verification, pages-workflow, manifest-version-check, demo-vault]
date: 2026-09-08
source_file: 
project: deploy-github-pages
model: 
last_updated: 2026-09-08
---
## Summary

The session documents how to host an llmwiki static site on GitHub Pages using the repo’s `.github/workflows/pages.yml`, which builds the committed `demo/` vault with `llmwiki build --vault demo --out ./site`, adds `.nojekyll`, and deploys via `actions/deploy-pages` without secrets. Publishing is gated on version tags (`v*.*.*`) or manual workflow dispatch (#213), not on every push to `main` (#69). After deploy, CI fetches `manifest.json` from the live URL and fails if its version does not match the checkout’s `llmwiki.__version__`, so a green deploy job is not treated as proof the public site updated.

## Key Claims

- GitHub Pages must use **Source: GitHub Actions** (not a branch) for `pages.yml` to publish the artifact.
- The default workflow builds only the committed `demo/` vault (`demo/raw/sessions/`, `demo/raw/docs/`, `demo/wiki/`, `demo/usage/`) so CI stays deterministic and does not run synthesis on every tag.
- `pages.yml` triggers on tags matching `v*.*.*` and on manual **Run workflow**; deploy-on-push to the default branch is intentionally disabled unless you restore a `push:` trigger.
- Post-deploy verification compares the live site’s `manifest.json` version to `__version__` from the built commit; tag push and manual dispatch use the same assertion, so a tag without a version bump can fail the check rather than silently mislabel the site.
- `scripts/check_live_version.py` mirrors that check locally (exit 0 match, 1 stale, 2 unreachable, 3 unparseable).

## Key Quotes

> "A green deploy job means GitHub accepted the artifact, not that the site serves it." — rationale for the manifest fetch after `actions/deploy-pages`

> "Deploy on every push to `main` stays off (#69) — the demo tracks releases, not merges" — explains why the public demo aligns with releases rather than every merge

> "`llmwiki build` stamps the manifest with the package version, which makes it the only field on a deployed site that identifies the build." — defines what the live version check is comparing

## Connections

- [[llmwiki]] (entity) — CLI `build` produces `site/` and stamps `manifest.json` with package `__version__`.
  - fact: Default Pages workflow runs `llmwiki build --vault demo --out ./site`.
- [[Static Site]] (concept) — output is static HTML under `site/`, deployed as a Pages artifact with `.nojekyll` for `_`-prefixed paths.
- [[GitHub Pages]] (entity) — free hosting at `https://<username>.github.io/<repo-name>/`; custom domain and HTTPS via Settings and optional `CNAME` in `site/`.
- [[GitHub Actions]] (entity) — `pages.yml` checkout, Python 3.12, `markdown` install, build, upload, and `deploy-pages`; tag and `workflow_dispatch` triggers.
- [[Observability]] (concept) — post-deploy manifest check and `check_live_version.py` as operational freshness gate (related doc: uptime).
