---
title: "Slash commands reference (part 3/4: /wiki-build)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-slash-commands, static-site-build, wiki-pipeline, llmwiki-cli, ci-strict-lint]
date: 2026-09-08
source_file: 
project: reference-slash-commands
model: 
last_updated: 2026-09-08
---
## Summary

This reference slice documents agent slash commands for rebuilding the static site and running the full wiki pipeline. `/wiki-build` maps to `python3 -m llmwiki build` and is the right step after manual `wiki/` edits or when you want HTML without sync/synth. `/wiki-all` maps to `llmwiki all` and chains sync → synth → build → graph → lint, with flags to skip stages, choose graph backend, and fail CI on lint warnings via `--strict`. The doc also notes `/wiki-reflect` as a model-orchestrated, token-heavy workflow with no CLI wrapper.

## Key Claims

- `/wiki-build` regenerates the static HTML site and wraps `python3 -m llmwiki build`; use it after manual `wiki/` edits or when you only need a fresh site without the full sync pipeline.
- `/wiki-all` runs the end-to-end pipeline (sync → synth → build → graph → lint) via `python3 -m llmwiki all`; AI-consumable exports such as `llms.txt` and `sitemap.xml` are produced during `build`, not as a separate step.
- Passing `--strict` to `/wiki-all` turns lint warnings into a non-zero exit, which matches what CI should enforce.
- `--no-synth` on `/wiki-all` omits synthesis and avoids calls to the AI provider; `--skip-graph` or `--graph-engine builtin` applies when the optional Graphify backend is not installed.
- `/wiki-reflect` has no CLI wrapper—it is a model-orchestrated workflow that reads index, overview, and a sample of pages—and should be used sparingly because it is the most token-heavy command.

## Key Quotes

> "Pass `--strict` to turn any lint warning into a non-zero exit, which is exactly what CI wants." — documents the intended CI contract for `/wiki-all`.

> "Use sparingly; it's the most token-heavy command." — guidance for `/wiki-reflect` relative to other slash commands.

## Connections

- [[llmwiki]] (entity) — slash commands are the agent-facing surface over `llmwiki build`, `llmwiki all`, and related CLI behavior.
  - fact: `/wiki-build` and `/wiki-all` explicitly wrap `python3 -m llmwiki build` and `python3 -m llmwiki all`.
- [[Static Site]] (concept) — `/wiki-build` is the dedicated step to regenerate static HTML from `wiki/` (and raw inputs as configured).
  - fact: Examples include default build, custom output path (`~/public_html`), and “tree search mode.”
- [[Wiki Synthesis]] (concept) — `/wiki-all` includes synth by default; `--no-synth` opts out to keep the run away from the AI provider.
- [[Knowledge Graph]] (concept) — the full pipeline runs graph unless `--skip-graph` or `--graph-engine builtin` is used when Graphify is unavailable.
- [[GitHub Actions]] (concept) — `--strict` on `/wiki-all` is described as what CI wants for lint-gated builds.
