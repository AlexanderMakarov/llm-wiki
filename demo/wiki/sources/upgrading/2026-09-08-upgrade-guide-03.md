---
title: "Upgrade guide (part 3/5: v1.5.0 — index cwd restore + encoded-path redaction (#56))"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, username-redaction, vault-migration, static-site-rebuild, schema-version-guard, cwd-restore, vault-upgrade, migrate-raw-redaction]
date: 2026-09-08
source_file: 
project: upgrading
model: 
last_updated: 2026-09-08
---
## Summary

Part 3 of the upgrade guide documents **v1.5.0** vault maintenance after pulling or installing a newer `llm-wiki` engine: agents must fix the **user’s vault**, not the llm-wiki git clone. A **`llmwiki build`** is required so `site/projects/index.html` and `site/sessions/index.html` pick up cwd restore, a **Cwd** column, and consistent path display (#56). Optionally, **`llmwiki migrate raw-redaction`** rewrites dash-encoded username segments in existing `raw/sessions/*.md` deterministically when `raw/` will be published—without using `sync --force`, which risks missing old transcripts and unnecessary LLM synth. **#29** blocks `sync` when `llmwiki-state.json` was written by a newer `schema_version`; pre-v1.5.0 checkouts that kept `raw/`/`wiki/` in the clone must move content into a vault by hand and reconcile the index.

## Key Claims

- Cwd restoration and session-table path cleanup for #56 run at **build** time; upgrading the package alone leaves stale `site/` HTML with mixed real home paths and `USER` placeholders.
- `llmwiki migrate raw-redaction` (or `scripts/migrate_raw_encoded_username.py`) rewrites encoded path strings in place and does **not** call the LLM, enqueue synthesize, or modify `wiki/`.
- Using `llmwiki sync --force` to “fix” redaction is discouraged because agent stores often retain sources only ~30 days, so older `raw/` rows may have nothing to re-convert from, and follow-on `synth` can burn tokens on unchanged wiki pages.
- When `schema_version` in the vault state file is greater than the running engine’s version, `sync` errors unless the user upgrades the engine or explicitly passes `--force-resync` for a full reconvert.
- Copying `raw/` and `wiki/` from an in-repo checkout into a new vault leaves demo catalog entries in `index.md` as dead links until `llmwiki sync --no-auto-build` reconciles `index_sync`.

## Key Quotes

> "after the user upgrades `llm-wiki` (pull / `pip install -U` / brew), fix **their** vault — not the llm-wiki git clone. The engine change alone does not rewrite `site/` or `raw/`." — scope of agent responsibility on upgrade

> "Force-sync is the wrong tool anyway: agents may follow it with `synth` / queue digest and **burn LLM tokens** rewriting wiki pages that did not need to change." — why raw-redaction migrator replaces force-sync for path masking

> "error: <vault>/llmwiki-state.json: state file was written by a newer llmwiki (schema_version=2 > 1). Upgrade llmwiki, or pass --force-resync to reconvert from scratch ..." — downgrade guard from #29

## Connections

- [[llmwiki]] (entity) — upgrade, migrate, sync, build, and lint commands all target the user vault, not the framework repo.
  - fact: v1.5.0 pairs engine changes with vault-side rebuild and optional `migrate raw-redaction`.
- [[Static Site]] (concept) — `llmwiki build` regenerates project and session index pages with restored cwds and redacted descriptions.
  - fact: skipping rebuild leaves grep-based #56 checks failing on old `site/sessions/index.html`.
- [[Adapters]] (concept) — Claude/Cursor-style stores use dash-encoded project paths (`-Users-<name>-…`) that convert and migrators normalize to `-Users-USER-…`.
  - fact: new syncs apply encoding redaction automatically; existing `raw/` needs `migrate raw-redaction` only for publish/share completeness.
- [[GitHub Actions]] (concept) — implied when vault or `raw/` is shared publicly; incomplete masking in old `raw/` is a redaction-contract gap, not a private-vault browsing issue.
  - fact: private vaults can skip raw migrator if day-to-day browsing after rebuild is enough.
