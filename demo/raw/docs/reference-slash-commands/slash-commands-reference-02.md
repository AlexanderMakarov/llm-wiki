---
title: "Slash commands reference (part 2/4: Wiki pipeline)"
slug: slash-commands-reference-02
project: reference-slash-commands
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/reference/slash-commands.md"
content_sha256: 27e61bf4e1fec0567f035bd800d927b554d63ef2038d5014d6a732e649596f37
---

> Part 2 of 4 of **Slash commands reference** — Wiki pipeline.

## Wiki pipeline

### `/wiki-init`

**What:** scaffolds an empty llmwiki — creates `raw/`, `wiki/`, `site/`
and seeds `wiki/index.md`, `wiki/log.md`, `wiki/overview.md`, plus the
nine navigation files (`CRITICAL_FACTS.md`, `MEMORY.md`, `SOUL.md`,
`hints.md`, `hot.md`, `dashboard.md`).

**Wraps:** `python3 -m llmwiki init`.

**When to use:** first time in a fresh repo, or after deleting `wiki/`
to start over.

**Example:**

```
/wiki-init
```

Claude Code will respond by running init and surfacing which files
were seeded.

---

### `/wiki-sync`

**What:** convert new Claude Code (+ Codex + Cursor + etc.) `.jsonl`
sessions into markdown under `raw/sessions/`, then ingest into `wiki/`.

**Wraps:** `python3 -m llmwiki sync`.

**Arguments Claude may pass through:** `--dry-run`, `--since`,
`--project`, `--force`, `--vault`. Say any of them in natural language
— "sync but only sessions from this week" becomes
`--since $(date -v-7d +%Y-%m-%d)`. Durable lookback in config (`filters.since` / `adapters.*.since`) applies on bare `/wiki-sync` when `--since` is omitted — see [configuration-reference.md](../configuration-reference.md#sync-lookback).

**When to use:** at the end of each coding block. Also the only command
that triggers auto-ingest of new pages into `wiki/`.

**Example:**

```
/wiki-sync
/wiki-sync only my llm-wiki project
/wiki-sync but don't auto-build afterwards
/wiki-sync into my Obsidian vault at ~/Documents/Obsidian Vault
```

**Expected output (narrated):**

```
==> claude_code: 3 new sessions since last sync
✓ wrote 3 pages under raw/sessions/
✓ ingested into wiki/sources/
✓ auto-build: site/ rebuilt (690 HTML files)
```

---

### `/wiki-ingest <path>`

**What:** ingest **one** source document or folder into `wiki/`, or enrich / discuss pending candidates during review. Reads the file, creates / updates the matching `wiki/sources/<slug>.md`, and may propose entity/concept candidates. **Trusted hubs still require review** (`/wiki-candidates` or `llmwiki candidates promote|merge|discard`) — ingest is not an auto-promote escape hatch.

**Wraps:** the Ingest Workflow in `CLAUDE.md` (no single CLI — it's a slash-command-driven workflow that the model orchestrates).

**When to use:** you dropped a source file manually (a PDF, a Jira ticket export, a meeting transcript), or Home / Analytics show a **To review** backlog and you want agent-led discussion over candidates. For bulk stub generation from already-synthesized sources, prefer `llmwiki synth --candidates-only`.

**Examples:**

```
/wiki-ingest raw/sources/2026-04-17-incident.md
/wiki-ingest raw/jira/
/wiki-ingest ~/Downloads/meeting-transcript.vtt
```

---

### `/wiki-synth`

**What:** synthesize pending raw sessions/docs into `wiki/sources/`, then harvest entity/concept candidates into `wiki/candidates/` (default). Use `--sources-only` for the legacy sources-only path. Sources are two LLM jobs per run (known-names prepare + one ask per queued file); harvest is offline. Ctrl+C harvests from written pages (or prints `synth --candidates-only` after `--sources-only`) and exits 130. Do not run a separate consolidate-topics step — known-names prepare is part of `synth`.

**Wraps:** `python3 -m llmwiki synth`.

**Example:**

```
/wiki-synth
/wiki-synth with a cost estimate
/wiki-synth force a re-run of every source
/wiki-synth sources only
```

---

### `/wiki-candidates`

**What:** triage pending candidates — `promote`, `flip-promote`, `merge`, `discard`, or batch `apply --actions`.

**Wraps:** `python3 -m llmwiki candidates list` + follow-ups (`apply --actions` for batches). Same intents `site/candidates.html` lists, whose copyable batch feeds the same command.

**When to use:** Home **Candidates** / Analytics **Candidates to review** is non-zero, `/wiki-lint` reported `stale_candidates`, or you just ran `llmwiki synth` / `synth --candidates-only`.

Promote fills an empty `## Key Facts` offline from source `fact:` bullets (and harvest stubs); Dummy / no backend is fine (#147). Prefer the CLI action for the common case. Opt-in `llmwiki candidates rewrite-key-facts --slug <Name>` (or `--all`) still needs an LLM for trusted pages with regex-era Key Facts or pasted harvest-stub `## Candidate merge` blocks. Prefer `flip-promote` over hand-moving stubs between `candidates/entities` and `candidates/concepts`.

**Example:**

```
/wiki-candidates
```

Claude will walk the queue one at a time and offer actions per candidate.

---

### `/wiki-query <question>`

**What:** answer a question from the wiki. Reads `wiki/index.md` +
`wiki/overview.md` + any `cache_tier: L1` pages, then walks relevant
source / entity / concept pages and synthesises an answer with inline
`[[wikilinks]]` back to the originals.

**Wraps:** the Query Workflow in `CLAUDE.md`.

**When to use:** "have I solved this before?" / "when did I add X?" /
"which sessions touched Y?".

**Examples:**

```
/wiki-query when did I add the lint rules?
/wiki-query which agent did I use for refactoring the cache-tier module?
/wiki-query summarize every session about Obsidian integration
```

**Save prompt:** if the answer runs 3+ paragraphs, Claude will offer to
save it under `wiki/syntheses/<slug>.md`.

---

### `/wiki-update <page>`

**What:** surgically edit one wiki page without re-ingesting. Useful
for fixing broken wikilinks, updating stale frontmatter, adding a
missing `## Connections` line.

**When to use:** lint flagged something, you know the fix, you don't
want to re-run sync.

**Example:**

```
/wiki-update wiki/entities/RAG.md add a Connections section linking to Karpathy and llm-wiki
```

---

### `/wiki-lint`

**What:** run every registered lint rule (16 at last count — all structural / deterministic). The live number is printed by `llmwiki lint --help`.

**Wraps:** `python3 -m llmwiki lint`.

**Rules, in order:**

1. `frontmatter_completeness`
2. `frontmatter_validity`
3. `link_integrity`
4. `orphan_detection`
5. `content_freshness`
6. `duplicate_detection`
7. `index_sync`
8. `contradiction_detection` — non-filler `## Contradictions` sections
9. `claim_verification` — entity/concept claims without sources
10. `summary_accuracy` — empty `summary:` frontmatter
11. `stale_candidates`
12. `tags_topics_convention` *(G-16 · #302)*
13. `stale_reference_detection` *(G-17 · #303)*
14. `frontmatter_count_consistency`
15. `tools_consistency`
16. `stub_source_pages`

**Example:**

```
/wiki-lint
/wiki-lint just the link_integrity rule
```

---

### `/wiki-graph`

**What:** build the knowledge graph. Nodes = wiki pages, edges =
`[[wikilinks]]`. Emits `graph/graph.json` + `graph/graph.html`.

**Wraps:** `python3 -m llmwiki graph`.

**Example:**

```
/wiki-graph
```

Then open `site/graph.html` (auto-copied from `graph/graph.html` during
build) in a browser.

---

### `/wiki-reflect`

**What:** higher-order self-reflection pass over the whole wiki. Looks
for gaps, patterns, duplicated-topic clusters, areas where a synthesis
page would help.
