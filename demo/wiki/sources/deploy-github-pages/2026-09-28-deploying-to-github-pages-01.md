---
title: "Deploying to GitHub Pages (part 1/2)"
type: source
tags: [wiki-add, raw-doc, session-transcript, deploy-github-pages, github-actions, deployment-verification, deterministic-builds]
date: 2026-09-28
source_file: 
project: deploy-github-pages
model: 
last_updated: 2026-09-28
---
## Summary

This documentation guides deploying [[llmwiki]] to [[GitHub Pages]] using a CI/CD workflow triggered by version tags or manual dispatch. The workflow builds from a committed `demo/` vault with pre-synthesized pages, ensuring deterministic and zero-cost CI. Critically, the deployment includes post-publish verification: the workflow fetches `manifest.json` from the live site and fails the entire run if the version doesn't match the commit's `__version__`, preventing stale publications from being marked successful.

## Key Claims

- The `pages.yml` workflow publishes only on version tags matching `v*.*.*` and manual dispatch, not on every push to main (deliberate design choice #69)
- Building from a committed `demo/` vault with pre-synthesized pages and state snapshot keeps CI deterministic and avoids "everything pending" backlog issues (#255)
- After `actions/deploy-pages` uploads the artifact, the workflow fetches `manifest.json` from the deployed URL and fails the run if the version doesn't match the commit's `__version__`
- The same version-check assertion applies equally to tag-based deploys and manual dispatch—both fail if `__version__` was never bumped
- The workflow requires no secrets or tokens, using GitHub's built-in `actions/deploy-pages` action with default credentials

## Key Quotes

> "Deploy on every push to `main` stays off (#69) — the demo tracks releases, not merges" — explains why deploys are gated to version tags rather than every merge

> "the workflow checks out the commit it just published, fetches `manifest.json` from the deployed URL, and fails the run when the version there is not the `__version__` of that commit" — describes the verification mechanism that prevents publishing stale sites

> "release/tag deploys are the gate" — the deployment strategy treats releases as the sole availability gate, with no separate scheduled freshness workflow

## Connections

- [[llmwiki]] (entity) — the system being deployed to Pages
  - fact: The `pages.yml` workflow runs `llmwiki build --vault demo --out ./site` to generate the deployable site
- [[GitHub Pages]] (entity) — the free hosting platform where the site is published
  - fact: The workflow uses `actions/deploy-pages` to upload and deploy the built artifact with no required secrets
- [[GitHub Actions]] (entity) — the CI/CD automation that builds and publishes on tag or manual dispatch
  - fact: `pages.yml` triggers on version tags (`v*.*.*`), manual workflow dispatch, and includes post-deploy verification via `check_live_version.py`
- [[Static Site]] (entity) — the generated website output served by Pages
  - fact: The workflow builds to `./site` and adds `.nojekyll` to enable `_`-prefixed paths
- [[Wiki Synthesis]] (concept) — the build process generating pages from source vault
  - fact: The workflow builds against the committed `demo/` vault containing pre-synthesized pages and state snapshot to keep CI deterministic

## Contradictions

None identified. The document aligns with existing [[GitHub Pages]] and [[GitHub Actions]] topic descriptions.