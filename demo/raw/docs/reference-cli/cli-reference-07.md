---
title: "CLI reference (part 7/15)"
slug: cli-reference-07
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/reference/cli.md"
content_sha256: 186543f38f0258ea703f9ef68071d930f7135ea481068df5e5b46346e0f33e99
---

> Part 7 of 15 of **CLI reference**.

Every `synthesize` call now produces **topical** tags alongside the deterministic baseline.  The synthesizer emits a `<!-- suggested-tags: prompt-caching, rag, github-actions -->` block as the first line of its response; the pipeline parses it, strips it from the body, and merges the tags into frontmatter with:

- **Baseline preserved** — adapter, project slug, model family stay.
- **Maintainer wins** — on `--force`, whatever you added via `llmwiki tag add` is kept at the front of the list.
- **Stop-word filter** — the LLM can't re-add boilerplate tags (`session`, `summary`, `claude-code`, etc.).
- **Cap 5** — max 5 AI tags per page to prevent drift.
- **Near-dup rejection** — `prompt-cache` is blocked when `prompt-caching` is already on the page (threshold 0.80 + prefix check).

No extra API round-trip — rides the existing synthesis call, so cost estimates from `--estimate` are unchanged.  If the backend returns no suggested-tags block (dummy backend, malformed output), the page still ships with baseline tags.

Removed: `synthesize` (use `synth`; the old name was sources-only by default) and `consolidate-topics` (known-names prepare is part of `synth`).

---
