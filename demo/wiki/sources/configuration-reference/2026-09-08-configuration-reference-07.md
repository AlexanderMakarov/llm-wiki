---
title: "Configuration Reference (part 7/8: Vault file (llmwiki.json))"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration-reference, llmwiki-json, lint-disabled-rules, vault-configuration, content-freshness]
date: 2026-09-08
source_file: 
project: configuration-reference
model: 
last_updated: 2026-09-08
---
## Summary

This installment documents the vault-root file `llmwiki.json`, which travels with the wiki (unlike gitignored install `config.json`) and is read by `lint`, the `all` pipeline’s lint stage, and MCP `wiki_lint`. It focuses on `lint.disabled_rules`: how to disable checks that cannot apply to a given wiki (list or name→reason map), how reports and `lint --json` surface skipped rules via `disabled_rules` and `ran`, and why invalid declarations fail with exit 2 instead of silently ignoring opt-outs. It also clarifies that disabling a rule removes its findings entirely (not a severity filter) and notes env vars `LLMWIKI_CONFIG`, `COPILOT_HOME`, and removal of `LLMWIKI_ROOT` in favor of `vault.default_path` in `config.json`.

## Key Claims

- `<vault-root>/llmwiki.json` describes wiki-specific settings (today: lint opt-outs); `config.json` at the install root describes adapter/redaction/synthesis behavior and does not travel with a copied vault.
- A disabled lint rule is never constructed or run; skipped rules are always named in reports so a short report cannot be mistaken for a full clean run.
- `lint.disabled_rules` accepts either a bare array of rule names or an object mapping each name to a one- or two-sentence reason printed verbatim on one line in every report.
- Unknown rule names, invalid JSON, or malformed `disabled_rules` shape cause **exit 2** with explicit errors; the tool does not fall back to “no opt-outs.”
- Disabling every registered rule (or every rule in a narrowed `--rules` run) yields a report that nothing was checked, not a clean summary.
- Disabling a rule is only appropriate when a check **cannot apply** (e.g. `content_freshness` on a committed snapshot); it is not a substitute for fixing real staleness or other defects.
- Vault content root is `vault.default_path` in `config.json`; `LLMWIKI_ROOT` is no longer read.

## Key Quotes

> "A disabled rule is never constructed, never runs, and contributes no findings — and is named as skipped in every report, whether or not anything was found, so a short report can never be mistaken for a clean one." — design goal for `lint.disabled_rules` visibility

> "A declaration that cannot be honoured is an error, never a silent skip" — invalid `llmwiki.json` lint config must not pretend the wiki has no opt-outs

> "This is not a noise filter. A disabled rule does not run, so anything it *would* have found is simply absent from the report" — scope limit for when to disable rules

> "`content_freshness` on a committed snapshot is the legitimate case" — documented example for disabling calendar-driven staleness on frozen published copies

## Connections

- [[llmwiki]] (entity) — product whose vault carries `llmwiki.json` beside `wiki/`, `raw/`, and `llmwiki-state.json`
  - fact: Wiki-level quality opt-outs live in committed vault JSON, not in install `config.json`.
- [[Configuration Reference]] (concept) — multi-part reference; this page is part 7/8 covering the vault file
  - fact: Contrasts `config.json` vs `llmwiki.json` by location, commit policy, and which commands read each file.
- [[Lint Rules]] (concept) — the 17 wiki quality rules; names match `## <rule>` headings and CLI reference
  - fact: `disabled_rules` only turns rules off entirely; severity cannot be re-graded per wiki.
- [[Configuration]] (concept) — install and vault configuration split
  - fact: `LLMWIKI_CONFIG` overrides install config path; vault path comes from `vault.default_path`.
- [[MCP Server]] (concept) — `wiki_lint` consumes the same lint behavior and `rules` narrowing as the CLI
  - fact: JSON output always includes `disabled_rules` (empty when undeclared) and `ran` for checks that actually executed.
