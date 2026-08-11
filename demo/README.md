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
python3 -m llmwiki build --vault demo --out demo/site
python3 -m llmwiki serve --dir demo/site
```

CI publishes the same tree via `.github/workflows/pages.yml`, which runs `llmwiki build --vault demo --out ./site` and uploads the result to GitHub Pages. Nothing is seeded or copied: everything the build needs is committed here.

## Refresh the synthesized pages

`demo/wiki/sources/` holds pre-synthesized pages so CI stays free, deterministic and secret-free — synthesis runs locally against a real backend, never in a workflow.

```bash
python3 -m llmwiki synth --vault demo --force
```
