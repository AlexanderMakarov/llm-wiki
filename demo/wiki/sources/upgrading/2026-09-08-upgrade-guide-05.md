---
title: "Upgrade guide (part 5/5: v1.2.0 — first stable on the 1.x line)"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, pypi-distribution-rename, version-migration, cli-deprecations, lint-rules, adapter-removals, llm-wiki-plus, upgrade-guide, sync-force, schema-migrations]
date: 2026-09-08
source_file: 
project: upgrading
model: 
last_updated: 2026-09-08
---
## Summary

Part five of the upgrade guide documents **v1.2.0** (2026-04-25) as the first stable **1.x** release: PyPI install becomes `pip install llm-wiki-plus` while the module and `llmwiki` CLI stay unchanged. The CLI shed several subcommands (#362), three adapters were removed (#363), demo session frontmatter counts were corrected with new lint rules, and `sync --force` no longer silently drops filename collisions. CI-oriented **`llmwiki all`** runs build → graph → lint (optional `--strict`). Earlier **1.1.x** rc notes cover Obsidian opt-in (#326), backlinks injection, state/quarantine files, session-ref stripping in transcripts, and optional **Ollama** synthesis backend.

## Key Claims

- PyPI distribution name is **`llm-wiki-plus`** because `llmwiki` is taken and `llm-wiki` is rejected as too similar; import and CLI remain `llmwiki`.
- **`llmwiki schedule`**, **`install-skills`**, **`check-links`**, **`watch`**, **`manifest`**, Obsidian/Marp/QMD export helpers, and **`eval`** were removed in v1.2.0; scheduling belongs on the OS job runner, link checks on GitHub Actions, quality on **`llmwiki lint`**.
- **`jira_adapter`**, **`meeting`**, and **`pdf`** adapters were removed in #363; dependents should pin **v1.1.0-rc8** until they migrate.
- **`sync --force`** previously allowed one of two colliding canonical filenames to be overwritten; v1.2.0 disambiguates per run (~200 of 495 sessions affected on a tested corpus).
- JSON sidecars now emit **`user_messages`**, **`tool_calls`**, and **`is_subagent`** as int/bool, not strings; code that compared `is_subagent == "false"` must use **`is_subagent is False`**.
- From **v1.1.0-rc4**, the **Obsidian** adapter no longer runs on every bare **`sync`**; enable with `{ "obsidian": { "enabled": true } }` in **`sessions_config.json`** (#326).

## Key Quotes

> "PyPI distribution name is `llm-wiki-plus` — `llmwiki` belongs to another author, and PyPI's name-similarity rule also rejects `llm-wiki` as too close to it" — explains why only the pip line changed, not the CLI or import.

> "If you ran `sync --force` against a corpus where two sources had the same canonical filename … one of them was silently overwritten" — motivates the v1.2.0 collision fix for large corpora.

## Connections

- [[llmwiki]] (entity) — upgrade target; v1.2.0 CLI slimming, `all` pipeline, lint rules #16/#17, quarantine and state key conventions from 1.1.x.
  - fact: **`llmwiki all`** runs build → graph → lint for CI; **`--strict`** exits 2 on lint warnings.
- [[Adapters]] (concept) — jira/meeting/pdf removed; Obsidian moved to explicit opt-in in rc4.
  - fact: Removed adapter users should pin **v1.1.0-rc8** until migration.
- [[Obsidian]] (entity) — no longer fires on default **`sync`** after rc4; **`enabled: true`** in sessions config restores prior behavior.
- [[GitHub Actions]] (concept) — replaces removed **`llmwiki check-links`**; pairs with **`llmwiki all`** for automated build/lint.
- [[Wiki Synthesis]] (concept) — **`wiki/candidates/`** from v1.0→rc1; **`/wiki-synthesize`** wrapped sources-only synth (retired #214 in favor of **`/wiki-synth`**).
- [[Static Site]] (concept) — **`README.md`** and **`CONTRIBUTING.md`** compile to site HTML; graph nodes without compiled pages show tooltips instead of 404 links.
- [[Knowledge Graph]] (concept) — **`llmwiki backlinks`** injects idempotent **`## Referenced by`** sections; graph click behavior tied to compiled-site existence.
- [[Ollama]] (entity) — **`synthesis.backend`** accepts **`"ollama"`** from v1.0→v1.1.0-rc1 alongside **`"dummy"`**.
- [[Claude Code]] (entity) — global slash commands after **`install-skills`** removal: manually copy **`.claude/commands/wiki-*.md`** into **`~/.claude/commands/`**.
