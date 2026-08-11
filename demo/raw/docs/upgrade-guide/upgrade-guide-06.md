---
title: "Upgrade guide (part 6/7: v1.4.0 — unified queue + vault state (hard cutover))"
slug: upgrade-guide-06
project: upgrade-guide
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/UPGRADING.md"
content_sha256: 1edde415b51f8cacf9995db66240407df90211d0b78f27234d578b0f7b9b29e3
---

> Part 6 of 7 of **Upgrade guide** — v1.4.0 — unified queue + vault state (hard cutover).

## v1.4.0 — unified queue + vault state (hard cutover)

**Requires Python ≥ 3.12.**

**One-time migration required** if your vault still has legacy dotfiles:

```bash
python3 scripts/migrate_state_v1_4_0.py --state-file /path/to/vault/llmwiki-state.json
# or:
llmwiki migrate-state --state-file /path/to/vault/llmwiki-state.json
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

### Re-run `migrate-state` to repair dead `synth_request` items (#23)

Vaults migrated with the first v1.4.0 migrator carry queue items with `task_type: "synth_request"`. The queue runner has no handler for that type, so `llmwiki queue run` marks every one of them `status: error`. Re-run the migration — it purges them, and enqueues a single `synthesize` task if (and only if) real backlog remains:

```bash
llmwiki migrate-state --state-file /path/to/vault/llmwiki-state.json
llmwiki queue run --vault /path/to/vault
```

The migration resolves each legacy `.llmwiki-pending-prompts/<uuid>.md` against the pending sentinel pages left in `wiki/sources/`, so it is safe to `rm -rf .llmwiki-pending-prompts/` afterwards — the prompts themselves are never needed again.

### Check `synthesis.backend` before syncing (#23)

`agent`, `agent-delegate`, and `agent_delegate` were **removed** in v1.4.0. `resolve_backend()` reads them as a typo and silently falls back to `dummy`, which writes stub pages (`Auto-synthesized from session`) into `wiki/sources/`. `migrate-state` prints a `WARNING:` when your `config.json` still names one — set `synthesis.backend` to `claude`, `ollama`, or `dummy`, then re-synthesize:

```bash
llmwiki synth --vault /path/to/vault
```

Stub pages left behind by the dummy backend count as **unsynthesized** backlog (#24): `llmwiki queue status` reports them under `unsynth_total`, `llmwiki lint` flags them with the `stub_source_pages` rule, and `llmwiki synth` refills them with a real backend.

## v1.3.83+ — unified queue preview (superseded by v1.4.0)

Same migration as v1.4.0; use `scripts/migrate_state_v1_4_0.py`.

## v1.3.0 — consolidated 1.2.x patch roll-up

**Released: 2026-04-26.**

### Summary

Drop-in upgrade from any 1.2.x. v1.3.0 consolidates 38 in-tree patch versions (1.2.1 → 1.2.38) under one minor release tag — no breaking API changes, no schema migrations, no config changes.

```bash
pip install -U llm-notebook   # → 1.3.0
llmwiki --version             # → 1.3.0
```

### What's in it

The full per-fix detail is preserved under the [1.2.x] entries in `CHANGELOG.md`. Two themes:

1. **Opus 4.7 deep code-review backlog (#403, ~26 issues)** — every correctness, perf, and observability finding got a one-issue-one-PR fix. Headliners: `is_subagent` strict path check (#406), `derive_session_slug` UUID-prefix collision (#424), tilde-fence counting in `_close_open_fence` (#419), `wiki_query` ranking length normalisation (#418), `wiki_search` cap (#413), per-vault synth state (#420), `--force` sync persisting `_meta`/`_counters` (#426), subprocess `claude_path` resolved via `shutil.which` (#421).

2. **Performance + features** — `DuplicateDetection` lint rule rewritten with bucket+fingerprint+SequenceMatcher (1s vs minutes on 500 pages, #412), perf-budget test suite (`-m slow`, #429), `md_to_plain_text` cache (#417), auto-seeded project stubs pre-populated from session metadata (#425), 2 new lint rules (`frontmatter_count_consistency`, `tools_consistency`, #378), `wiki-all` slash command, `_context.md` folder convention (#60).

### Breaking — none

Same CLI surface, same config schema, same on-disk state format. The only thing that changed is that the next plain `sync` after a forced re-sync will now correctly identify already-processed files as unchanged (was: re-processed every time, #426).

### Schema migrations — none

State files written by 1.2.x are read verbatim by 1.3.0.
