---
title: "CLI reference (part 13/19: broken-provenance — remap or clear hops to missing raw sessions)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, provenance-repair, source-migration, link-remapping, raw-sessions]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

This reference documentation describes two `llmwiki migrate` subcommands for maintaining source file provenance in the wiki. `migrate source-page-paths` remaps wiki pages and cross-references when raw source files are reorganized, while `migrate broken-provenance` repairs wiki pages that reference deleted raw sessions by remapping them to valid same-day interactive sources or clearing broken hops.

## Key Claims

- Source page paths can become out-of-sync when underlying raw files move, requiring systematic remapping of frontmatter `source_file` entries and all wikilinks (`[[old-stem]]`, `[[old-stem|label]]`) across the vault.
- Broken provenance occurs when wiki pages retain `source_file:` entries pointing to deleted `raw/sessions/…` paths while newer raw files exist under the same project slug (e.g., after re-syncs with different filesystem stems).
- `migrate broken-provenance` only remaps hops within the same calendar day (to prevent accidentally linking June stubs to January sessions) and only to interactive raw files (`is_headless: false` or unmarked/legacy).
- When multiple same-day interactive candidates exist, the migration chooses the uniquely closest HH-MM timestamp; ambiguous ties or no valid candidate results in clearing the broken reference rather than deleting the wiki page.
- Both migrations are idempotent and support `--dry-run` preview; they update synth state to mark pages as stale when raw files are re-converted.

## Key Quotes

> "Never remaps across days (that used to point every June stub at a single January session)." — Critical safety constraint preventing cross-day misremapping.

> "Prefer a Cursor Agent CLI re-sync first so raw filenames carry real chat dates and `is_headless` is stamped; unmarked legacy same-day files remain remap-eligible until then." — Recommended workflow for reliable remap eligibility.

## Connections

- [[llmwiki]] (entity) — the CLI tool providing migration commands
  - fact: Two `migrate` subcommands repair source file provenance after raw file reorganization or deletion.
- [[Wiki Synthesis]] (concept) — relates to tracking and updating source page state
  - fact: Both migrations update synth state (`synth.files` in llmwiki-state.json) to mark moved/remapped pages as stale.
- [[Wikilinks]] (concept) — the cross-reference syntax being remapped
  - fact: All forms of wikilinks (`[[stem]]`, `[[stem|label]]`, `[[stem#anchor]]`, path-qualified variants) are rewritten during source-page-paths migration.
- [[Knowledge Graph]] (concept) — the interconnected wiki that requires consistency during migrations
  - fact: Link remapping must maintain backlink relationships and handle ambiguous redirects systematically.

## Contradictions

None detected.