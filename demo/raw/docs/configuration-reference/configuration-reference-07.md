---
title: "Configuration Reference (part 7/8: Vault file (llmwiki.json))"
slug: configuration-reference-07
project: configuration-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/configuration-reference.md"
content_sha256: 037667c9a64c03e7e116aad5677fbb0f9c2a8a529294787eae7fbe5f06d78089
---

> Part 7 of 8 of **Configuration Reference** — Vault file (llmwiki.json).

## Vault file (`llmwiki.json`)

`<vault-root>/llmwiki.json` holds the settings that belong to **the wiki itself** rather than to this install. It sits at the vault root beside `wiki/`, `raw/` and the vault's `llmwiki-state.json`, and it is meant to be committed: copying, sharing, or publishing the vault carries it along. The example wiki shipped with the project has one — [`demo/llmwiki.json`](../demo/llmwiki.json).

Two similarly-named JSON files, so keep them apart:

| | `config.json` | `llmwiki.json` |
|---|---|---|
| Lives at | the repo / install root | the vault root, beside `wiki/` |
| Describes | how *this install* behaves — adapters, redaction, truncation, synthesis backend | what is true of *this wiki* — today, the quality checks that cannot apply to it |
| Committed? | no, it is gitignored | yes, that is the point of it |
| Travels with a copied or published vault? | no | yes |
| Read by | `sync`, `synth`, `build`, … | `lint`, the `all` pipeline's lint stage, and the MCP `wiki_lint` tool |
| When missing | falls back to `examples/sessions_config.json` | the wiki declares nothing, and lint behaves exactly as it did before this file existed |

### `lint.disabled_rules`

Names the quality checks that do not apply to this wiki. A disabled rule is never constructed, never runs, and contributes no findings — and is named as skipped in every report, whether or not anything was found, so a short report can never be mistaken for a clean one. It is on/off only: a wiki cannot re-grade a finding's severity, and cannot switch a rule off for part of itself.

Two shapes are accepted. A bare list, when you do not want to record a reason:

```json
{
  "lint": {
    "disabled_rules": ["content_freshness"]
  }
}
```

Or an object mapping each rule to a written reason — preferred, because the reason is what you or a reviewer will read six months from now:

```json
{
  "lint": {
    "disabled_rules": {
      "content_freshness": "This wiki is a committed snapshot, so this check measures elapsed calendar time rather than a defect in the pages."
    }
  }
}
```

Rule names are the ones the report prints as `## <rule>` headings; the full list is in [reference/cli.md](reference/cli.md#lint--run-17-wiki-quality-rules), and any run that rejects a name prints the valid ones.

Keep a reason to a sentence or two. It is printed **verbatim, on one line** of every report the wiki produces, so a paragraph-length reason wraps badly in a CI log.

### Worked example

Write the file at the vault root and run the check:

```bash
cat > /path/to/vault/llmwiki.json <<'JSON'
{
  "lint": {
    "disabled_rules": {
      "content_freshness": "This wiki is a committed snapshot, so this check measures elapsed calendar time rather than a defect in the pages."
    }
  }
}
JSON

python3 -m llmwiki lint --vault /path/to/vault
```

The report names what it skipped, above the findings:

```
  scanned 3 pages
  2 issues: 1 errors, 1 warnings, 0 info
  skipped 1 of 17 rules (disabled in llmwiki.json):
    - content_freshness — This wiki is a committed snapshot, so this check measures elapsed calendar time rather than a defect in the pages.

## index_sync (1)
  [error] index.md: page 'sources/demo-source.md' not listed in index.md

## link_integrity (1)
  [warning] entities/Widget.md: broken wikilink [[Gadget]]
```

`lint --json` carries the same declaration under `disabled_rules`, which is always present — empty when the wiki declares nothing — so a consumer can read it without probing for the key:

```json
{
  "summary": { "error": 1, "warning": 1 },
  "issues": [
    { "rule": "index_sync", "severity": "error", "page": "index.md", "message": "page 'sources/demo-source.md' not listed in index.md" },
    { "rule": "link_integrity", "severity": "warning", "page": "entities/Widget.md", "message": "broken wikilink [[Gadget]]" }
  ],
  "total_pages": 3,
  "disabled_rules": {
    "content_freshness": "This wiki is a committed snapshot, so this check measures elapsed calendar time rather than a defect in the pages."
  },
  "ran": ["frontmatter_completeness", "index_sync", "link_integrity", "orphan_detection"]
}
```

`ran` names the checks that actually produced the report, in registry order. `disabled_rules` covers only the narrowing the wiki declared; `--rules` (and the MCP tool's `rules` argument) narrows a run without declaring anything, so without `ran` a short report is indistinguishable from a full one.

### A declaration that cannot be honoured is an error, never a silent skip

| Situation | What happens |
|---|---|
| A name that is not a registered rule (a typo, or a rule since retired) | The run stops with **exit 2**, naming the file, the unrecognised entry, and every valid rule name |
| `llmwiki.json` that is not valid JSON, or whose top level is not a JSON object | **exit 2**, naming the file and the parse error |
| A `lint.disabled_rules` that is neither a list of names nor an object mapping names to reasons | **exit 2** |
| Every registered rule disabled | The report states that nothing was checked, instead of printing a clean summary |
| Every rule a narrowed run selected disabled | The same, counted against what the run would have used — `--rules content_freshness` on a wiki that disables it skipped 1 rule of 1, not 1 of 17 |

None of these fall back to "this wiki declares no opt-outs". A declaration nobody can read might be switching every check off, so reporting the wiki as clean would be a guess dressed up as a result — and a typo must never leave a check switched on that you believed you had switched off.

### Switching a check off hides real findings

This is not a noise filter. A disabled rule does not run, so anything it *would* have found is simply absent from the report — and the report will look shorter and healthier for it. Reserve the declaration for checks that **cannot apply** to a wiki, not for checks that are merely inconvenient.

`content_freshness` on a committed snapshot is the legitimate case, and the one the shipped example uses. That check asks whether a page has gone untouched for three months; on a frozen, published copy the answer is decided by the calendar rather than by anything wrong with the pages, so the check would redden on a date rather than on a defect. Where staleness is *real*, refreshing the content is the honest cure — switching the check off only removes the reminder that the content has aged.

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `LLMWIKI_CONFIG` | Override the config file path | `./config.json`, then `examples/sessions_config.json` |
| `COPILOT_HOME` | Override the Copilot CLI base directory | `~/.copilot` |

Vault content root is **`vault.default_path` in `config.json`**. The removed `LLMWIKI_ROOT` env var is no longer read.
