---
title: "Configuration Reference (part 2/8: CLI subcommands)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration-reference, cli-subcommands, lint-min-refs, sync-flags, pipeline-all, link-integrity]
date: 2026-09-08
source_file: 
project: configuration-reference
model: 
last_updated: 2026-09-08
---
## Summary

This installment of the configuration reference documents core `llmwiki` CLI subcommands from `init` through `version`, with flag tables for `sync`, `build`, `graph`, `lint`, and the v1.2 `all` pipeline. It states that static site build also emits AI-oriented artifacts (`llms.txt`, `graph.jsonld`, `sitemap.xml`, and others) without a separate `export` command. A long subsection explains how `lint --min-refs` aligns broken-link reporting with the candidate harvest threshold so deliberately unmaterialized wikilink targets are not treated as defects.

## Key Claims

- `llmwiki sync --since YYYY-MM-DD` applies a one-run lookback only and overrides durable `filters.since` and per-adapter `since` for every source in that run (#192).
- `llmwiki build` writes `llms.txt`, `llms-full.txt`, `graph.jsonld`, `sitemap.xml`, `rss.xml`, `robots.txt`, and `ai-readme.md` into the output directory; there is no separate `export` subcommand.
- Lint rules disabled in the vault `llmwiki.json` never execute, and every lint report lists those disabled rules by name.
- The default `--min-refs` value is defined once as `llmwiki.vault_settings.DEFAULT_MIN_REFS` and is read by both candidate harvest and `link_integrity`, so “decline to create a page” and “report missing page” cannot drift apart.
- `llmwiki all` runs sync → synth → build → graph → lint by default; `--strict` is shorthand for `--lint-fail warnings` for CI gating, and deprecated `--with-sync` / `--with-synth` are inert but still accepted for backward-compatible parsing.

## Key Quotes

> "Everything below that bar is left unmaterialized *on purpose*, so `link_integrity` honours the same threshold rather than reporting the product's own design decisions as defects." — rationale for tying lint to harvest `--min-refs`

> "`--force-resync` … may duplicate an already-populated `raw/`" — warning that overriding the newer-schema / corrupt-state guard (#29) can reconvert from scratch and duplicate content

## Connections

- [[llmwiki]] (entity) — documents the primary CLI surface (`init`, `sync`, `build`, `lint`, `all`, etc.) that implements the vault toolchain.
  - fact: `llmwiki all` chains sync, synth, build, graph, and lint with per-stage opt-outs and `--lint-fail` / `--strict` for pipeline exit behavior.
- [[Adapters]] (concept) — `sync --adapter` limits which session sources run; `llmwiki adapters` lists registration and store presence.
  - fact: Default sync runs all available adapters unless `--adapter` narrows the set.
- [[Wiki Synthesis]] (concept) — `all` includes synth by default (`--no-synth` skips LLM calls); `--synth-force` forwards force re-synthesis.
- [[Static Site]] (concept) — `build --out` compiles HTML from `raw/` and `wiki/` and emits machine-readable site exports in the same step.
- [[Knowledge Graph]] (concept) — `graph --format json|html|both` builds from wiki wikilinks; `all` forwards `--graph-engine` (default `graphify`).
- [[Wikilinks]] (concept) — `lint --min-refs` gates which unresolved `[[wikilink]]` targets count as broken relative to how often sources name them.
- [[GitHub Actions]] (concept) — `--strict` / `--lint-fail warnings` are described as the CI gate pattern for failing the pipeline on warning-severity lint findings.
