---
title: "Upgrade guide (part 8/8: v1.1.0-rc4)"
slug: upgrade-guide-08
project: upgrading
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/UPGRADING.md"
content_sha256: c3075657888a257c11c0c2658857c42e4c57a45b7e70f26eac2aec1c3b5b4614
---

> Part 8 of 8 of **Upgrade guide** — v1.1.0-rc4.

## v1.1.0-rc4

**Released: 2026-04-20.**

### New behaviour

- **Obsidian is opt-in now.** Past versions fired the Obsidian adapter on every `sync` by default. If your workflow relied on that, add this to `sessions_config.json`:

  ```json
  { "obsidian": { "enabled": true } }
  ```

  Context: [#326](https://github.com/AlexanderMakarov/llm-wiki/issues/326). Runs as of rc3; surfaced in `llmwiki adapters` column `will_fire`.

- **Graph clicks respect compiled-site existence.** Nodes whose corresponding page wasn't rendered to HTML show a tooltip instead of opening a 404. No action needed — if you see the tooltip on entity / concept / nav pages that's the new design.

- **Backlinks now propagate.** Run `llmwiki backlinks` once to inject managed `## Referenced by` sections into every linked-to page. Idempotent, dry-runnable, prune-able:

  ```bash
  llmwiki backlinks --dry-run --verbose   # preview
  llmwiki backlinks                       # commit writes
  llmwiki backlinks --prune               # strip every block
  ```

### Schema migrations

- `.llmwiki-state.json` keys rewrite from absolute paths to `<adapter>::<home-relative-path>` on first load under rc3+. Migration is automatic and idempotent. If you moved your repo to a new machine, old state will be preserved verbatim — re-sync to reindex.

- `.llmwiki-quarantine.json` is a new local file (gitignored). First appears when a convert error happens. Inspect with `llmwiki quarantine list`.

- Frontmatter `tags:` / `topics:` convention is lint-enforced (rule
  #14 `tags_topics_convention`) — projects use `topics:`, everything
  else uses `tags:`. Run `llmwiki tag convention` to see violations. `llmwiki tag rename <old> <new>` rewrites across every page.

### Breaking — none

No breaking CLI or config changes. Every test pre-upgrade keeps passing post-upgrade.

## v1.1.0-rc3

See the [release notes](https://github.com/AlexanderMakarov/llm-wiki/releases/tag/v1.1.0-rc3) for the full rc3 gap-sweep bundle. No migration required.

## v1.0.0 → v1.1.0-rc1

Config: `synthesis.backend` now accepts `"ollama"` in addition to the default `"dummy"`. See `docs/reference/prompt-caching.md` for the ollama setup.

`wiki/candidates/` directory is new — created automatically by ingest when it sees a brand-new entity/concept. Triage with `/wiki-candidates` (renamed from `/wiki-review` in rc3).

## Older versions

Pre-v1.0 milestones shipped under internal sprint tags. Upgrade from v0.9.x to v1.0.0 in one step — no intermediate migration required. If you're on a pre-0.9 build, start fresh: `llmwiki init` in a new tree and re-run `sync`.
