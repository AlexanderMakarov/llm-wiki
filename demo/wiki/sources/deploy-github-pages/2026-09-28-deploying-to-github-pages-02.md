---
title: "Deploying to GitHub Pages (part 2/2: Differences from GitLab Pages)"
type: source
tags: [wiki-add, raw-doc, session-transcript, deploy-github-pages, platform-comparison, ci-configuration, deployment-setup, site-features]
date: 2026-09-28
source_file: 
project: deploy-github-pages
model: 
last_updated: 2026-09-28
---
## Summary

This documentation page (Part 2 of a GitHub Pages deployment guide) provides a side-by-side comparison of key configuration differences between [[GitHub Pages]] and [[GitLab Pages]]. It covers workflow files, output directory configuration, branch restriction methods, domain setup, HTTPS, and site privacy features—serving as a reference for developers choosing between or migrating between the two hosting platforms.

## Key Claims

1. [[GitHub Pages]] uses `.github/workflows/pages.yml` for CI/CD workflows, while [[GitLab Pages]] uses `.gitlab-ci.yml`
2. [[GitHub Pages]] requires GitHub Pro for private site hosting; [[GitLab Pages]] offers this feature on the free tier
3. [[GitHub Pages]] configures output directory via action settings, whereas [[GitLab Pages]] requires a fixed `public/` directory
4. Both platforms provide automatic HTTPS and custom domain support
5. [[GitHub Pages]] offers configurable branch restrictions; [[GitLab Pages]] manages this via `rules:` in CI configuration

## Key Quotes

> "See [gitlab-pages.md](gitlab-pages.md) for the GitLab equivalent. Key differences:" — indicates this document is part of a structured documentation hierarchy with cross-references to the [[GitLab Pages]] equivalent.

## Connections

- [[GitHub Pages]] (entity) — the primary platform documented
  - fact: Uses `.github/workflows/pages.yml` and allows configurable output directories
  - fact: Private site hosting requires GitHub Pro tier
- [[GitHub Actions]] (entity) — the workflow automation platform underlying GitHub Pages
  - fact: Deployment workflows are stored in `.github/workflows/pages.yml`
- [[GitLab Pages]] (entity) — the alternative platform featured in direct comparison
  - fact: Uses `.gitlab-ci.yml` and requires `public/` as fixed output directory
  - fact: Offers private site hosting on free tier
- [[Static Site]] (entity) — the deployment target for both platforms
  - fact: Both provide automatic HTTPS and custom domain support for static content

## Contradictions

None identified.