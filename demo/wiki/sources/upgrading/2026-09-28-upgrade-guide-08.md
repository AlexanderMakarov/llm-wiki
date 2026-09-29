---
title: "Upgrade guide (part 8/8: v1.1.0-rc4)"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, release-notes, obsidian-adapter, backlinks, schema-migration, lint-rules]
date: 2026-09-28
source_file: 
project: upgrading
model: 
last_updated: 2026-09-29
---
## Summary

Release notes for [[llmwiki]] v1.1.0-rc4 (2026-04-20) and upgrade path documentation. Major changes include making the [[Obsidian]] [[Adapters|adapter]] opt-in (requiring explicit config), implementing backlinks propagation to create backward-reference sections, automatic schema migration for state tracking, and lint enforcement of tags/topics conventions. No breaking changes; backward compatibility maintained.

## Key Claims

- [[Obsidian]] adapter is now opt-in by default and requires `{ "obsidian": { "enabled": true } }` in `sessions_config.json` to enable (previously fired on every sync automatically).
- [[Backlinks|Wikilinks]] propagation is idempotent and invoked via `llmwiki backlinks`, supporting `--dry-run` and `--prune` operations to create `## Referenced by` sections.
- State file migration from absolute paths to `<adapter>::<home-relative-path>` format happens automatically on first rc3+ load and is idempotent.
- New `.llmwiki-quarantine.json` file (gitignored) appears when conversion errors occur; inspectable via `llmwiki quarantine list`.
- Frontmatter tags/topics convention is now [[Lint Rules|lint-enforced]] (rule #14): projects use `topics:`, everything else uses `tags:`.
- Graph navigation shows tooltips for unrendered pages instead of 404s when clicking nodes whose page wasn't compiled to HTML.
- No breaking CLI or config changes; all pre-upgrade tests pass post-upgrade.

## Key Quotes

> "Obsidian is opt-in now. Past versions fired the Obsidian adapter on every `sync` by default." — Behavior flip requiring explicit opt-in for previously automatic functionality.

> "Run `llmwiki backlinks` once to inject managed `## Referenced by` sections into every linked-to page. Idempotent, dry-runnable, prune-able" — New feature with first-class safety and reversibility guarantees.

> "Migration is automatic and idempotent." — Upgrade strategy prioritizing user safety and non-destructiveness.

## Connections

- [[llmwiki]] (entity) — core system whose release is documented
  - fact: v1.1.0-rc4 released 2026-04-20 with no breaking changes
  - fact: Graph navigation avoids 404s by respecting compiled-site existence

- [[Obsidian]] (entity) — adapter enablement model changed
  - fact: Shifted from default-enabled to opt-in; discoverable via `llmwiki adapters` column `will_fire`

- [[Adapters]] (entity) — configuration and discovery mechanism expanded
  - fact: Adapter firing status now queryable; Obsidian behavior became configurable

- [[Wikilinks]] (concept) — backlinks create bidirectional reference structure
  - fact: Backlinks propagation creates `## Referenced by` sections automatically across all linked-to pages

- [[Lint Rules]] (concept) — new enforcement for metadata consistency
  - fact: Rule #14 enforces tags/topics convention; `llmwiki tag convention` command reports violations; `llmwiki tag rename` rewrites across all pages

- [[Configuration]] (entity) — schema and state management updated
  - fact: `.llmwiki-state.json` auto-migrates from absolute to adapter-relative paths on first rc3+ load
  - fact: New `.llmwiki-quarantine.json` quarantines conversion errors locally