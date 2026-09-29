---
title: "Upgrade guide (part 5/8: v1.5.0 — Analytics layout + CallMcpTool migration)"
slug: upgrade-guide-05
project: upgrading
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/UPGRADING.md"
content_sha256: c3075657888a257c11c0c2658857c42e4c57a45b7e70f26eac2aec1c3b5b4614
---

> Part 5 of 8 of **Upgrade guide** — v1.5.0 — Analytics layout + CallMcpTool migration.

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

## v1.5.0 — index cwd restore + encoded-path redaction (#56)

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
llmwiki migrate raw-redaction --vault /path/to/their/vault --dry-run
# or: python3 scripts/migrate_raw_encoded_username.py --vault … --dry-run

llmwiki migrate raw-redaction --vault /path/to/their/vault
llmwiki build --vault /path/to/their/vault
```

**Do not** use `llmwiki sync --force` / re-convert from `~/.claude/projects/` or Cursor session folders for this:

- Agent stores usually retain transcripts only ~**30 days** (Claude Code retention; Cursor similar). Older sessions in `raw/` often have **no** source file left to re-convert from — force-sync silently skips or fails those rows while still looking like “migration work”.
- Force-sync is the wrong tool anyway: agents may follow it with `synth` / queue digest and **burn LLM tokens** rewriting wiki pages that did not need to change. The path-string rewrite above is enough.

**If you skip the raw migrator** (normal for private vaults):

- Day-to-day browsing and resume: **unaffected** after rebuild.
- Old `raw/` rows that already contain `-Users-<real-username>-…` next to a redacted `/Users/USER/…` prefix keep that incomplete masking until `migrate raw-redaction` (or a future sync of still-present sources). That is a redaction-contract gap for publish/share workflows, not data escaping a private vault.

### Config note

If root `config.json` copied the examples placeholder `"redaction": { "real_username": "" }`, #56 re-autodetects after overlay so restore works again. No manual config edit required unless the user wants username redaction, which needs `redaction.redact_username: true` (#253).
