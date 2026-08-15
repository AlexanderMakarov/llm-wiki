---
title: "Deploying to GitLab Pages"
type: source
tags: [wiki-add, raw-doc, session-transcript, deploying-to-gitlab-pages, ci-cd-pipeline, pii-prevention, static-site-hosting]
date: 2026-08-10
source_file: 
project: deploying-to-gitlab-pages
model: 
last_updated: 2026-08-11
---
## Summary

This guide documents deploying an [[llmwiki]] site on [[GitLab Pages]], a free service with automatic builds on every push to the default branch. The CI pipeline includes a privacy-check stage that uses regex pattern matching to prevent accidental PII leaks, and requires no authentication secrets or CI variables for deployment.

## Key Claims

- [[GitLab Pages]] deployment is free and automatically triggered on every push to the default branch
- The `.gitlab-ci.yml` pipeline includes three stages: `build_site` (installs llmwiki and runs `llmwiki build`), `privacy_check` (prevents PII leaks using regex), and `pages` (deploys to GitLab Pages)
- GitLab Pages on private projects are accessible only to project members by default; public access requires explicit configuration in **Settings > Pages**
- No authentication credentials or CI secrets are required for GitLab Pages deployment (uses the built-in `pages` job)
- GitLab Pages supports private sites on the free tier, whereas GitHub Pages requires a paid plan for equivalent privacy features

## Key Quotes

> "The `privacy_check` stage runs the same pattern matching as the GitHub Actions workflow to prevent accidental PII leaks. Customize the regex patterns in the `grep -rE` line to match your setup."
— Highlights the consistent security approach across platforms and the ability to customize detection rules for different vaults

> "GitLab Pages deployment uses the built-in `pages` job which requires no authentication."
— Emphasizes the simplicity of setup without needing secrets management

## Connections

- [[GitLab Pages]] — the deployment platform and primary subject of this guide
- [[llmwiki]] — the static site generator being deployed

## Contradictions

None identified—this is new documentation.