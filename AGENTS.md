# llmwiki — Codex CLI / Agent Schema

This file is the schema for **Codex CLI** and any other coding agent that reads `AGENTS.md` instead of `CLAUDE.md` (OpenCode, Gemini CLI, etc.). The workflows are identical to [CLAUDE.md](CLAUDE.md) — only the language is agent-agnostic.

> **Changing llmwiki's own code or docs instead of a vault?** This file is the *product schema* — it tells you how to maintain a user's `raw/` → `wiki/` → `site/` knowledge base. It is not the contribution guide. For repo work (fixes, features, tests, PRs) read [`CONTRIBUTING.md`](CONTRIBUTING.md). Cursor loads the short form from [`.cursor/rules/`](.cursor/rules); Claude Code loads it from [`.claude/rules/contributing.md`](.claude/rules/contributing.md). Run `ruff check` and `python3 -m pytest tests/ -q` before pushing.

## Three layers

```
raw/           IMMUTABLE. Session transcripts converted from the agent's session store.
               Never modify files here.

wiki/          LLM-maintained. Pages you write that summarise and cross-reference raw/.
  index.md         Catalog of every page. Update on every ingest.
  log.md           Append-only chronological record (auto-archives at 50KB).
  overview.md      Living synthesis.
  hints.md         Writing conventions and entity naming rules (load on demand).
  hot.md           Last 10 session summaries — global hot cache.
  hot/<project>.md Per-project hot caches (default ON, configurable).
  MEMORY.md        Cross-session facts (200-line cap, auto-consolidated).
  SOUL.md          Wiki identity and writing voice.
  CRITICAL_FACTS.md Must-know facts (<120 tokens).
  sources/         One page per raw source.
  candidates/      Pending entity/concept stubs from harvest — review before promote.
  entities/        People, companies, products.
  concepts/        Ideas, frameworks, methods.
  projects/        Codebases and work streams (seeded from session metadata).
  syntheses/       Saved query answers.

site/          GENERATED. Static HTML from `python3 -m llmwiki build`. Do not edit.
```

Canonical loop: `sync / add → synth (sources + harvest) → review candidates → build`. `synth` does not rebuild `site/` — run `build` when you want Home/Analytics refreshed. Serve with `llmwiki serve --dir <vault>/site` (bare `serve` defaults to `./site` under cwd).

## Session stores by agent

Different agents write their transcripts to different locations. The adapter registry in `llmwiki/adapters/` abstracts this away.

| Agent | Session store | Adapter |
|---|---|---|
| Claude Code | `~/.claude/projects/<project>/<uuid>.jsonl` | `claude_code.py` |
| Codex CLI | `~/.codex/sessions/` | `codex_cli.py` (stub in v0.1) |
| Gemini CLI | `~/.gemini/` (TBD) | `gemini_cli.py` (planned) |
| OpenCode | `~/.opencode/` (TBD) | `opencode.py` (planned) |

The CLI auto-detects which adapter(s) to run. Override with `--adapter <name>`.

## Commands

Run from inside the repo:

```bash
python3 -m llmwiki sync           # convert new .jsonl → raw/sessions/*.md
python3 -m llmwiki synth          # wiki/sources/ + harvest wiki/candidates/
python3 -m llmwiki build          # compile site/ from raw/ + wiki/
python3 -m llmwiki serve --dir <vault>/site   # local HTTP server (default ./site is cwd-relative)
python3 -m llmwiki init           # scaffold raw/, wiki/, site/ directories
```

Or use the one-click scripts: `./sync.sh`, `./build.sh`, `./serve.sh` (macOS/Linux); `sync.bat`, `build.bat`, `serve.bat` (Windows).

## Ingest Workflow

Triggered when the user says "ingest this", "sync the wiki", or runs `/wiki-sync`:

1. Read the source file(s) under `raw/`.
2. Read `wiki/index.md` and `wiki/overview.md` for current wiki context.
3. For each source, write `wiki/sources/<slug>.md` using the Source Page Format below.
4. Update `wiki/index.md` — add the new source under `## Sources`.
5. Update `wiki/overview.md` if the source adds substantial new information.
6. Create/update `wiki/entities/<Name>.md` for any people, companies, products, tools, or libraries mentioned.
7. Create/update `wiki/concepts/<Name>.md` for any ideas or patterns discussed.
8. Create/update `wiki/projects/<slug>.md` with `type: project` for any codebase or work stream mentioned — never file a project as an entity.
9. Cross-link everything with `[[wikilinks]]` under `## Connections`.
10. Flag contradictions under `## Contradictions` — keep both claims visible.
11. Append to `wiki/log.md`: `## [YYYY-MM-DD] ingest | <title>`

## Query Workflow

Triggered by `/wiki-query <question>`:

1. Read `wiki/index.md` and `wiki/overview.md`.
2. Read the pages most relevant to the question.
3. Synthesise an answer with `[[wikilink]]` citations.
4. If the answer is substantial, ask if it should be saved to `wiki/syntheses/<slug>.md`.
5. Append to `wiki/log.md`: `## [YYYY-MM-DD] query | <question>`.

## Lint Workflow

Triggered by `/wiki-lint`:

Check for:

- **Orphans** — pages with no inbound `[[links]]`.
- **Broken wikilinks** — pointing to non-existent pages.
- **Contradictions** — conflicting claims across pages.
- **Stale pages** — `last_updated` older than the most recent contributing source.
- **Missing entity pages** — entities mentioned in 3+ sources but no dedicated page.
- **Data gaps** — questions the wiki can't answer.

Do not hand-repair the catalog: `sync`, `synth`, and `remove` reconcile `wiki/index.md` with the pages on disk (#71) — adding unlisted pages, dropping dead links, refreshing every `(count)` — and preserve existing descriptions. Run `llmwiki lint --rules index_sync` to verify.

Output a report. Offer to save it to `wiki/lint-report.md`.

## Page formats

### Source page (`wiki/sources/<slug>.md`)

```markdown
---
title: "Source Title"
type: source
tags: []
date: YYYY-MM-DD
source_file: raw/sessions/<project>/<file>.md
project: <project-slug>
---

## Summary
2–4 sentences.

## Key Claims
- Claim 1
- Claim 2

## Key Quotes
> "Quote" — context

## Connections
- [[Entity]] — how they relate
- [[Concept]] — how it connects
```

### Entity / Concept / Project page

```markdown
---
title: "Name"
type: entity   # or: concept, project
tags: []
sources: [slug-1, slug-2]
last_updated: YYYY-MM-DD
---

# Name

One paragraph.

## Key Facts
- Fact 1

## Sessions
- [[session-slug]] (YYYY-MM-DD) — what happened

## Connections
- [[Other]]
```

### Index

```markdown
# Wiki Index

## Overview
- [Overview](overview.md)

## Sources
- [Title](sources/slug.md) — one-line summary

## Entities
- [Name](entities/Name.md) — one-line description

## Concepts
- [Name](concepts/Name.md) — one-line description

## Projects
- [project-slug](projects/project-slug.md) — one-line description

## Syntheses
- [Title](syntheses/slug.md) — the question it answers
```

### Log

```markdown
## [YYYY-MM-DD] <operation> | <title>

<optional one-line notes>
```

Parse recent entries with: `grep "^## \[" wiki/log.md | tail -10`

## Naming conventions

- Source slugs: `kebab-case`
- Entity / concept pages: `TitleCase.md`
- Synthesis pages: `kebab-case.md`

## Cross-project wiki access

Other projects can reference this wiki by adding to their agent config:

```
wiki_path: ~/Desktop/2026/production-draft/llm-wiki
```

Then read `wiki/index.md` first, navigate from there.

## Page kinds

Every page declares its kind in the `type` frontmatter field:

`source` | `entity` | `concept` | `project` | `synthesis` | `comparison` | `question` | `navigation` | `context`

## Confidence & lifecycle

- `confidence: 0.85` — 4-factor score (source count, quality, recency, cross-refs)
- `lifecycle: draft` — one of: draft, reviewed, verified, stale, archived

## Hard rules

1. `raw/` is immutable. Never edit files there.
2. No silent overwrites. Record contradictions, don't hide them.
3. Cross-link everything — every page has a `## Connections` section.
4. Frontmatter is authoritative. Always populate `title`, `type`, `tags`, `sources`, `last_updated`, `confidence`, `lifecycle`.
5. Do not ingest raw `.jsonl` files directly — only ingest the markdown under `raw/`.
