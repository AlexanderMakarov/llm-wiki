# Deploying to GitHub Pages

Host your llmwiki site on GitHub Pages for free, with automatic builds on every push to master.

Live example: [pratiyush.github.io/llm-wiki/](https://pratiyush.github.io/llm-wiki/)

## Prerequisites

- A GitHub repository (fork or clone of [Pratiyush/llm-wiki](https://github.com/Pratiyush/llm-wiki))
- Python 3.12+ (only needed locally for `llmwiki sync`)
- Some session data already synced (or demo sessions under `examples/demo-sessions/`)

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
3. Runs `llmwiki init` to scaffold directories
4. Seeds demo sessions from `examples/demo-sessions/` (or `tests/fixtures/demo/`)
5. Runs `llmwiki build --out ./site`
6. Creates a `.nojekyll` file (prevents Jekyll processing)
7. Uploads `site/` as a Pages artifact
8. Deploys to GitHub Pages

No secrets or tokens are required. The workflow uses GitHub's built-in `actions/deploy-pages@v4`.

## Step 4: Push to master

```bash
git push origin master
```

The workflow triggers on pushes to `master` or `main`, on version tags (`v*`), and on manual `workflow_dispatch`. After a successful run, your site is live at:

```
https://<username>.github.io/<repo-name>/
```

## Using your own session data

By default the workflow builds from demo sessions. To deploy your real sessions:

1. Run `llmwiki sync` locally to populate `raw/sessions/`
2. Commit the `raw/sessions/` directory (remove it from `.gitignore` first)
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
- `examples/demo-sessions/` contains `.md` files, or
- `raw/sessions/` is committed with real data

### Build fails with import error

The workflow installs `markdown` via pip. If you have added dependencies, update the `Install deps` step in the workflow:

```yaml
- name: Install deps
  run: python -m pip install markdown
```

### Workflow not triggering

- The workflow triggers on pushes to `master` and `main`. Check your default branch name.
- For manual runs, go to **Actions > Deploy demo site to GitHub Pages > Run workflow**.

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
