---
title: "Slash commands reference (part 1/4)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-slash-commands, agent-kit, cli-vs-slash, wiki-lint, vault-pipeline]
date: 2026-09-08
source_file: 
project: reference-slash-commands
model: 
last_updated: 2026-09-08
---
## Summary

This reference slice catalogs the twelve `/wiki-*` slash commands shipped with `llmwiki install-agent-kit` for the vault pipeline (init through `/wiki-all`), and states that maintainer/AWOS commands such as `/release` are documented separately and are not installed by the agent kit. It gives a decision tree for choosing **CLI** (`python3 -m llmwiki …`) versus **slash** commands inside Claude Code: automation, piping, and human-only reading favor the CLI; free-form questions and model-driven follow-up favor slashes because the agent sees stdout and can chain steps. Wiki quality checks are unified under `llmwiki lint` / `/wiki-lint` with error/warning/info severities—there is no separate `eval` subcommand.

## Key Claims

- The agent kit installs exactly twelve vault-pipeline slash commands; maintainer delivery commands (`/release`, `/fix-bug`, `/implement-feature`) are outside that set and live in maintainer docs.
- Slash command files ship in the installable package and land in the agent directory via `llmwiki install-agent-kit --dest PATH`.
- Structural and content wiki quality is checked only through `llmwiki lint` / `/wiki-lint`, not a distinct `eval` subcommand.
- Use CLI when output is for you to read and act on manually; use slash when output should feed the next LLM turn (e.g. `/wiki-query` or chaining after sync/build).
- Lint should run after `/wiki-sync` or `/wiki-build` and in CI; `--fail-on-errors` makes non-zero exit depend only on `error`-severity rules.

## Key Quotes

> "Rule of thumb: if the output is for *you* to read + act on manually, use the CLI. If the output should feed back into an LLM turn, use the slash — the model sees the full stdout and can chain into the next step." — CLI vs slash selection criterion

> "Structural and content quality for the wiki is **`llmwiki lint`** / **`/wiki-lint`** — there is no separate `eval` subcommand." — where wiki quality lives in the toolchain

## Connections

- [[llmwiki]] (entity) — documents the installable slash surface and how it maps to the Python CLI for the Karpathy-style vault loop.
  - fact: `/wiki-synth` synthesizes pending raw into `wiki/sources/` and harvests candidates; `/wiki-build` regenerates static HTML.
- [[Claude Code]] (entity) — primary environment named for invoking `/wiki-*` commands after agent-kit install.
- [[Wiki Synthesis]] (concept) — `/wiki-synth` and `/wiki-candidates` are the synthesis and triage steps in the documented pipeline order.
- [[Static Site]] (concept) — `/wiki-build` wraps site regeneration; CLI is appropriate for one-shot builds in scripts.
- [[Wikilinks]] (concept) — `/wiki-graph` builds the knowledge graph from `[[wikilinks]]`; lint checks wikilink integrity.
- [[CLAUDE.md]] (concept) — agent schema and workflows align with the same command names and ingest/synth/lint/build loop described here.
