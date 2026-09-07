---
title: "Upgrade guide (part 3/5: v1.5.0 — index cwd restore + encoded-path redaction (#56))"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, vault-upgrade, path-redaction, cwd-restore, schema-versioning]
date: 2026-09-07
source_file: raw/docs/upgrading/upgrade-guide-03.md
project: upgrading
model: 
last_updated: 2026-09-07
---
## Summary

This part of the upgrade guide documents the v1.5.0 release, which introduces index working-directory restoration and encoded-path redaction. It provides required rebuild steps for users' vaults, an optional deterministic path migrator (without LLM cost), clarification on downgrade protection via schema versioning, and migration guidance for pre-v1.5.0 checkouts that stored wiki content in the git clone.

## Key Claims

- After upgrading to v1.5.0, users must rebuild their vault with `llmwiki build --vault <path>` to restore local working directory paths and add a Cwd column to the sessions index table.
- A deterministic `migrate raw-redaction` command rewrites dash-encoded paths in `raw/` without calling the LLM, enqueuing synthesis, or modifying `wiki/`.
- Using `llmwiki sync --force` for path redaction is inappropriate because agent stores retain transcripts only ~30 days, so older sessions in `raw/` often have no source file to re-convert and will silently fail.
- As of #29, vaults written by newer llm-wiki versions cannot be opened by older engines; the engine must be upgraded to match the vault's `schema_version` in `llmwiki-state.json`.
- Pre-v1.5.0 checkouts that stored `raw/` and `wiki/` inside the git clone require manual copy to the vault and cleanup of dead index links.

## Key Quotes

> "For AI agents maintaining a user's vault: after the user upgrades llm-wiki... fix **their** vault — not the llm-wiki git clone."
— Clarifies that upgrades target the user's vault, not the development repository.

> "it rewrites path strings in place, does **not** call the LLM, does **not** enqueue synthesize, and does **not** touch wiki/"
— Explains the safety guarantees of the deterministic migrator.

> "The fix is to **upgrade the engine** to match the vault."
— Directs users to resolve downgrade-protection errors.

## Connections

- [[llmwiki]] (tool) — v1.5.0 release with index restoration and path redaction features
  - fact: `llmwiki build --vault <path>` is required after upgrade to restore local cwds
  - fact: `llmwiki migrate raw-redaction` command is available for deterministic path rewriting
- [[Configuration]] (concept) — username redaction settings in config.json
  - fact: Redaction auto-detects after upgrade; manual config edit is not required unless intentionally disabled
- [[Vault management]] (implied topic) — vault upgrade procedures and schema versioning
  - fact: Downgrade protection prevents older engines from opening vaults written by newer versions

## Contradictions

None identified in this session.