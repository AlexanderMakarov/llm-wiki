---
title: "Deploying to GitHub Pages"
type: source
tags: [wiki-add, raw-doc, session-transcript, deploy-github-pages, deployment, github-actions, static-site, ci-cd, version-verification]
date: 2026-09-07
source_file: 
project: deploy-github-pages
model: 
last_updated: 2026-09-07
---
## Summary

This guide documents the deployment of [[llmwiki]]-generated [[Static Site]]s to [[GitHub Pages]] via [[GitHub Actions]]. The workflow is triggered by version tags (`v*.*.*`) or manual dispatch—not on every push—and includes a post-deploy verification step that fetches `manifest.json` from the live URL and fails if its version does not match the checked-out code's `__version__`. Coverage includes setup, custom domains, and troubleshooting.

## Key Claims

- Deployment is triggered only by version tags and manual workflow dispatch; automatic push-to-deploy is disabled by design (PR #69), keeping the demo synchronized with releases rather than every merge
- The workflow installs Python 3.12, the `markdown` dependency, runs `llmwiki build --vault demo --out ./site`, adds `.nojekyll` to the site root, and deploys via GitHub's built-in `actions/deploy-pages` action (no secrets required)
- A post-deployment verification step fetches `manifest.json` from the deployed URL and fails the run if its version does not match `__version__` from the checked-out commit, preventing stale or mislabeled builds
- The `.nojekyll` file is mandatory for GitHub Pages to serve paths with underscores correctly
- Custom domains require a CNAME DNS record and GitHub's automatic HTTPS provisioning via Let's Encrypt

## Key Quotes

> "Pages publishes on every version tag (`v*.*.*`) and on manual **Run workflow**. Deploy on every push to `main` stays off (#69) — the demo tracks releases, not merges"

This captures the deliberate separation of release deployments from merge activity, preventing version drift between the live demo and the source tree.

> "A green deploy job means GitHub accepted the artifact, not that the site serves it. So after `actions/deploy-pages`, the workflow checks out the commit it just published, fetches `manifest.json` from the deployed URL, and fails the run when the version there is not the `__version__` of that commit."

This describes the critical verification mechanism that gates publication and ensures label integrity.

## Connections

- [[GitHub Pages]] (service) — the static hosting platform  
  - fact: Configured via Settings > Pages to use GitHub Actions as source; deploys artifacts without requiring secrets or tokens
- [[GitHub Actions]] (platform) — CI/CD automation for building and publishing  
  - fact: The `pages.yml` workflow orchestrates Python installation, `llmwiki build`, artifact creation, and post-deploy verification
- [[llmwiki]] (tool) — the static site generator  
  - fact: Invoked as `llmwiki build --vault <path> --out ./site` to produce the deployable output
- [[Static Site]] (output) — HTML served by GitHub Pages  
  - fact: Requires `.nojekyll` file in root to enable correct serving of underscored paths

## Contradictions

None identified.