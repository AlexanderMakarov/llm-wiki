---
title: "Upgrade guide (part 3/8: Unreleased — Claude control tags + session TOC (#229))"
slug: upgrade-guide-03
project: upgrading
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/UPGRADING.md"
content_sha256: c3075657888a257c11c0c2658857c42e4c57a45b7e70f26eac2aec1c3b5b4614
---

> Part 3 of 8 of **Upgrade guide** — Unreleased — Claude control tags + session TOC (#229).

## Unreleased — Claude control tags + session TOC (#229)

No migration. After upgrade:

- **Re-convert Claude sessions if tags leaked into `raw/`:** `llmwiki sync --force` then `llmwiki build`. Convert now strips Claude Code local-command / slash-command envelopes (`local-command-caveat`, `command-name`, …) and background-task `[SYSTEM NOTIFICATION …]` / `<task-notification>` blocks so they never become `description:` or Conversation prose. Non-empty `<command-args>` are kept on the slash label (`/implement-feature https://…`); injected command/skill markdown dumps are skipped for `description:`; user-prompt newlines become markdown hard breaks. Already-written `raw/sessions/*.md` keep the old text until force-synced. (Under #249, `description:` may still select a scored slash turn when it outranks prose.)
- **Session TOC:** rebuild alone is enough for layout — the “On this page” nav is sticky in a Raw-style left column below the hero (not fixed over the title band), appears when the article has ≥2 headings, and uses the same `max-width: 860px` collapse as Raw.

## 2.3.0 — Home Pipeline state stamps + Automation panel shrink (#234)

No migration. After upgrade + rebuild:

- **Pipeline state** on Home: Eligible sources + Knowledge tables stay clean; **Timeline** holds Last sync / Last synth / Last build / Last lint. A lint-error note appears under the Candidates table when the last lint recorded an error.
- **Automation** is settings-only (shorter): no stage timestamps, no lint-fail reminder, no installer Updated line; short Synth backend line (spend hint); Agent hooks and Watch on separate lines. Maintain wording: site refreshes once after summarization.
- **Standalone `llmwiki lint`** updates `llmwiki-state.json` and copies `site/llmwiki-state.js` — it does not rewrite HTML. `--lint-fail` on `all` does not undo the site built earlier in that run.
- **`--fail-fast`** still stops the full pipeline at the first failure; without it, later stages (including build) continue after an earlier failure.

## 2.3.0 — Cursor Agent CLI synthesis backend (#230)

`synthesis.backend` accepts `"cursor_cli"`: shells out to Cursor Agent CLI (`agent` / `cursor-agent` on `$PATH`) the same way `claude` uses `claude -p`. Defaults: model `composer-2.5`, timeout 180s. Settings live under nested `synthesis.cursor_cli` (and nested `synthesis.claude` / `synthesis.ollama`); flat `claude_*` keys still work as fallbacks.

- **One-run override:** `llmwiki synth --backend cursor_cli` (also honoured by `--check` / `--estimate`) — does not write `config.json`.
- **Not session ingest:** this is the synthesis *generator*. The contrib adapters `cursor_cli` (Agent CLI chats) and `cursor_ide` (IDE Composer) only convert transcripts into `raw/`.
- **Cost estimates:** `--estimate` prices Cursor models from the packaged `model_pricing.csv` (Cursor-published Composer / Grok rates + `agent --model` aliases). No live Agent CLI price fetch. Stand-in rows (if any) are labeled in `source` / `notes`.
- **Overview:** `build --synthesize` follows the active backend; `dummy` / unavailable skips the overview LLM.
- **install-automation:** interactive backend prompt and `--synth-backend` accept `cursor_cli`.

## 2.2.0 — install from PyPI as `llm-wiki-plus` (#210)

The published distribution is **`llm-wiki-plus`** (`llmwiki` and `llm-wiki` are unavailable on PyPI). The import and CLI stay `llmwiki`.

```bash
pip install -U llm-wiki-plus
llmwiki --version   # → 2.2.0
```

Optional graph extra: `pip install 'llm-wiki-plus[graph]'`. Re-run `llmwiki install-agent-kit --dest PATH` after upgrade so retired slash commands (`/wiki-export-marp`, `/wiki-synthesize`) are pruned from an older kit install (#214). Prefer `/wiki-synth` (add sources-only when you want the old synthesize path).

## 2.1.0 — CLI help as a lifecycle map (#112)

`llmwiki --help` is grouped into six lifecycle sections. Command renames that affect scripts and muscle memory:

| Old name | Replacement |
|---|---|
| `synthesize` | `synth` (old default was sources-only; today's `synth` does sources + harvest unless you pass `--sources-only`) |
| `consolidate-topics` | gone — `synth` prepares known names at the start of each sources pass |
| `migrate-state` | `migrate state` |
| `migrate-raw-redaction` | `migrate raw-redaction` |
| `migrate-tools-used` | `migrate tools-used` |
| `migrate-page-kinds` | `migrate page-kinds` |
| `migrate-topic-kinds` | `migrate topic-kinds` |
| `migrate-broken-provenance` | `migrate broken-provenance` |

List migrations with `llmwiki migrate` or `llmwiki migrate --list`. Nothing runs until you pick a name. Prefer `--dry-run` first. The `/wiki-synthesize` slash alias is retired — `/wiki-synth` is the command, and `synth --sources-only` is the flag for the sources-only pass.

## 2.1.0 — durable sync lookback (#192)

Optional shared `filters.since` and per-adapter `adapters.<name>.since` (`YYYY-MM-DD`, or `"all"` to skip the date gate for one source). Unset still means unlimited history.

- **Set a lookback before enabling a long-retention store** so the first bare sync does not convert years of history. CLI `--since` still overrides for one run.
- **`llmwiki configure-sources`** asks shared start date first (Enter = today−30, or keep a stored date), then per source shows **Sessions · Earliest · In last 30 days** before Enable / path / start date. Enable means the source is on the next bare `sync` (Cursor IDE included). Skipped interviews invent no dates.
- **The next successful sync with a durable lookback** prunes that coding-agent adapter’s `sync.files` stamps older than the window (CLI `--since` does not GC; notes intake is not GC’d). Lookback-only skips are never remembered as done, so widening the date later can pick them up. GC does not delete `raw/` or queue/synth/quarantine/ops.
- **Cursor IDE registry name is `cursor_ide`** (was `cursor`) so it is distinct from `cursor_cli`. `--adapter cursor` and a legacy `adapters.cursor` config block still work. Prefer `adapters.cursor_ide` in new configs. Existing `sync.files` keys prefixed `cursor::` are rewritten to `cursor_ide::` on the next state load so Composer threads are not re-converted.
- **`llmwiki adapters` enabled column is yes/no** (will the next bare sync include this source). The old `active` column and `auto` / `explicit` / `off` labels are gone.
Keys and inheritance: [configuration-reference.md — Sync lookback](configuration-reference.md#sync-lookback).
