---
title: "Deploying to GitHub Pages"
type: source
tags: [wiki-add, raw-doc, session-transcript, deploying-to-github-pages, github-actions, vault-publishing, static-site-generation]
date: 2026-08-10
source_file: 
project: deploying-to-github-pages
model: 
last_updated: 2026-08-11
---
## Summary

A guide for deploying an [[llmwiki]] site to [[GitHub Pages]] using [[GitHub Actions]]. Covers the 4-step setup process (fork/clone, enable Pages in settings, configure the workflow, publish), the workflow's architecture (building from a committed `demo/` vault containing raw sessions and pre-synthesized wiki pages), and options for using custom session data or custom domains with automatic HTTPS provisioning.

## Key Claims

- llmwiki sites can be hosted on GitHub Pages for free with automatic builds on every push to `master`
- The workflow requires no secrets or tokens; it uses GitHub's built-in `actions/deploy-pages` action
- The workflow automatically adds `.nojekyll` to the site root to allow serving `_`-prefixed paths correctly
- The deployed site is built from a committed `demo/` vault (not generated on-the-fly), keeping CI free and deterministic
- Users can deploy their own session data by changing the `--vault` parameter in `pages.yml` and committing their vault's `raw/sessions/` and `wiki/` directories
- Custom domains configured via Settings automatically receive HTTPS certificates via Let's Encrypt
- On the fork, `pages.yml` is set to `workflow_dispatch`-only by default; the `push:` trigger must be restored to enable automatic builds on merge

## Key Quotes

> "Host your llmwiki site on GitHub Pages for free, with automatic builds on every push to master." — The core value proposition

> "No secrets or tokens are required. The workflow uses GitHub's built-in `actions/deploy-pages`." — Highlights the simplicity and security model

> "The published site is built from the committed `demo/` vault" — Explains the key architectural decision to pre-build and commit vault contents rather than generating on deploy

## Connections

- [[GitHub Pages]] — the hosting platform
- [[GitHub Actions]] — the CI/CD system orchestrating builds and deployment
- [[llmwiki]] — the tool and site generator being deployed