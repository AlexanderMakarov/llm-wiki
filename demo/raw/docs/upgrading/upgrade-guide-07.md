---
title: "Upgrade guide (part 7/8: v1.3.0 — consolidated 1.2.x patch roll-up)"
slug: upgrade-guide-07
project: upgrading
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/UPGRADING.md"
content_sha256: c3075657888a257c11c0c2658857c42e4c57a45b7e70f26eac2aec1c3b5b4614
---

> Part 7 of 8 of **Upgrade guide** — v1.3.0 — consolidated 1.2.x patch roll-up.

## v1.3.0 — consolidated 1.2.x patch roll-up

**Released: 2026-04-26.**

### Summary

Drop-in upgrade from any 1.2.x. v1.3.0 consolidates 38 in-tree patch versions (1.2.1 → 1.2.38) under one minor release tag — no breaking API changes, no schema migrations, no config changes.

```bash
pip install -U llm-wiki-plus  # → 1.3.0
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

## v1.2.0 — first stable on the 1.x line

**Released: 2026-04-25.**

### Install changes

- **PyPI distribution name is `llm-wiki-plus`** — `llmwiki` belongs to another author, and PyPI's name-similarity rule also rejects `llm-wiki` as too close to it, so the distribution carries a `-plus` suffix. The Python module + CLI command stay `llmwiki`, only the `pip install` line changes:
  ```bash
  pip install llm-wiki-plus       # was: pip install llmwiki
  llmwiki --version               # → 1.2.0  (CLI name unchanged)
  python3 -c "import llmwiki"     # still works (import name unchanged)
  ```
  Releases before the rename documented this distribution as `llm-notebook`; that name was never published for this fork and no longer appears in install instructions (#210).

### Removed CLI subcommands

The CLI was slimmed in #362. If you scripted any of these, replace as noted:

- `llmwiki schedule` — removed. Schedule `llmwiki sync` directly via your OS's job runner (launchd / systemd / Task Scheduler).
- `llmwiki install-skills` — removed. Manually copy `.claude/commands/wiki-*.md` into `~/.claude/commands/` for global availability.
- `llmwiki check-links` — removed. Use the GitHub Actions link-check workflow instead.
- `llmwiki watch`, `llmwiki manifest`, `llmwiki link-obsidian`, `llmwiki export-obsidian`, `llmwiki export-marp`, `llmwiki export-qmd`, `llmwiki eval` — also removed. (`llmwiki eval` was never a live CLI — structural scoring never shipped; use `llmwiki lint` for wiki quality.)

### Removed adapters

`jira_adapter`, `meeting`, `pdf` were removed in #363. If you depended on any of them, pin v1.1.0-rc8 until you migrate.

### Demo data correctness

`user_messages` / `tool_calls` counts on the 8 demo session files were 2–10× higher than the body actually contained. The values are now recomputed from body content. Two new lint rules (`#16 frontmatter_count_consistency`, `#17 tools_consistency`) prevent regression.

### `sync --force` no longer drops colliding sessions

If you ran `sync --force` against a corpus where two sources had the same canonical filename (rare but real on large corpora), one of them was silently overwritten. Fix: per-run filename tracking now disambiguates regardless of `--force`. Affected ~200 of 495 sessions on a real corpus we tested.

### New: `llmwiki all`

One-shot pipeline runner for CI:

```bash
llmwiki all                  # build → graph → lint
llmwiki all --strict         # exit 2 on any lint warning
```

### Schema migrations

None. JSON sibling files now correctly emit `int` and `bool` types for `user_messages` / `tool_calls` / `is_subagent` (were strings); any downstream that string-compared `is_subagent == "false"` now needs `is_subagent is False`.

## v1.1.0-rc5

**Released: 2026-04-21.**

### New behaviour

- **Session transcripts strip project-local file refs.** Anchors pointing at `tasks.md`, `user_profile.md`, `settings.gradle.kts`, `.kiro/…`, `/Users/…`, etc. are unwrapped into inline `<span class="session-ref dead-link">` — the filename stays visible but the anchor doesn't 404. No action required.

- **`README.md` and `CONTRIBUTING.md` now compile as site pages.** `site/README.html` and `site/CONTRIBUTING.html` ship alongside `changelog.html`. Link rewriter routes to the compiled page instead of GitHub for these two files.

- **`/wiki-synthesize` slash command** — wraps `llmwiki synth --sources-only` (prefer `/wiki-synth`). Copy via `llmwiki install-agent-kit --dest PATH`. (`llmwiki install-skills` was removed in v1.2.0.) (retired in #214 — use `/wiki-synth`)

- **Dual-mode docs landing pages.** `docs/modes/api/` and `docs/modes/agent/` exist as skeletons; the actual API / Agent backends ship with #315 / #316.

### Schema migrations

None. Fully backwards-compatible with rc4 state files.

### Breaking

None.
