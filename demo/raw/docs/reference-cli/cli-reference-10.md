---
title: "CLI reference (part 10/15: topic-kinds — stamp entity/concept kinds onto older source Connections)"
slug: cli-reference-10
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/reference/cli.md"
content_sha256: 186543f38f0258ea703f9ef68071d930f7135ea481068df5e5b46346e0f33e99
---

> Part 10 of 15 of **CLI reference** — topic-kinds — stamp entity/concept kinds onto older source Connections.

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

### `broken-provenance` — remap or clear hops to missing raw sessions

After a Cursor Agent CLI re-sync that used the filesystem stem `store` as `sessionId`, force-convert can leave wiki pages pointing at deleted `raw/sessions/…` paths while newer raw files exist under the same project slug (`cursor-<hash>`). This offline migration walks wiki pages that carry `source_file:` / `sources:` provenance and, when a hop targets a missing `raw/sessions/` file:

1. Parses the project slug from the missing path (for example `cursor-<hash>`).
2. Finds existing raw files whose names contain that project slug.
3. Restricts candidates to the **same calendar day** (`YYYY-MM-DD` prefix). Never remaps across days (that used to point every June stub at a single January session).
4. Remaps only among same-day **interactive** raw files: explicit `is_headless: false`, or legacy unmarked (no `is_headless` field — same eligibility rule as synth). When several remain, remaps to the uniquely closest HH-MM in that shortlist.
5. Otherwise clears the broken `source_file` (same-day headless-only pools, ambiguous closest-time ties, or no same-day interactive candidate) and drops matching `sources:` list aliases. Wiki pages themselves are never deleted. Never remaps to a row that is explicitly `is_headless: true`.

Implementation: `llmwiki/migrate_broken_provenance.py`. Preview with `--dry-run`. Prefer a Cursor Agent CLI re-sync first so raw filenames carry real chat dates and `is_headless` is stamped; unmarked legacy same-day files remain remap-eligible until then.

```bash
python3 -m llmwiki migrate broken-provenance --vault /path/to/vault --dry-run
python3 -m llmwiki migrate broken-provenance --vault /path/to/vault
```

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `wiki/` and `raw/`. |
| `--dry-run` | Report what would change; write nothing. |

The report prints `remapped` / `cleared` / `unresolved` counts. Idempotent once hops are healed or cleared.

---
