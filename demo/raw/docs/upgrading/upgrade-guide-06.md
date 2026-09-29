---
title: "Upgrade guide (part 6/8: Downgrading is guarded (#29))"
slug: upgrade-guide-06
project: upgrading
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/UPGRADING.md"
content_sha256: c3075657888a257c11c0c2658857c42e4c57a45b7e70f26eac2aec1c3b5b4614
---

> Part 6 of 8 of **Upgrade guide** — Downgrading is guarded (#29).

## Downgrading is guarded (#29)

Pointing an **older** checkout at a vault a **newer** engine wrote used to silently reconvert everything under the old slug scheme, duplicating `raw/`. As of #29, `sync` refuses to run when the vault's `llmwiki-state.json` was written by a newer `meta.schema_version`, or is present but unreadable:

```
error: <vault>/llmwiki-state.json: state file was written by a newer llmwiki
(schema_version=2 > 1). Upgrade llmwiki, or pass --force-resync to reconvert
from scratch ...
```

The fix is to **upgrade the engine** to match the vault. Only pass `sync --force-resync` if you genuinely want a full reconvert from scratch (it implies `--force` and may duplicate an already-populated `raw/`). This guard protects the newer→older direction; the older engine that lacks it still can't see the unified file, so keep engines at or ahead of the version that last wrote the vault.

### Moving an in-clone wiki into a vault (pre-v1.5.0 checkouts only)

#29 shipped in **v1.5.0**, so a fresh install is vault-first and nothing here applies to it. If you ran a pre-release checkout that kept `raw/` and `wiki/` inside the git clone and you are now setting `vault.default_path`, move the content by hand — there is no migration command, and two trees holding the same wiki drift silently:

```bash
llmwiki init --vault /path/to/vault          # scaffold + seed the vault
cp -r raw/ wiki/ /path/to/vault/             # move your content across
llmwiki sync --vault /path/to/vault --no-auto-build   # reconcile index after copy
llmwiki lint --vault /path/to/vault --rules index_sync
```

Two things to do explicitly, because neither is obvious:

- **Delete the demo entries from the copied `index.md`.** The clone's `wiki/index.md` catalogs the repo's demo pages (`entities/Anthropic.md`, `concepts/CachePricing.md`, `projects/demo-*.md`). Copied into a vault that has none of them, every one becomes a dead index link. `llmwiki sync --no-auto-build` reconciles the catalog for you — that is the reason to run it right after the copy.
- **Remove the leftover ignored pages from the clone.** `raw/` and `wiki/` are gitignored, so anything left behind is invisible to `git status` but still real on disk. A command run without a vault (or from a script with a different config) writes there, and you end up with pages that exist in only one of the two trees.

## v1.4.0 — unified queue + vault state (hard cutover)

**Requires Python ≥ 3.12.**

**One-time migration required** if your vault still has legacy dotfiles:

```bash
python3 scripts/migrate_state_v1_4_0.py --state-file /path/to/vault/llmwiki-state.json
# or:
llmwiki migrate state --state-file /path/to/vault/llmwiki-state.json
# optional cleanup after verifying:
# rm -rf /path/to/vault/.llmwiki-state.json ...
```

### What changed

| Before | After |
|---|---|
| `.llmwiki-state.json`, `.llmwiki-synth-state.json`, `.llmwiki-queue.json`, `.llmwiki-pending-prompts/` | `<vault>/llmwiki-state.json` (+ `llmwiki-state.js` sidecar) |
| `LLMWIKI_ROOT` env var | `vault.default_path` in `config.json` |
| SessionStart auto-sync hook | Manual `llmwiki queue run` |
| `synthesis.backend: agent_delegate` | Removed — use `dummy`, `ollama`, or `claude` |
| external `wiki_tasks` queue ownership | `llmwiki queue enqueue` into vault state |
| Python 3.9–3.11 | **Python ≥ 3.12** |
| `llmwiki add` synthesized whole backlog | `add` synthesizes **only** the docs it just wrote |

### New commands

```bash
llmwiki queue status
llmwiki queue enqueue --task-type add_doc --source https://example.com
llmwiki queue run --limit 20
```

Rebuild the site after upgrading so the Home page loads `llmwiki-state.js` from `site/` (build copies the vault sidecar into the site tree).

### State path isolation (v1.4.0+)

The active state file is **process-scoped**: `llmwiki` CLI entry points call `configure_state_file` once from `--vault` / `--state-file` / `config.json` `vault.default_path`. Library code and tests must pass an explicit `state_file=` override or rely on that configured path — there are no import-time vault bindings.

If `llmwiki-state.json` looks truncated (e.g. only a handful of `synth.files` keys after a test run), re-run the migration against your vault:

```bash
PYTHONPATH=/path/to/llm-wiki python3 scripts/migrate_state_v1_4_0.py \
  --state-file /path/to/vault/llmwiki-state.json
```

Legacy dotfiles (`.llmwiki-state.json`, `.llmwiki-synth-state.json`, …) are merged in; verify `sync.files` / `synth.files` counts before deleting them.

### Re-run `migrate state` to repair dead `synth_request` items (#23)

Vaults migrated with the first v1.4.0 migrator carry queue items with `task_type: "synth_request"`. The queue runner has no handler for that type, so `llmwiki queue run` marks every one of them `status: error`. Re-run the migration — it purges them, and enqueues a single `synthesize` task if (and only if) real backlog remains:

```bash
llmwiki migrate state --state-file /path/to/vault/llmwiki-state.json
llmwiki queue run --vault /path/to/vault
```

The migration resolves each legacy `.llmwiki-pending-prompts/<uuid>.md` against the pending sentinel pages left in `wiki/sources/`, so it is safe to `rm -rf .llmwiki-pending-prompts/` afterwards — the prompts themselves are never needed again.

### Check `synthesis.backend` before syncing (#23)

`agent`, `agent-delegate`, and `agent_delegate` were **removed** in v1.4.0. `resolve_backend()` reads them as a typo and silently falls back to `dummy`, which writes stub pages (`Auto-synthesized from session`) into `wiki/sources/`. `migrate state` prints a `WARNING:` when your `config.json` still names one — set `synthesis.backend` to `claude`, `ollama`, or `dummy`, then re-synthesize:

```bash
llmwiki synth --vault /path/to/vault
```

Stub pages left behind by the dummy backend count as **unsynthesized** backlog (#24): `llmwiki queue status` reports them under `unsynth_total`, `llmwiki lint` flags them with the `stub_source_pages` rule, and `llmwiki synth` refills them with a real backend.

## v1.3.83+ — unified queue preview (superseded by v1.4.0)

Same migration as v1.4.0; use `scripts/migrate_state_v1_4_0.py`.
