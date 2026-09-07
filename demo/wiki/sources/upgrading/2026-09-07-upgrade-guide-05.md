---
title: "Upgrade guide (part 5/5: v1.2.0 — first stable on the 1.x line)"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, upgrade-guide, release-notes, cli-removal, pypi-naming]
date: 2026-09-07
source_file: raw/docs/upgrading/upgrade-guide-05.md
project: upgrading
model: 
last_updated: 2026-09-07
---
## Summary

Comprehensive upgrade guide covering [[llmwiki]] v1.2.0 (first stable 1.x release, April 2026) and preceding RC versions. Major breaking changes include: PyPI distribution renamed to `llm-wiki-plus` (though Python module name and CLI command remain `llmwiki`), removal of 8 CLI subcommands (#362) and 3 adapters (#363), and schema migrations across RC releases. Includes detailed migration paths from v1.0 forward with backward-compatibility notes where applicable.

## Key Claims

- PyPI distribution is now `llm-wiki-plus` because the name `llmwiki` belongs to another author and `llm-wiki` was rejected as too similar; however, `import llmwiki` and the `llmwiki` CLI command remain unchanged
- Eight CLI subcommands were removed in v1.2.0: `schedule`, `install-skills`, `check-links`, `watch`, `manifest`, `link-obsidian`, `export-obsidian`, `export-marp`, `export-qmd`, `eval` (#362)
- Three adapters were removed in v1.2.0: `jira_adapter`, `meeting`, `pdf` (#363)
- Demo session file counts for `user_messages` and `tool_calls` were 2–10× higher than actual body content; values are now recomputed from source material
- `sync --force` previously silently overwrote colliding sessions; per-run filename tracking now disambiguates regardless of force flag (~200 affected sessions in tested corpus)
- New `llmwiki all` command provides one-shot CI pipeline runner (build → graph → lint)
- [[Obsidian]] adapter transitioned from default-on (v1.1.0-rc3) to opt-in configuration in v1.1.0-rc4
- Session transcript anchors to project-local files are now unwrapped into dead-link spans instead of 404ing (v1.1.0-rc5)

## Key Quotes

> "The Python module + CLI command stay `llmwiki`, only the `pip install` line changes: `pip install llm-wiki-plus`" — clarifies that the distribution rename does not break existing code or workflows

> "`sync --force` no longer drops colliding sessions… Affected ~200 of 495 sessions on a real corpus we tested." — significant real-world correctness improvement

> "Obsidian is opt-in now. Past versions fired the Obsidian adapter on every `sync` by default." — breaking behavioral change requiring configuration addition

## Connections

- [[llmwiki]] (entity) — the core project this upgrade guide documents
  - fact: v1.2.0 is first stable release on 1.x line (released 2026-04-25)
  - fact: Upgrade notes cover v1.2.0, v1.1.0-rc5/rc4/rc3, and v1.0.0→v1.1.0-rc1 paths
  
- [[Codex CLI]] (entity) — command-line interface undergoes significant simplification
  - fact: 8 subcommands removed in #362; users must replace with OS-native job runners, manual config copy, or external tools
  - fact: New `llmwiki all` command added for CI (runs build, graph, lint sequentially)
  
- [[Adapters]] (concept) — adapter system pruned and behavior shifted
  - fact: Three adapters removed (#363): jira_adapter, meeting, pdf
  - fact: v1.1.0-rc4 makes [[Obsidian]] adapter opt-in; requires config entry `{ "obsidian": { "enabled": true } }`
  
  - fact: Changed from automatic execution on every sync to opt-in configuration
  
- [[Static Site]] (concept) — site generation and link handling improved
  - fact: README.md and CONTRIBUTING.md now compile to site HTML (rc5)
  - fact: Graph clicks check for compiled-page existence; missing pages show tooltip instead of 404
  
- [[Configuration]] (concept) — config system evolved across releases
  - fact: Obsidian adapter requires explicit enablement in sessions_config.json
  - fact: Schema migrations in rc3+ rewrite state file paths from absolute to `<adapter>::<home-relative-path>` format
  
- [[Ollama]] (entity) — synthesis backend option added
  - fact: synthesis.backend now accepts "ollama" in addition to default "dummy" (v1.1.0-rc1+)
  
- [[GitHub Actions]] (entity) — moved responsibility for link checking
  - fact: `llmwiki check-links` CLI removed; users should use GitHub Actions link-check workflow instead

## Contradictions

None identified. This is authoritative upgrade documentation; all statements are internally consistent with their referenced version tags and issue numbers.