---
title: "Upgrade guide (part 7/8: v1.3.0 — consolidated 1.2.x patch roll-up)"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, release-notes, upgrade-guide, backwards-compatibility, schema-migrations, cli-deprecation]
date: 2026-09-28
source_file: 
project: upgrading
model: 
last_updated: 2026-09-29
---
## Summary

This is part 7 of the upgrade guide, documenting v1.3.0 (2026-04-26), v1.2.0 (2026-04-25), and v1.1.0-rc5 (2026-04-21) releases of llmwiki. v1.3.0 consolidates 38 patches from the 1.2.x line with no breaking changes or schema migrations. v1.2.0, the first stable 1.x release, renamed the PyPI distribution to `llm-wiki-plus`, removed several CLI subcommands and adapters, and fixed data correctness issues. v1.1.0-rc5 introduced session transcript cleanup and compilation of core documentation as site pages.

## Key Claims

1. v1.3.0 is a drop-in upgrade from any 1.2.x version with no breaking API changes, schema migrations, or config changes.
2. v1.3.0 fixes derived from an Opus 4.7 code-review backlog (~26 issues) address correctness, performance, and observability concerns, including strict path checking, UUID collision handling, fence counting, query ranking normalization, and per-vault synthesis state.
3. v1.2.0 removed CLI subcommands (schedule, install-skills, check-links, watch, manifest, link-obsidian, export-obsidian, export-marp, export-qmd, eval) and adapters (jira_adapter, meeting, pdf), requiring affected users to pin v1.1.0-rc8 until migration.
4. The PyPI distribution was renamed to `llm-wiki-plus` to resolve name-similarity conflicts, but the Python module name and CLI command remain `llmwiki`.
5. v1.2.0 fixes `sync --force` to no longer silently drop colliding sessions; per-run filename tracking disambiguates conflicts and prevented data loss for ~200 of 495 sessions in tested corpora.
6. v1.3.0 rewrote the DuplicateDetection lint rule using bucket+fingerprint+SequenceMatcher, reducing runtime from minutes to 1 second on 500-page wikis.

## Key Quotes

> "Drop-in upgrade from any 1.2.x. v1.3.0 consolidates 38 in-tree patch versions (1.2.1 → 1.2.38) under one minor release tag — no breaking API changes, no schema migrations, no config changes." — Clarifies the scope and safety of the upgrade path.

> "The PyPI distribution carries a `-plus` suffix. The Python module + CLI command stay `llmwiki`, only the `pip install` line changes" — Emphasizes that despite the distribution rename to avoid PyPI conflicts, the developer-facing API remains stable.

> "If you ran `sync --force` against a corpus where two sources had the same canonical filename (rare but real on large corpora), one of them was silently overwritten. Fix: per-run filename tracking now disambiguates regardless of `--force`. Affected ~200 of 495 sessions on a real corpus we tested." — Documents a data loss bug in large deployments and its fix.

## Connections

- [[llmwiki]] (entity) — primary subject across three release versions
  - fact: v1.3.0 (2026-04-26) consolidates 38 patches with no breaking changes
  - fact: v1.2.0 (2026-04-25) is the first stable 1.x release
  - fact: PyPI distribution renamed to llm-wiki-plus in v1.2.0

- [[Lint Rules]] (concept) — new data quality validation rules introduced
  - fact: v1.3.0 adds frontmatter_count_consistency and tools_consistency rules to prevent regression
  - fact: DuplicateDetection rewritten with fingerprinting, improving performance from minutes to 1 second

- [[Wiki Synthesis]] (concept) — per-vault synthesis state tracking improved
  - fact: v1.3.0 implements per-vault synth state (#420) instead of global state

- [[Static Site]] (concept) — documentation compilation to static pages
  - fact: v1.1.0-rc5 added README.md and CONTRIBUTING.md as compiled site pages
  - fact: Link rewriter routes to compiled pages instead of GitHub URLs

- [[GitHub Actions]] (entity) — CI/CD workflows replace removed local commands
  - fact: v1.2.0 removes check-links CLI command, directs users to GitHub Actions link-check workflow