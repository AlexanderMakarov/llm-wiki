---
title: "CLI reference (part 5/15: candidates — approval workflow)"
slug: cli-reference-05
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/reference/cli.md"
content_sha256: 186543f38f0258ea703f9ef68071d930f7135ea481068df5e5b46346e0f33e99
---

> Part 5 of 15 of **CLI reference** — candidates — approval workflow.

## `candidates` — approval workflow

Positional `action` picks `list` / `promote` / `flip-promote` / `merge` / `discard` / `apply` / `rewrite-key-facts`.

Successful `promote` / `flip-promote` / `merge` / `discard` / `apply` reconcile `wiki/index.md` (#101): dead `candidates/…` bullets are dropped, an empty `## Candidates` section is removed, and newly trusted pages are listed under Entities/Concepts. `/wiki-candidates` should call these same actions — do not run idle `sync`/`synth` just to refresh the catalog after review. Site UI: open `site/candidates.html` — it lists everything pending, takes a decision per row, and its **Apply** button prints the `candidates apply --vault … --actions -` command plus the JSON batch for the rows you decided (#97). A successful `apply` then rebuilds `site/` so the open candidates page, Home, and Analytics match the wiki; pass `--no-rebuild` to skip that (for example when applying several batches before one `llmwiki build`).

`promote` fills an empty (or heading-only) `## Key Facts` from nested `fact:` bullets on the cited source pages' Connections topics (#147 / #103). That path is offline — Dummy / `None` backends are fine. Non-empty reviewer Key Facts are left alone. Opt-in rewrite of trusted pages still needs a model: `rewrite-key-facts` uses the backend named by `synthesis.backend` (override the prompt per vault at `wiki/prompts/key_facts.md`).

`merge` folds a harvest stub into the target by unioning its `sources:` and Connections links and recording the name under `## Aliases` (inbound `[[merged-away]]` links resolve to the survivor via that section in graph, lint, backlinks, and references); a candidate containing reviewer prose still has that prose appended under `## Candidate merge — <date>`. Target may be a trusted page or another pending stub in the same kind.

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
| `--kind {entities,concepts,sources,syntheses}` | Subtree. Auto-detected if omitted. |
| `--wiki-dir PATH` | Wiki dir. Default: `./wiki`. |
| `--stale` | With `list`: only stale candidates. |
| `--stale-days N` | Staleness threshold. Default: 30. |
| `--json` | JSON output for `list`. |
| `--actions JSON` | For `apply`: JSON array of `{action,slug,kind?,into?,reason?}`. Pass `-` to read the array from stdin. |
| `--no-rebuild` | For `apply`: skip rebuilding `site/` after a successful batch. Default is to rebuild so `candidates.html` drops the rows that were just promoted, merged, or discarded. |

See [`guides/existing-vault.md`](../guides/existing-vault.md) for the round-trip semantics when a candidate lives inside a vault.

---
