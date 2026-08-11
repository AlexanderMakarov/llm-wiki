---
title: "Slash commands reference (part 2/4: Wiki pipeline)"
slug: slash-commands-reference-02
project: slash-commands-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/slash-commands.md"
content_sha256: b914ad5a59ba24c268c483ba5ec07399a0c9cbe9939abfcc4d7a50b7216c9763
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
`--since $(date -v-7d +%Y-%m-%d)`.

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

### `/wiki-synth`

**What:** synthesize pending raw sessions/docs into `wiki/sources/`, then harvest entity/concept candidates into `wiki/candidates/` (default). Use `--sources-only` for the legacy sources-only path.

**Wraps:** `python3 -m llmwiki synth`.

**Example:**

```
/wiki-synth
/wiki-synth with a cost estimate
/wiki-synth force a re-run of every source
/wiki-synth sources only
```

### `/wiki-synthesize`

**Deprecated** alias for `/wiki-synth`. Prefer `/wiki-synth`. Still wraps `python3 -m llmwiki synthesize` (sources-only + deprecation warning).

---

### `/wiki-candidates`

**What:** triage pending candidates — `promote`, `flip-promote`, `merge`, `discard`, or batch `apply --actions`.

**Wraps:** `python3 -m llmwiki candidates list` + follow-ups (`apply --actions` for batches). Same intents as `/candidates.html` (batch Apply under serve, or copy one `apply --actions` CLI line when static).

**When to use:** Home **Candidates** / Analytics **Candidates to review** is non-zero, `/wiki-lint` reported `stale_candidates`, or you just ran `llmwiki synth` / `synth --candidates-only`.

Promote has the configured synthesis backend write an empty `## Key Facts` from harvest evidence sources, and fails rather than guessing when no LLM backend is configured (#103). Prefer the CLI action over hand-editing Key Facts for the common case. Already-trusted pages that still have regex-era Key Facts (or pasted harvest-stub `## Candidate merge` blocks) are recovered with `llmwiki candidates rewrite-key-facts --slug <Name>` (or `--all`). Prefer `flip-promote` over hand-moving stubs between `candidates/entities` and `candidates/concepts`.

**Example:**

```
/wiki-candidates
```

Claude will walk the queue one at a time and offer actions per candidate.

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
build) or the compiled URL in the served site.

---

### `/wiki-reflect`

**What:** higher-order self-reflection pass over the whole wiki. Looks
for gaps, patterns, duplicated-topic clusters, areas where a synthesis
page would help.

**No CLI wrapper** — it's a model-orchestrated workflow that reads the
index + overview + sample of pages and outputs suggestions.

**Example:**

```
/wiki-reflect
```

Use sparingly; it's the most token-heavy command.

---
