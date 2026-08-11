---
title: "CLI reference (part 4/8: candidates — approval workflow)"
slug: cli-reference-04
project: cli-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/cli.md"
content_sha256: c2fa4d275fde9cc72d3178206373fc46e586aec2e3b709417d7081afdcd15f4b
---

> Part 4 of 8 of **CLI reference** — candidates — approval workflow.

## `candidates` — approval workflow

Positional `action` picks `list` / `promote` / `flip-promote` / `merge` / `discard` / `apply` / `rewrite-key-facts`.

Successful `promote` / `flip-promote` / `merge` / `discard` / `apply` reconcile `wiki/index.md` (#101): dead `candidates/…` bullets are dropped, an empty `## Candidates` section is removed, and newly trusted pages are listed under Entities/Concepts. `/wiki-candidates` should call these same actions — do not run idle `sync`/`synth` just to refresh the catalog after review. Site UI: open `/candidates.html` — per-row decisions + Apply; batch API under `llmwiki serve`, or one pasteable `candidates apply --actions '…'` command when static (#97).

`promote` also writes an empty (or heading-only) `## Key Facts` (#103). It builds an evidence digest — every line where each source listed in frontmatter `sources:` / Connections names the subject, capped at 12 sources and 4 lines each — and hands it to the backend named by `synthesis.backend`, which returns 3–5 attributed bullets. Non-empty reviewer Key Facts are left alone.

Because those bullets become trusted-layer prose, promote refuses to write them without a model: with `synthesis.backend` unset or `dummy` it exits 2 with `KeyFactsBackendError` and leaves the candidate pending. Override the prompt per vault at `wiki/prompts/key_facts.md`.

`merge` folds a harvest stub into the target by unioning its `sources:` and Connections links and recording the name under `## Aliases`; a candidate containing reviewer prose still has that prose appended under `## Candidate merge — <date>`. Target may be a trusted page or another pending stub in the same kind.

`apply` runs a **batch** of the same intents in one process (same JSON shape as `POST /api/candidates`):

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

See [`guides/existing-vault.md`](../guides/existing-vault.md) for the round-trip semantics when a candidate lives inside a vault.

---
