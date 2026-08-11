---
title: "Deploying to GitHub Pages"
slug: deploying-to-github-pages
project: deploying-to-github-pages
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/deploy/github-pages.md"
content_sha256: e276a2df37d7c3ac1555f8edc0b47d964d16ab4f7047b37f292901f161098084
---

# Deploying to GitHub Pages

Host your llmwiki site on GitHub Pages for free, with automatic builds on every push to master.

Live example (this fork): [alexandermakarov.github.io/llm-wiki](https://alexandermakarov.github.io/llm-wiki/) · upstream: [pratiyush.github.io/llm-wiki](https://pratiyush.github.io/llm-wiki/)

> **This fork (#69):** `pages.yml` is `workflow_dispatch`-only by default (restore `push:` if you want every merge to republish). The published site is built from the committed `demo/` vault: `demo/raw/sessions/` (demo sessions), `demo/raw/docs/` (product docs), `demo/wiki/` (pre-synthesized pages, committed so CI stays free/deterministic) and `demo/usage/` (MCP telemetry fixtures for Analytics).

## Prerequisites

- A GitHub repository (fork or clone of [Pratiyush/llm-wiki](https://github.com/Pratiyush/llm-wiki))
- Python 3.12+ (only needed locally for `llmwiki sync`)
- Some session data already synced (or the demo sessions under `demo/raw/sessions/`)

## Step 1: Fork or clone the repo

```bash
# Option A: fork on GitHub, then clone your fork
git clone https://github.com/<you>/llm-wiki.git

# Option B: clone directly
git clone https://github.com/Pratiyush/llm-wiki.git
```

## Step 2: Enable GitHub Pages

1. Go to your repo on GitHub
2. Navigate to **Settings > Pages**
3. Under **Source**, select **GitHub Actions**
4. Save

This tells GitHub to use the workflow file rather than serving from a branch directly.

## Step 3: The workflow handles everything

The repo ships with `.github/workflows/pages.yml` which:

1. Checks out the code
2. Installs Python 3.12 and the `markdown` dependency
3. Runs `llmwiki build --vault demo --out ./site` against the committed `demo/` vault
4. Adds `.nojekyll` so Pages serves `_`-prefixed paths
5. Uploads and deploys the artifact

No secrets or tokens are required. The workflow uses GitHub's built-in `actions/deploy-pages`.

## Step 4: Publish

With auto-push disabled on this fork, run **Actions → Deploy demo site to GitHub Pages → Run workflow** (or restore the `push:` trigger in `pages.yml`). After a successful run, the site is live at:

```
https://<username>.github.io/<repo-name>/
```

## Using your own session data

By default the workflow builds the committed `demo/` vault. To deploy your real sessions:

1. Point the build at your own vault — change `--vault demo` in `pages.yml` to the path you sync into
2. Commit that vault's `raw/sessions/` and `wiki/` (remove them from `.gitignore` first)
3. Push to master

Alternatively, keep sessions local and commit only the built `site/` directory.

## Custom domain

1. Go to **Settings > Pages > Custom domain**
2. Enter your domain (e.g. `wiki.example.com`)
3. Add a CNAME DNS record pointing to `<username>.github.io`
4. GitHub provisions HTTPS automatically via Let's Encrypt
5. Optionally add a `CNAME` file in `site/` (the workflow will deploy it)

## Troubleshooting

### 404 after deploy

- Confirm Pages source is set to **GitHub Actions** (not a branch)
- Check that the workflow completed successfully in the **Actions** tab
- Wait 2-5 minutes after the first deploy for DNS propagation

### Build fails with "no sources found"

The workflow needs session data. Make sure either:
- `demo/raw/sessions/` contains `.md` files, or
- `raw/sessions/` is committed with real data

### Build fails with import error

The workflow installs `markdown` via pip. If you have added dependencies, update the `Install deps` step in the workflow:

```yaml
- name: Install deps
  run: python -m pip install markdown
```

### Workflow not triggering

- On this fork, automatic push deploy is disabled until Pages is configured (#69). Use **Actions → Deploy demo site to GitHub Pages → Run workflow** for a manual run after enabling Pages, then restore the `push:` trigger in `pages.yml`.
- When the `push:` trigger is restored, it fires on `master` and `main` — check your default branch name.

### Assets or CSS missing

Ensure `.nojekyll` exists in the site root. The workflow creates it automatically, but if you are deploying from a branch instead, add it manually.

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
