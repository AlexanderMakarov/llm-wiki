---
title: "Deploying to GitHub Pages (part 2/2: Differences from GitLab Pages)"
slug: deploying-to-github-pages-02
project: deploy-github-pages
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/deploy/github-pages.md"
content_sha256: ba4b0b76097efabb53cd3c80a3ffa5603c7e53b369594976fea73554950f0b97
---

> Part 2 of 2 of **Deploying to GitHub Pages** — Differences from GitLab Pages.

## Differences from GitLab Pages

See [gitlab-pages.md](gitlab-pages.md) for the GitLab equivalent. Key differences:

| Feature | GitHub Pages | GitLab Pages |
|---|---|---|
| Workflow file | `.github/workflows/pages.yml` | `.gitlab-ci.yml` |
| Output directory | Configured via action | Must be `public/` |
| Branch restriction | Configurable | Uses `rules:` in CI |
| Custom domain | Settings > Pages | Settings > Pages > New Domain |
| HTTPS | Automatic | Automatic |
| Private site | GitHub Pro required | Available on free tier |
