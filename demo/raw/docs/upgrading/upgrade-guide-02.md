---
title: "Upgrade guide (part 2/5: 2.0.0 — static site, pipeline, and MCP (from v1.5.0))"
slug: upgrade-guide-02
project: upgrading
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-07
source: "docs/UPGRADING.md"
content_sha256: 79fd93bf709421f37aa05c27a435cd601ed7f0443274f4ab0c06dc082831e232
---

> Part 2 of 5 of **Upgrade guide** — 2.0.0 — static site, pipeline, and MCP (from v1.5.0).

## 2.0.0 — static site, pipeline, and MCP (from v1.5.0)

### Read this first

1. **Re-run `llmwiki install-automation`** if you schedule `llmwiki all` — bare `all` now includes `sync` and `synth`. With a real synthesis backend, add `--no-synth` (or `--no-sync --no-synth`) to keep the old behaviour (#156).
2. **Run `llmwiki configure-sources`** after upgrade if you use Cursor Agent CLI, OpenClaw, Codex, or other non-Claude stores (#182).
3. **Stop using `llmwiki serve`** — open `<vault>/site/index.html`. Candidate decisions on `/candidates.html` execute via `llmwiki candidates apply --vault <vault> --actions -` (#109).
4. **Update MCP clients** — replace `wiki_entity_search` with `wiki_search`; parse `wiki_lint` as `llmwiki lint --json` (#102, #150).
5. **Run migrations when applicable:**
   - `llmwiki migrate page-kinds --vault <vault>` if you have `wiki/questions/` or `wiki/comparisons/`
   - `llmwiki migrate topic-kinds --vault <vault>` for #147 catch-up on older source pages (#174)
   - `llmwiki migrate broken-provenance --vault <vault>` after Cursor CLI re-sync left broken `source_file` hops (#180)
6. **Re-sync Cursor Agent CLI** (`llmwiki sync --force` or targeted re-convert) so `is_headless`, `sessionId`, and timestamps are correct (#180).
7. **Rebuild the site** — `llmwiki build --vault <vault>` refreshes vendored assets, topic pages, pipeline widgets, and provenance links.

### Breaking changes

- **`llmwiki serve` / `POST /api/candidates` / `/wiki-serve` gone** — static files + CLI review (#109).
- **`llmwiki all` default pipeline** is `sync` → `synth` → `build` → `graph` → `lint` (#156).
- **Lint default on `all`** is `--lint-fail never` (report only) (#156).
- **MCP `wiki_lint` JSON shape** matches CLI (**BREAKING**); filter `issues` by `rule`; old keys `orphans` / `broken_links` are gone (#150).
- **`wiki_entity_search` removed** — `wiki_search(term, kind=…, format=…)` (#102).
- **`llmwiki consolidate-topics` is gone** (#147 / #112) — known-names prepare is part of `synth`.
- **`synth --allow-unclassified` removed** (#102).
- **`type: question` / `type: comparison` invalid** — `migrate page-kinds` (#109).
- **`entity_consistency` lint rule removed**; unknown `--rules` names fail (#102).

### Session sources and adapters

- Bare **`llmwiki sync` loads every enabled ingest-ready adapter** whose store exists; `enabled: false` is honoured (#182).
- **Obsidian and ChatGPT export stay opt-in** (`adapters.*.enabled: true`).
- **`filters.exclude_headless` (default on)** skips automated launches for every coding-agent adapter; re-sync to classify older Cursor CLI rows (#180).
- **Cursor IDE Composer ingest works via bare `llmwiki sync` after `configure-sources` Enable** (or `llmwiki sync --adapter cursor_ide`) (#2 / #192) — parses global `state.vscdb`. Set `filters.since` / `adapters.cursor_ide.since` (or pass `--since`) before the first large run. Alias `--adapter cursor` / legacy `adapters.cursor` still resolve. Cursor Agent CLI remains `cursor_cli`.

### Synthesis and candidates

- Prefer **`llmwiki synth`** — `synthesize` is removed (#112); use `--sources-only` when you want the old sources-only default (#90).
- **Next `synth` rewrites source pages** lacking parseable topic bullets once (#147); optional `migrate topic-kinds` for cheap catch-up (#174).
- **Promote needs no LLM** — empty Key Facts copy from source `fact:` bullets; `rewrite-key-facts` still needs a backend (#147, #103).
- **`wiki/archive/` is cold storage** — discarded candidates stay resolved in harvest; first lint after upgrade may report more broken links (#140).
- **`synth --estimate` Already synthesized** follows synth state, not pages-on-disk alone (#163).
- **Ctrl+C during `synth`** exits 130 after recording pages that reached disk (#145).

### Site and review

- **Open `site/index.html`** (or `file://`) — highlight.js and vis-network are vendored (#109, #127).
- **`llmwiki build --local-root PATH`** for portable published paths (#109).
- **`candidates apply` rebuilds `site/`** unless `--no-rebuild` (#109).
- **`llmwiki export` / `llmwiki reindex` CLI removed** — use `build`; catalog reconciles on `sync` / `synth` / candidate actions (#82).

### Lint and MCP

- **`<vault>/llmwiki.json`** — `lint.disabled_rules` to opt out of named checks (#150).
- **`llmwiki lint --min-refs N`** and **`llmwiki all --min-refs N`** share harvest threshold (default 3) (#150).
- **`llmwiki lint --fail-on-warnings`** for warning-severity gate (#150).
- **`llmwiki lint --include-llm` removed** — drop the flag from scripts (#72).
- **`provenance_integrity`** may report new errors on broken `sources:` / `source_file:` chains (#122).

### Automation

- **`install-automation`** plain-language wizard, cron `--schedule`, `--job {ingest,maintain}` (#156).
- **`--with-sync` / `--with-synth` still parse** but are inert — use `--no-sync` / `--no-synth` to opt out (#156).
- **`--profile {A,B,C}` deprecated** — `A`→ingest, `B`/`C`→maintain; `--hour`/`--minute` superseded by `--schedule`.
- **`llmwiki install-agent-kit --dest PATH`** replaces manual `.claude/commands` copy and `.claude-plugin/` (#109).

### No action needed

- **`/vs/` removed** — never wired into normal builds (#138).
- **Honest Home pipeline counts** — eligible sources and On disk column (#81).
- **Estimate Candidates** labelled pre-run state, not a harvest forecast (#113).
- **`entity_type` on existing pages** — inert metadata; optional re-stamp `wiki/projects/` to `type: project` (#102).

## v1.5.0 — Analytics layout + CallMcpTool migration

After upgrading the engine, rebuild the vault site so Analytics picks up the new section order and heatmaps:

```bash
llmwiki build --vault /path/to/vault
# or, when vault.default_path is already configured:
llmwiki build
```

`build` also one-shot backfills `synth.pipeline` in `llmwiki-state.json` / `llmwiki-state.js` when that key is missing (state last written by v1.4.0). That fills the Home **State** widget without a separate `synth --estimate`. The refresh is local-only (no API / no tokens) and runs only on a shape mismatch — later builds skip it once the snapshot exists. Sync / add / estimate still refresh the snapshot when content changes.

**Optional:** expand `CallMcpTool` entries in already-synced `raw/sessions/*.md` when the originating agent session file still exists:

```bash
llmwiki migrate tools-used --vault /path/to/vault --dry-run
llmwiki migrate tools-used --vault /path/to/vault
llmwiki build --vault /path/to/vault
```

When the origin store is gone (TTL / deleted sessions), rows are skipped safely — the migrator never invents MCP tool names. Prefer this over `sync --force` for the same TTL reasons as other raw rewrites: agent transcripts are usually retained only ~30 days, so force re-convert often has nothing left to read.

See [`reference/state-persistence.md`](reference/state-persistence.md) for how usage logs, rollup, daily series, and state file relate.
