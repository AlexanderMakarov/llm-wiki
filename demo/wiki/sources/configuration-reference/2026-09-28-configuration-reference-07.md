---
title: "Configuration Reference (part 7/8: Vault file (llmwiki.json))"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration-reference, lint-rules, vault-configuration, disabled-rules]
date: 2026-09-28
source_file: 
project: configuration-reference
model: 
last_updated: 2026-09-28
---
## Summary

This documentation page explains `llmwiki.json`, the vault-level configuration file that persists with a vault when copied or published. It focuses on the `lint.disabled_rules` configuration, which allows wikis to opt out of quality checks that cannot apply to them, with strict error handling that prevents silent fallbacks from invalid declarations.

## Key Claims

- `llmwiki.json` lives at the vault root beside `wiki/`, `raw/`, and `llmwiki-state.json`, and must be committed to version control (unlike `config.json`)
- `lint.disabled_rules` can be either a bare list of rule names or an object mapping rule names to written reasons for disabling them
- A disabled rule is never constructed, never runs, and contributes no findings to reports; all disabled rules are named in every report
- Invalid declarations (unrecognized rule names, malformed JSON, wrong structure) cause exit code 2 with detailed errors—there is no silent fallback or default behavior
- The environment variable `LLMWIKI_ROOT` was removed; vault path is now specified only via `vault.default_path` in `config.json`

## Key Quotes

> "A disabled rule is never constructed, never runs, and contributes no findings — and is named as skipped in every report, whether or not anything was found, so a short report can never be mistaken for a clean one."
- Establishes that disabling is transparent and prevents confusion between a clean report and a disabled-rules report.

> "Reserve the declaration for checks that **cannot apply** to a wiki, not for checks that are merely inconvenient."
- Clarifies the intent: disable only impossible checks (e.g., staleness on a frozen snapshot), not uncomfortable ones.

> "A declaration nobody can read might be switching every check off, so reporting the wiki as clean would be a guess dressed up as a result — and a typo must never leave a check switched on that you believed you had switched off."
- Explains why invalid declarations are errors: allowing silent skips would make error detection impossible.

## Connections

- [[Lint Rules]] (concept) — this page documents the `lint.disabled_rules` configuration for disabling quality checks per-wiki
  - fact: Disabled rules never run and never contribute findings, and are named in every lint report for transparency
  - fact: Invalid rule names or malformed configurations cause exit code 2; invalid declarations are never silently ignored
- [[llmwiki]] (entity) — this page documents `llmwiki.json`, the vault-level configuration file for llmwiki
  - fact: `llmwiki.json` is committed and travels with the vault when published or copied, unlike the install-level `config.json`
  - fact: Read by `lint`, the `all` pipeline's lint stage, and the MCP `wiki_lint` tool