---
title: "Upgrade guide"
type: navigation
docs_shell: true
---

# Upgrade guide

How to upgrade between `llmwiki` releases.  Most releases are drop-in (`pip install -U llmwiki` or `brew upgrade llmwiki`) — this page documents the exceptions: schema migrations, config changes, and behaviour flips that affect what happens on your next `sync`.

The canonical per-release detail is [CHANGELOG.md](https://github.com/Pratiyush/llm-wiki/blob/master/CHANGELOG.md) — this guide focuses on "what might break".

## Unreleased — Analytics layout + CallMcpTool migration

After upgrading the engine, rebuild the vault site so Analytics picks up the new section order and heatmaps:

```bash
llmwiki build --vault /path/to/vault
# or, when vault.default_path is already configured:
llmwiki build
```

**Optional:** expand `CallMcpTool` entries in already-synced `raw/sessions/*.md` when the originating agent session file still exists:

```bash
llmwiki migrate-tools-used --vault /path/to/vault --dry-run
llmwiki migrate-tools-used --vault /path/to/vault
llmwiki build --vault /path/to/vault
```

When the origin store is gone (TTL / deleted sessions), rows are skipped safely — the migrator never invents MCP tool names. Prefer this over `sync --force` for the same TTL reasons as other raw rewrites: agent transcripts are usually retained only ~30 days, so force re-convert often has nothing left to read.

See [`reference/state-persistence.md`](reference/state-persistence.md) for how usage logs, rollup, daily series, and state file relate.

## Unreleased — index cwd restore + encoded-path redaction (#56)

**For AI agents maintaining a user's vault:** after the user upgrades `llm-wiki` (pull / `pip install -U` / brew), fix **their** vault — not the llm-wiki git clone. The engine change alone does not rewrite `site/` or `raw/`.

### Required: rebuild the site

```bash
llmwiki build --vault /path/to/their/vault
# or, if vault.default_path is already set in that checkout's config.json:
llmwiki build
```

That regenerates `site/projects/index.html` and `site/sessions/index.html` with restored local cwds (and a **Cwd** column on the sessions table).

**If you skip the rebuild** (engine updated, old `site/` left as-is):

| Symptom | Why |
|---|---|
| `projects/index.html` still mixes `/Users/USER/…` (or `/home/USER/…`) with real paths | Stale HTML from before restore/autodetect fixes |
| Session detail shows a usable `cd … && claude --resume …`, but the sessions index does not | Index never restored paths until #56; old build has no Cwd column |
| Descriptions on the sessions table still contain `…/USER/…` | Same — restore runs at **build** time |
| Grep checks from #56 stay non-zero (`grep -c '/Users/USER/' site/sessions/index.html`) | Expected until rebuild |

Nothing in `raw/` or `wiki/` is harmed by skipping rebuild; only the browsable site stays wrong / inconsistent with session heroes.

### Optional: deterministic raw/ redaction rewrite (no LLM)

#56 also teaches convert to rewrite dash-encoded agent-store segments
(`~/.claude/projects/-Users-<name>-…` → `-Users-USER-…`). **New** syncs do that automatically.

Existing `raw/sessions/*.md` are immutable during normal sync. For a vault that stays private and local, leaving old `raw/` alone is fine — site restore already shows usable local cwds after rebuild.

When the user intends to **publish or share `raw/`** (or otherwise wants the `USER` placeholder complete in every path shape already on disk), run the **deterministic** migrator — it rewrites path strings in place, does **not** call the LLM, does **not** enqueue `synthesize`, and does **not** touch `wiki/`:

```bash
# preview
llmwiki migrate-raw-redaction --vault /path/to/their/vault --dry-run
# or: python3 scripts/migrate_raw_encoded_username.py --vault … --dry-run

llmwiki migrate-raw-redaction --vault /path/to/their/vault
llmwiki build --vault /path/to/their/vault
```

**Do not** use `llmwiki sync --force` / re-convert from `~/.claude/projects/` or Cursor session folders for this:

- Agent stores usually retain transcripts only ~**30 days** (Claude Code retention; Cursor similar). Older sessions in `raw/` often have **no** source file left to re-convert from — force-sync silently skips or fails those rows while still looking like “migration work”.
- Force-sync is the wrong tool anyway: agents may follow it with `synthesize` / queue digest and **burn LLM tokens** rewriting wiki pages that did not need to change. The path-string rewrite above is enough.

**If you skip the raw migrator** (normal for private vaults):

- Day-to-day browsing and resume: **unaffected** after rebuild.
- Old `raw/` rows that already contain `-Users-<real-username>-…` next to a redacted `/Users/USER/…` prefix keep that incomplete masking until `migrate-raw-redaction` (or a future sync of still-present sources). That is a redaction-contract gap for publish/share workflows, not data escaping a private vault.

### Config note

If root `config.json` copied the examples placeholder `"redaction": { "real_username": "" }`, #56 re-autodetects after overlay so restore works again. No manual config edit required unless the user intentionally disabled username redaction.

## Downgrading is guarded (#29)

Pointing an **older** checkout at a vault a **newer** engine wrote used to silently reconvert everything under the old slug scheme, duplicating `raw/`. As of #29, `sync` refuses to run when the vault's `llmwiki-state.json` was written by a newer `meta.schema_version`, or is present but unreadable:

```
error: <vault>/llmwiki-state.json: state file was written by a newer llmwiki
(schema_version=2 > 1). Upgrade llmwiki, or pass --force-resync to reconvert
from scratch ...
```

The fix is to **upgrade the engine** to match the vault. Only pass `sync --force-resync` if you genuinely want a full reconvert from scratch (it implies `--force` and may duplicate an already-populated `raw/`). This guard protects the newer→older direction; the older engine that lacks it still can't see the unified file, so keep engines at or ahead of the version that last wrote the vault.

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

Rebuild the site after upgrading so the Home page loads `../llmwiki-state.js`.

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
llmwiki synthesize --vault /path/to/vault
```

Stub pages left behind by the dummy backend count as **unsynthesized** backlog (#24): `llmwiki queue status` reports them under `unsynth_total`, `llmwiki lint` flags them with the `stub_source_pages` rule, and `llmwiki synthesize` refills them with a real backend.

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

## v1.2.0 — first stable on the 1.x line

**Released: 2026-04-25.**

### Install changes

- **PyPI distribution name is `llm-notebook`** — the `llmwiki` name was taken on PyPI. The Python module + CLI command stay `llmwiki`, only the `pip install` line changes:
  ```bash
  pip install llm-notebook        # was: pip install llmwiki
  llmwiki --version               # → 1.2.0  (CLI name unchanged)
  python3 -c "import llmwiki"     # still works (import name unchanged)
  ```

### Removed CLI subcommands

The CLI was slimmed in #362. If you scripted any of these, replace as noted:

- `llmwiki schedule` — removed. Schedule `llmwiki sync` directly via your OS's job runner (launchd / systemd / Task Scheduler).
- `llmwiki install-skills` — removed. Manually copy `.claude/commands/wiki-*.md` into `~/.claude/commands/` for global availability.
- `llmwiki check-links` — removed. Use the GitHub Actions link-check workflow instead.
- `llmwiki watch`, `llmwiki manifest`, `llmwiki link-obsidian`, `llmwiki export-obsidian`, `llmwiki export-marp`, `llmwiki export-qmd`, `llmwiki eval` — also removed.
- `llmwiki export marp` is the new path for Marp slide export.

### Removed adapters

`jira_adapter`, `meeting`, `pdf` were removed in #363. If you depended on any of them, pin v1.1.0-rc8 until you migrate.

### Demo data correctness

`user_messages` / `tool_calls` counts on the 8 demo session files were 2–10× higher than the body actually contained. The values are now recomputed from body content. Two new lint rules (`#16 frontmatter_count_consistency`, `#17 tools_consistency`) prevent regression.

### `sync --force` no longer drops colliding sessions

If you ran `sync --force` against a corpus where two sources had the same canonical filename (rare but real on large corpora), one of them was silently overwritten. Fix: per-run filename tracking now disambiguates regardless of `--force`. Affected ~200 of 495 sessions on a real corpus we tested.

### New: `llmwiki all`

One-shot pipeline runner for CI:

```bash
llmwiki all                  # build → graph → export → lint
llmwiki all --strict         # exit 2 on any lint warning
```

### Schema migrations

None. JSON sibling files now correctly emit `int` and `bool` types for `user_messages` / `tool_calls` / `is_subagent` (were strings); any downstream that string-compared `is_subagent == "false"` now needs `is_subagent is False`.

## v1.1.0-rc5

**Released: 2026-04-21.**

### New behaviour

- **Session transcripts strip project-local file refs.** Anchors pointing at `tasks.md`, `user_profile.md`, `settings.gradle.kts`, `.kiro/…`, `/Users/…`, etc. are unwrapped into inline `<span class="session-ref dead-link">` — the filename stays visible but the anchor doesn't 404. No action required.

- **`README.md` and `CONTRIBUTING.md` now compile as site pages.** `site/README.html` and `site/CONTRIBUTING.html` ship alongside `changelog.html`. Link rewriter routes to the compiled page instead of GitHub for these two files.

- **`/wiki-synthesize` slash command** — wraps `llmwiki synthesize` with natural-language flags ("estimate cost", "dry run", "force"). Copy `.claude/commands/wiki-synthesize.md` into `~/.claude/commands/` for global availability. (`llmwiki install-skills` was removed in v1.2.0; manual copy is the supported path.)

- **Dual-mode docs landing pages.** `docs/modes/api/` and `docs/modes/agent/` exist as skeletons; the actual API / Agent backends ship with #315 / #316.

### Schema migrations

None. Fully backwards-compatible with rc4 state files.

### Breaking

None.

## v1.1.0-rc4

**Released: 2026-04-20.**

### New behaviour

- **Obsidian is opt-in now.** Past versions fired the Obsidian adapter on every `sync` by default. If your workflow relied on that, add this to `sessions_config.json`:

  ```json
  { "obsidian": { "enabled": true } }
  ```

  Context: [#326](https://github.com/Pratiyush/llm-wiki/issues/326). Runs as of rc3; surfaced in `llmwiki adapters` column `will_fire`.

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

See the [release notes](https://github.com/Pratiyush/llm-wiki/releases/tag/v1.1.0-rc3) for the full rc3 gap-sweep bundle. No migration required.

## v1.0.0 → v1.1.0-rc1

Config: `synthesis.backend` now accepts `"ollama"` in addition to the default `"dummy"`. See `docs/reference/prompt-caching.md` for the ollama setup.

`wiki/candidates/` directory is new — created automatically by ingest when it sees a brand-new entity/concept. Triage with `/wiki-candidates` (renamed from `/wiki-review` in rc3).

## Older versions

Pre-v1.0 milestones shipped under internal sprint tags. Upgrade from v0.9.x to v1.0.0 in one step — no intermediate migration required. If you're on a pre-0.9 build, start fresh: `llmwiki init` in a new tree and re-run `sync`.
