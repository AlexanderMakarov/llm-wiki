---
title: "Upgrade guide (part 4/5: v1.4.0 — unified queue + vault state (hard cutover))"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, vault-migration, unified-queue, python-3-12, synthesis-backend, upgrade-guide, llmwiki-state]
date: 2026-09-08
source_file: 
project: upgrading
model: 
last_updated: 2026-09-08
---
## Summary

This upgrade-guide slice documents the **v1.4.0 hard cutover**: legacy vault dotfiles and env-based roots consolidate into a single `llmwiki-state.json` (with a `llmwiki-state.js` sidecar for the static site), Python **≥ 3.12** becomes mandatory, and work is driven by **`llmwiki queue`** instead of SessionStart auto-sync. Operators must run **`llmwiki migrate state`** once, fix removed **`synthesis.backend`** values (`agent` / `agent_delegate`), and rebuild **`site/`** so Home loads the new sidecar. The same part notes **v1.3.0** as a drop-in roll-up of 1.2.x patches with no schema break.

## Key Claims

- v1.4.0 merges `.llmwiki-state.json`, `.llmwiki-synth-state.json`, `.llmwiki-queue.json`, and `.llmwiki-pending-prompts/` into `<vault>/llmwiki-state.json` plus `llmwiki-state.js`.
- `LLMWIKI_ROOT` is replaced by `vault.default_path` in `config.json`; active state is **process-scoped** via `configure_state_file` from CLI flags or config, not import-time bindings.
- `synthesis.backend` values `agent`, `agent-delegate`, and `agent_delegate` were removed; `resolve_backend()` treats them as invalid and **silently falls back to `dummy`**, which can leave stub source pages that count as unsynthesized backlog.
- Queue items with `task_type: "synth_request"` from an early v1.4.0 migration have **no runner handler** and end in `status: error` until **`migrate state` is re-run**, which purges them and may enqueue a single `synthesize` task if backlog remains.
- After v1.4.0, **`llmwiki add` synthesizes only the docs it just wrote**, not the entire backlog (contrast with pre-1.4.0 behavior in the guide’s before/after table).
- v1.3.0 (2026-04-26) bundles 1.2.1–1.2.38 with **no breaking API, config, or state schema changes** relative to 1.2.x.

## Key Quotes

> "SessionStart auto-sync hook | Manual `llmwiki queue run`" — documents the operational shift from hook-driven sync to explicit queue execution in v1.4.0.

> "`agent`, `agent-delegate`, and `agent_delegate` were **removed** in v1.4.0. `resolve_backend()` reads them as a typo and silently falls back to `dummy`" — explains stub `wiki/sources/` pages and the need to set `claude`, `ollama`, or `dummy` explicitly.

> "The queue runner has no handler for that type, so `llmwiki queue run` marks every one of them `status: error`" — rationale for re-running `migrate state` on vaults with legacy `synth_request` items (#23).

## Connections

- [[llmwiki]] (entity) — release upgrade path, CLI (`migrate state`, `queue status|enqueue|run`, `synth`, `add`) and vault state layout.
  - fact: v1.4.0 centralizes queue and sync/synth state in `llmwiki-state.json` at the vault root.
- [[Wiki Synthesis]] (concept) — backend selection, backlog semantics, and stub detection (`stub_source_pages`, `unsynth_total`).
  - fact: removed delegate backends; dummy stubs are treated as unsynthesized until a real backend refills them.
- [[Static Site]] (concept) — post-upgrade **`llmwiki build`** copies the state sidecar so Home can load `llmwiki-state.js` from `site/`.
- [[Ollama]] (entity) — named as a supported `synthesis.backend` alongside `claude` and `dummy` after v1.4.0.
- [[Adapters]] (concept) — indirect: unified vault state and queue ownership replace external `wiki_tasks` queue patterns described in the before/after table.
