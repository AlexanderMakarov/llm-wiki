---
title: "CLI reference (part 11/19: page-kinds — retype pages off the removed question/comparison kinds)"
slug: cli-reference-11
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-10-01
source: "docs/reference/cli.md"
content_sha256: 8c1258c0faddb3eb988de6c7870bdada2b983cd07f6b325b78b35e680759efeb
---

> Part 11 of 19 of **CLI reference** — page-kinds — retype pages off the removed question/comparison kinds.

```bash
python3 -m llmwiki migrate tools-used --vault /path/to/vault --dry-run
python3 -m llmwiki migrate tools-used --vault /path/to/vault
```

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `raw/sessions/`. |
| `--dry-run` | Report files that would change; write nothing. |
| `--config PATH` | Optional `sessions_config.json` override (record filters). |

Origin resolution prefers the vault's `llmwiki-state.json` sync keys (`adapter::home-relative-path`), then falls back to a glob under the adapter session store by `sessionId`. Claude Code JSONL is fully supported; Cursor and other non-JSONL stores work when the state key or glob resolves a readable origin path. Missing origins leave `CallMcpTool` entries intact for `wiki_adoption` body fallback.

### `page-kinds` — retype pages off the removed question/comparison kinds

`llmwiki/schema.py` lists five knowledge kinds — `source`, `entity`, `concept`, `project`, `synthesis`. A hand-written page declaring `type: question` or `type: comparison` is a `frontmatter_validity` **error**, and this migration clears it: each such page is retyped to `concept` and moved into `wiki/concepts/` **keeping its filename**, then `wiki/questions/` and `wiki/comparisons/` lose their `_context.md` and are pruned once empty.

Inbound links are left alone on purpose. `[[wikilinks]]` resolve by filename, never by folder, so a page that keeps its name keeps every inbound link and no referring page needs editing.

Two safety rules: a page whose filename is already taken in `wiki/concepts/` is retyped where it stands and reported as a collision rather than overwriting anything, and a removed folder still holding other content is left in place and reported rather than deleted. A vault with no removed-kind page prints `nothing to migrate` and exits 0 without writing.

Implementation: `llmwiki/migrate_page_kinds.py` — in the package rather than under `scripts/`, so it runs from a pip install with no checkout. After migrating, rebuild so `site/` picks up the new locations: `llmwiki build --vault PATH`.

```bash
python3 -m llmwiki migrate page-kinds --vault /path/to/vault --dry-run
python3 -m llmwiki migrate page-kinds --vault /path/to/vault
python3 -m llmwiki lint --vault /path/to/vault --rules frontmatter_validity
```

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `wiki/`. |
| `--dry-run` | Report what would change; write nothing. |

Idempotent: a second run finds nothing to migrate. On a run that changed something the command reconciles `wiki/index.md` and appends `## [YYYY-MM-DD] migrate | page kinds` to `wiki/log.md`.

### `topic-kinds` — stamp entity/concept kinds onto older source Connections

Older source summaries often list `[[wikilinks]]` under `## Connections` without an `(entity)` or `(concept)` kind. After the one-pass topic shape, those pages look like they still need a full rewrite. This offline migration stamps known kinds from pages already under `wiki/entities/`, `wiki/concepts/`, and the matching `wiki/candidates/` folders — no language model, no network call, and `raw/` is never written.

Only the Connections section is edited. Nested `fact:` lines, Key Claims, Key Quotes, and frontmatter stay byte-identical. Names that exist as both an entity and a concept are ambiguous: those bullets are skipped and listed in the report rather than guessed. Already-kinded bullets are left alone.

A successful non-dry-run that stamps at least one page writes `.llmwiki-topic-kinds-stamped.json` at the vault root (vault-local machine state — not for git) so you can later force-resynthesize exactly those sources if you want fact lines. The same apply (and a re-run over already-clear pages) upserts synth state for every raw session/doc whose wiki target is rewrite-clear — including when many raw files share one synth filename — so plain `llmwiki synth` / `--estimate` will not re-bill them. The report always states that zero facts were derived.

Implementation: `llmwiki/migrate_topic_kinds.py`. Stamping clears the rewrite-needed flag when at least one resolvable kind lands; it does not invent facts. Use `llmwiki synth --force --path …` on stamped pages if you want fact lines afterwards.

```bash
python3 -m llmwiki migrate topic-kinds --vault /path/to/vault --dry-run
python3 -m llmwiki migrate topic-kinds --vault /path/to/vault
```

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `wiki/`. |
| `--dry-run` | Report what would change; write nothing (no stamped JSON either). |

Idempotent: a second run finds nothing to stamp and prints `nothing to migrate: no connection lines need topic kinds`. Preview with `--dry-run` before applying.

### `wikilink-titles` — add title display text to bare resolving wikilinks

Wiki search and the `page_findability` lint key on page **title** (frontmatter `title`), not on slug/filename. Bare `[[OpenAI]]` links still resolve correctly, but their visible text is the slug stem. This offline migration rewrites resolving bare `[[slug]]` links to `[[slug|Title]]` using titles already on disk under `wiki/` — no language model, no network call, and `raw/` is never written.

Section anchors are preserved (`[[Page#Section]]` → `[[Page#Section|Title]]`). Case/punctuation variants that uniquely match a page under the same `norm_page_key` fold as `link_integrity` / harvest (e.g. `[[LLM-Wiki]]` when the page slug is `llm-wiki`) are rewritten to the **canonical slug** plus title (`[[llm-wiki|…]]`). Links that already carry display text (`[[slug|alias]]`), unresolved or ambiguous-norm targets, true aliases (written name is a different page identity), and titles that would break wikilink syntax (contain `|` or `]]`) are skipped and counted in the report. Fenced/example `[[slug]]` tokens are rewritten the same as prose — skim `--dry-run` changed pages before applying.

Implementation: `llmwiki/migrate_wikilink_titles.py`. Cosmetic/readability only — not required for lint green once findability is title-only. Rebuild the site after applying if you want HTML to show the new display text: `llmwiki build --vault PATH`.

```bash
python3 -m llmwiki migrate wikilink-titles --vault /path/to/vault --dry-run
python3 -m llmwiki migrate wikilink-titles --vault /path/to/vault
```

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `wiki/`. |
| `--dry-run` | Report what would change; write nothing. |

Idempotent: a second run finds nothing to rewrite and prints `nothing to migrate: no bare slug wikilinks need title display text`. Preview with `--dry-run` before applying.

### `discarded-topic-links` — unlink or redirect links to discarded candidates
