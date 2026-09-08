# Deploying to GitHub Pages

Host your llmwiki site on GitHub Pages for free, with automatic builds on every push to master.

Live example: [alexandermakarov.github.io/llm-wiki](https://alexandermakarov.github.io/llm-wiki/) (historical demo also at [pratiyush.github.io/llm-wiki](https://pratiyush.github.io/llm-wiki/)).

> **This repository (#213):** `pages.yml` publishes on every version tag (`v*.*.*`) and on manual **Run workflow**. Deploy on every push to `main` stays off (#69) — the demo tracks releases, not merges; restore `push:` if you want each merge to republish. The published site is built from the committed `demo/` vault: `demo/raw/sessions/` (demo sessions), `demo/raw/docs/` (product docs), `demo/wiki/` (pre-synthesized pages, committed so CI stays free/deterministic) and `demo/usage/` (MCP telemetry fixtures for Analytics).

## Prerequisites

- A GitHub repository (clone or fork of [AlexanderMakarov/llm-wiki](https://github.com/AlexanderMakarov/llm-wiki))
- Python 3.12+ (only needed locally for `llmwiki sync`)
- Some session data already synced (or the demo sessions under `demo/raw/sessions/`)

## Step 1: Fork or clone the repo

```bash
# Option A: fork on GitHub, then clone your fork
git clone https://github.com/<you>/llm-wiki.git

# Option B: clone this repository
git clone https://github.com/AlexanderMakarov/llm-wiki.git
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

Two ways to publish, and both end in the same assertion:

- **Push a version tag.** `git push origin v2.2.0` runs `pages.yml` alongside `release.yml`, so the live demo moves with the release instead of drifting behind it (#213).
- **Run it by hand.** **Actions → Deploy demo site to GitHub Pages → Run workflow** — for republishing after a demo-vault change, or the first deploy once Pages is enabled.

After a successful run, the site is live at:

```
https://<username>.github.io/<repo-name>/
```

### The deploy verifies itself

A green deploy job means GitHub accepted the artifact, not that the site serves it. So after `actions/deploy-pages`, the workflow checks out the commit it just published, fetches `manifest.json` from the deployed URL, and fails the run when the version there is not the `__version__` of that commit. `llmwiki build` stamps the manifest with the package version, which makes it the only field on a deployed site that identifies the build.

Both triggers assert against the checked-out `__version__` rather than the tag name, so a manual dispatch is checked exactly as strictly as a tag push — and a tag whose `__version__` was never bumped fails here rather than publishing a mislabelled site.

Run the same check by hand against any deployed site:

```bash
python3 scripts/check_live_version.py --url https://<username>.github.io/<repo-name>/
```

It exits 0 on a match, 1 when the site is stale, 2 when the manifest is unreachable, and 3 when it cannot be parsed. The same check runs automatically after every Pages deploy; there is no separate scheduled freshness workflow — release/tag deploys are the gate (see [uptime.md](../uptime.md)).

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

- `pages.yml` fires on version tags matching `v*.*.*` and on manual dispatch. A tag like `v2.2` or `release-2.2.0` matches neither — check the tag shape first.
- Deploy on push to the default branch is deliberately off (#69). Add a `push:` trigger to `pages.yml` if you want every merge to republish; it fires on `master` and `main`, so check your default branch name.
- Pages must be enabled with **Source: GitHub Actions** before any run can deploy.

### Deploy succeeded but the site is stale

The post-deploy check fails with `serves version X, expected Y`. The artifact was published but the URL still serves an older build:

- Give it a minute — the check already retries, but a CDN edge can lag further. Re-run the job before digging.
- Confirm the run you are looking at actually deployed: a cancelled or skipped `deploy` job leaves the previous site up while the tag looks handled.
- Check that `__version__` in `llmwiki/__init__.py` matches the tag. A tag pushed without the version bump publishes a site labelled with the old version, and this is the check that says so.

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
