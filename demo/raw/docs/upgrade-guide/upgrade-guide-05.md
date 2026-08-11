---
title: "Upgrade guide (part 5/7: v1.5.0 — index cwd restore + encoded-path redaction (#56))"
slug: upgrade-guide-05
project: upgrade-guide
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/UPGRADING.md"
content_sha256: 1edde415b51f8cacf9995db66240407df90211d0b78f27234d578b0f7b9b29e3
---

> Part 5 of 7 of **Upgrade guide** — v1.5.0 — index cwd restore + encoded-path redaction (#56).

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
