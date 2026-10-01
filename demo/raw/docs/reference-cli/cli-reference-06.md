---
title: "CLI reference (part 6/19: candidates — approval workflow)"
slug: cli-reference-06
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-10-01
source: "docs/reference/cli.md"
content_sha256: 8c1258c0faddb3eb988de6c7870bdada2b983cd07f6b325b78b35e680759efeb
---

> Part 6 of 19 of **CLI reference** — candidates — approval workflow.

## `candidates` — approval workflow

Positional `action` picks `list` / `promote` / `flip-promote` / `merge` / `discard` / `apply` / `rewrite-key-facts`.

`--slug` on `promote` / `flip-promote` / `merge` / `discard` / `rewrite-key-facts` (and `merge --into`, `discard --redirect`) matches the searched filename exactly first; failing that, it falls back to a unique `norm_page_key` fold of those filenames (case and punctuation insensitive, same fold `link_integrity` and harvest use), so `--slug Junk` still finds a stub written `JUNK.md`. The searched files are the pending stubs under `wiki/candidates/<kind>/` for the review actions and the trusted pages under `wiki/entities/` and `wiki/concepts/` for `rewrite-key-facts`. A fold matching more than one page raises, naming every match, instead of guessing. A slug is sanitized the way a stub filename is and the resolved page must sit inside the wiki, so `--slug ../../outside` resolves to nothing rather than to a file beside the vault (#282).

Successful `promote` / `flip-promote` / `merge` / `discard` / `apply` reconcile `wiki/index.md` (#101): dead `candidates/…` bullets are dropped, an empty `## Candidates` section is removed, and newly trusted pages are listed under Entities/Concepts. `/wiki-candidates` should call these same actions — do not run idle `sync`/`synth` just to refresh the catalog after review. Site UI: open `site/candidates.html` — it lists everything pending, takes a decision per row, and its **Apply** button prints the `candidates apply --vault … --actions -` command plus the JSON batch for the rows you decided (#97). A successful `apply` then rebuilds `site/` so the open candidates page, Home, and Analytics match the wiki; pass `--no-rebuild` to skip that (for example when applying several batches before one `llmwiki build`).

`promote` fills an empty (or heading-only) `## Key Facts` from nested `fact:` bullets on the cited source pages' Connections topics (#147 / #103). That path is offline — Dummy / `None` backends are fine. Non-empty reviewer Key Facts are left alone. Opt-in rewrite of trusted pages still needs a model: `rewrite-key-facts` uses the backend named by `synthesis.backend` (override the prompt per vault at `wiki/prompts/key_facts.md`).

`merge` folds a harvest stub into the target by unioning its `sources:` and Connections links and recording the name under `## Aliases` (inbound `[[merged-away]]` links resolve to the survivor via that section in graph, lint, backlinks, and references); a candidate containing reviewer prose still has that prose appended under `## Candidate merge — <date>`. Target may be a trusted page or another pending stub in the same kind.

`discard` archives the stub and rewrites every `[[link]]` to its name outside `wiki/archive/` (any casing, labels and anchors included) to plain text — the label when there is one, else the name as written — so no link points into cold storage (#282). With `--redirect PAGE` those links become `[[PAGE|text]]` instead and the name is recorded under `PAGE`'s `## Aliases`, so later links to it resolve there and the synth vocabulary maps the name onto that page. `PAGE` must be an existing page outside `wiki/candidates/` and `wiki/archive/`. Links are left alone when another live page or alias already answers to the name, and `--redirect` is then refused before the stub moves — the error names the page that already owns the name, since recording the alias anyway would leave two live pages answering to it. `PAGE`'s own mention of the discarded name becomes plain text rather than a link to itself. The command prints how many links it rewrote in how many pages, and warns on stderr naming every page it could not read (those may still link to the discarded name). `--redirect` only applies to `discard`: combined with another action it is refused, on the command line and in an `apply` batch alike.

`apply` runs a **batch** of the same intents in one process (the JSON shape `site/candidates.html` prints). A batch that merges into a peer slug the same batch also promotes, flip-promotes, discards, or merges away is refused before any row runs — the CLI prints the conflicting actions and exits non-zero (#149).

```bash
python3 -m llmwiki candidates apply --actions '[{"action":"promote","slug":"Foo","kind":"entities"},{"action":"promote","slug":"Prompt Caching","kind":"concepts"}]'
python3 -m llmwiki candidates apply --actions - <<'EOF'
[{"action":"discard","slug":"Bogus","kind":"entities","reason":"noise"}]
EOF
```

Already-trusted pages that still carry machine-assembled (regex) Key Facts, or pasted harvest-stub `## Candidate merge` blocks from the old merge path, are fixed with `rewrite-key-facts`:

```bash
python3 -m llmwiki candidates list
python3 -m llmwiki candidates list --stale --stale-days 60
python3 -m llmwiki candidates list --json
python3 -m llmwiki candidates promote --slug NewEntity
python3 -m llmwiki candidates promote --slug NewEntity --kind concepts
python3 -m llmwiki candidates flip-promote --slug Misfiled
python3 -m llmwiki candidates merge --slug DuplicateFoo --into Foo
python3 -m llmwiki candidates discard --slug BogusEntity --reason "LLM hallucinated"
python3 -m llmwiki candidates discard --slug "Old Name" --reason "duplicate" --redirect ExistingPage
python3 -m llmwiki candidates rewrite-key-facts --slug ExistingEntity
python3 -m llmwiki candidates rewrite-key-facts --all
```

### Flags

| Flag | What |
|---|---|
| `--slug NAME` | Page slug. **Required** for `promote` / `flip-promote` / `merge` / `discard`; or with `rewrite-key-facts`. |
| `--all` | For `rewrite-key-facts`: every entity/concept page. |
| `--into NAME` | For `merge`: target slug (trusted page or another pending stub in the same kind). |
| `--reason TEXT` | For `discard`: why (written to archive's `.reason.txt`). |
| `--redirect PAGE` | For `discard`: point every `[[link]]` to the discarded name at existing live page `PAGE` (keeping the visible text) and record the name under its `## Aliases`. Without it, discard turns those links into plain text. |
| `--kind {entities,concepts,sources,syntheses}` | Subtree. Auto-detected if omitted. |
| `--wiki-dir PATH` | Wiki dir. Default: `./wiki`. |
| `--stale` | With `list`: only stale candidates. |
| `--stale-days N` | Staleness threshold. Default: 30. |
| `--json` | JSON output for `list`. |
| `--actions JSON` | For `apply`: JSON array of `{action,slug,kind?,into?,reason?,redirect?}` (`redirect` only with `discard`). Pass `-` to read the array from stdin. |
| `--no-rebuild` | For `apply`: skip rebuilding `site/` after a successful batch. Default is to rebuild so `candidates.html` drops the rows that were just promoted, merged, or discarded. |

See [`guides/existing-vault.md`](../guides/existing-vault.md) for the round-trip semantics when a candidate lives inside a vault.

---
