# The llmwiki demo vault

A self-contained vault that ships with the repository. It is the corpus behind the published GitHub Pages site, and it is the only vault any workflow in this repo is allowed to build.

```
demo/
  raw/sessions/   Synthetic session transcripts (no personal data).
  raw/docs/       Product documents about llmwiki itself.
  wiki/           The knowledge layer: index, overview, sources, entities, concepts, projects.
  usage/          Fixture MCP telemetry so the Analytics widgets have something to render.
  site/           Build output. Never committed — see .gitignore.
```

## Build it

```bash
python3 -m llmwiki build --vault demo --out demo/site --local-root /home/user
```

Open `demo/site/index.html` in a browser. Nothing has to be running.

CI publishes the same tree via `.github/workflows/pages.yml`, which runs `llmwiki build --vault demo --out ./site --local-root /home/user` and uploads the result to GitHub Pages. Nothing is seeded or copied: everything the build needs is committed here.

## Refresh from product docs

When `docs/` (not `docs/maintainers/`) changes, regenerate this vault locally with [`scripts/refresh_demo.py`](../scripts/refresh_demo.py). That command needs a git working copy and a reachable synthesis backend. It never runs in CI.

```bash
python3 scripts/refresh_demo.py --dry-run
python3 scripts/refresh_demo.py
```

The pre-push hook reminds you if the push includes product docs. Wiki-checks builds and lints the *committed* demo; if `demo/.demo-source-rev` is present it also prints a `--dry-run` plan so a stale demo is visible without calling a model.
