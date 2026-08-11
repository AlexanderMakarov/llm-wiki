---
title: "Upgrade guide (part 4/7: Unreleased — pipeline reshape: export/reindex CLI removed, all extended)"
slug: upgrade-guide-04
project: upgrade-guide
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/UPGRADING.md"
content_sha256: 1edde415b51f8cacf9995db66240407df90211d0b78f27234d578b0f7b9b29e3
---

> Part 4 of 7 of **Upgrade guide** — Unreleased — pipeline reshape: export/reindex CLI removed, all extended.

## Unreleased — pipeline reshape: export/reindex CLI removed, `all` extended

- **`llmwiki export` is gone.** AI-consumable files (`llms.txt`, `llms-full.txt`, `sitemap.xml`, `rss.xml`, `robots.txt`, `graph.jsonld`, `ai-readme.md`, etc.) are written by `build` into `--out` (default `site/`). Replace `llmwiki export all` with `llmwiki build`. The library module `llmwiki.exporters` (`export_all`, …) remains — only the standalone CLI entry point is removed.
- **`llmwiki reindex` is gone.** Catalog reconciliation (`wiki/index.md` ↔ pages on disk) runs inside `sync`, after a sources `synth` pass that actually wrote pages, after candidate **harvest** when stubs are written, and after `candidates promote|merge|discard` (#101). Idle sync/synth with nothing new are not the path to clean the catalog after review — use the candidates consume actions. After unrelated hand-edits to `wiki/`, `llmwiki sync --no-auto-build` still reconciles; then `llmwiki lint --rules index_sync` to verify. The library module `llmwiki.reindex` (`reindex_wiki`, `plan_reindex`) remains for internal callers.
- **`sync` always reconciles `wiki/index.md`.** Reconciliation used to run only inside the auto-build branch; it now runs after every successful `sync` regardless of `--no-auto-build`, so a sync-only workflow can't drift the catalog between builds.
- **`llmwiki all` pipeline order** — `[sync?]` → `[synthesize?]` → `build` → `[graph?]` → `lint`. Optional `--with-sync` converts new agent sessions (auto-build off — `all` builds next), refreshes the synth-pending backlog, and reconciles the catalog. Optional `--with-synth` fills `wiki/sources/` from `raw/`. `build` already calls `export_all`, so there is no separate export step. `graph` is skipped with `--skip-graph`.

```bash
llmwiki all                              # build → graph → lint
llmwiki all --with-sync --with-synth     # sync → synthesize → build → graph → lint
llmwiki all --strict                     # exit 2 on any lint warning
```

- **`llmwiki all` no longer self-deadlocks.** It used to acquire the pipeline lock and then dispatch to `cmd_build` / `cmd_sync` / `cmd_synthesize`, each of which tried to acquire the same non-reentrant lock again and hung. `run_pipeline` now takes the lock exactly once and calls the library functions directly (`convert_all`, `synthesize_new_sessions`, `build_site`, …). No CLI or config change is needed — `llmwiki all` just completes instead of hanging.
- **`llmwiki watch`** — near-real-time maintain: polls agent session stores and runs sync → synthesize → build when a session finishes (turn-complete gating where the adapter supports it). Restores the v1.2.0-removed daemon as a focused maintain loop; stdlib only, no `watchdog` dep.
- **`llmwiki install-automation`** — interactive setup for OS schedulers (systemd / launchd / Task Scheduler), optional agent hooks, and synth backend; writes automation status for the site Home panel. Non-interactive flags exist; `./setup.sh` is an alias.

Index reconciliation behaviour (#71) is unchanged — existing entries stay verbatim; dead links drop; `(count)` headings refresh.

## Unreleased — lint: `--include-llm` removed (#72)

`llmwiki lint --include-llm` is gone. The flag never called an LLM (no callback was wired; the three stub rules never invoked one). Scripts that pass it will fail with `unrecognized arguments: --include-llm` — drop the flag.

`contradiction_detection`, `claim_verification`, and `summary_accuracy` now always run with the other structural rules. `contradiction_detection` no longer flags filler `## Contradictions` sections (`None identified.`, `n/a`, and similar synthesis boilerplate).

Python callers of `run_all(..., include_llm=…, llm_callback=…)` still work — those kwargs are ignored.

## v1.5.0 — Analytics layout + CallMcpTool migration

After upgrading the engine, rebuild the vault site so Analytics picks up the new section order and heatmaps:

```bash
llmwiki build --vault /path/to/vault
# or, when vault.default_path is already configured:
llmwiki build
```

`build` also one-shot backfills `synth.pipeline` in `llmwiki-state.json` / `llmwiki-state.js` when that key is missing (state last written by v1.4.0). That fills the Home **State** widget without a separate `synthesize --estimate`. The refresh is local-only (no API / no tokens) and runs only on a shape mismatch — later builds skip it once the snapshot exists. Sync / add / estimate still refresh the snapshot when content changes.

**Optional:** expand `CallMcpTool` entries in already-synced `raw/sessions/*.md` when the originating agent session file still exists:

```bash
llmwiki migrate-tools-used --vault /path/to/vault --dry-run
llmwiki migrate-tools-used --vault /path/to/vault
llmwiki build --vault /path/to/vault
```

When the origin store is gone (TTL / deleted sessions), rows are skipped safely — the migrator never invents MCP tool names. Prefer this over `sync --force` for the same TTL reasons as other raw rewrites: agent transcripts are usually retained only ~30 days, so force re-convert often has nothing left to read.

See [`reference/state-persistence.md`](reference/state-persistence.md) for how usage logs, rollup, daily series, and state file relate.
