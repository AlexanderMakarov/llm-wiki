---
name: llmwiki-ingest
description: Ingest one source document (or a folder of them) into the llmwiki. Use when the user drops a new markdown file, PDF, or URL into the wiki and asks you to process it. The user will typically say "ingest this", "add this to the wiki", "process this file into the wiki", or point at a file under `raw/`.
---

# llmwiki-ingest

## What this skill does

Turns a source (file, folder, URL, or PDF) into wiki content following the Karpathy LLM Wiki pattern. The path taken depends on what kind of source it is:

- **Documents** (files, folders, URLs, PDFs that are not `raw/sessions/` transcripts) route through `llmwiki add` (CLI) or the equivalent MCP `wiki_add` tool, then through `llmwiki synth`. The tools write the raw doc, the `wiki/sources/` page, and the candidate entity/concept stubs — you do not hand-write any of those pages.
- **Session transcripts** already under `raw/sessions/` were converted by `llmwiki sync`; there is nothing left to "add". Run `llmwiki synth` to synthesize and harvest them the same way, and only summarize by hand when the user explicitly wants a page the pipeline will not produce.
- **Knowledge pages** (`wiki/entities/`, `wiki/concepts/`) come from reviewing harvested candidates with `/wiki-candidates`, not from writing files directly. Harvest emits entity and concept stubs only — **project pages** (`wiki/projects/`) are seeded from session metadata by `llmwiki sync`, so when a document needs one, hand-write it into the resolved vault.

## When to use

- User says "ingest this file", "add this to the wiki", "process this into the wiki"
- User runs the `/wiki-ingest` slash command
- User says "sync the wiki" — in that case, the `llmwiki-sync` skill runs the converter first, then invokes this skill for each new file

## Workflow — documents (files, folders, URLs, PDFs)

Anything that isn't already a `raw/sessions/` transcript is a **document**. Do not hand-write a `wiki/sources/*` page for it, and do not hand-write entity or concept pages from it — run the pipeline and review what it proposes. A project page is the exception: harvest never proposes one, so write it by hand into the resolved vault if the document needs one.

1. **Add the source.** Either surface works and they share the same `run_add` implementation, so pick whichever you have: CLI `python3 -m llmwiki add <src> --project <slug>`, or the MCP tool `wiki_add` with `url` / `path` / `content` (plus `project`, `title`, `tags`, `note`, `synthesize`, `no_build`).
   ```bash
   python3 -m llmwiki add <src> --project <slug>
   ```
   `<src>` may be a URL, a file path, a folder (repeatable — pass several sources in one invocation to batch the convert/build pass), or `-` for stdin in the process locale encoding (`source: "piped"`; cannot mix `-` with other sources). `--project <slug>` groups the doc under `raw/docs/<slug>/` instead of letting it derive its own slug; pick a slug that matches the topic being ingested. Useful extra flags: `--title` (override title derivation, single source only), `--tag` (repeatable), `--note` (blockquote prepended to the body), `--dry-run` (convert and report, write nothing), `--no-build` (skip the post-add site rebuild), `--synthesize` (write the `wiki/sources/` page in the same pass). `--no-synthesize` is a deprecated warn+no-op (synthesis is already off by default).
2. **Synthesize and harvest.** Bare `add` writes raw and rebuilds the site only, so run synth afterwards — it fills `wiki/sources/` from what is pending and then harvests candidate entity/concept stubs into `wiki/candidates/`:
   ```bash
   python3 -m llmwiki synth
   ```
   If you already passed `--synthesize` (or `synthesize: true`) the source page exists, but the harvest does not — `python3 -m llmwiki synth --candidates-only` gets the stubs without paying for a second synthesis pass.
3. **Read the resulting `wiki/sources/<slug>.md`** page in the resolved vault to see what was synthesized, and report it to the user.
4. **Review the candidates** — the harvested stubs under `wiki/candidates/` are the proposed entity and concept pages, and they are not trusted wiki content until somebody approves them. Follow `/wiki-candidates` (or `python3 -m llmwiki candidates list` then `promote` / `flip-promote` / `merge` / `discard`, or one `candidates apply --actions` batch). Promotion moves the stub into `wiki/entities/` or `wiki/concepts/`, fills empty Key Facts offline, and reconciles `wiki/index.md` for you.
5. **Rebuild the site** with `python3 -m llmwiki build` when synth or a one-off review action changed pages (`candidates apply` rebuilds on its own).

`wiki/index.md` and `wiki/log.md` are reconciled by the commands — `sync`, `synth`, and the review actions — so do not hand-edit the catalog or the log for a document ingest.

**Source-layer guardrail:** pass the user's exact path, URL, or text to `add` / MCP `wiki_add`. Do not reconstruct input from `wiki/sources/` or other derived pages unless the user asked.

### ⚠️ If MCP `wiki_add` times out, verify before retrying

`wiki_add` runs under `mcp.tool_timeouts.wiki_add` (default 120s) and holds the vault pipeline lock while it works. A large source, a folder, or `synthesize: true` can exceed the budget; when it does, the tool returns a timeout error but **the add keeps running in the background**. Do not repeat the call and do not fall back to CLI `add` straight away: check whether the doc landed first (`wiki_search` for its title, or look for the file under `raw/docs/`). Retrying blindly gets you a duplicate doc, or a second run blocked on the lock the first one still holds. Raise `mcp.tool_timeouts.wiki_add` in `config.json` for sources that genuinely need longer.

### ⚠️ Vault resolution — read before writing anything by hand

`llmwiki add` resolves the target vault itself (`--vault`, else `config.json` → `vault.default_path`, else the current working directory), so step 1 is always safe as written. Anything you do write **by hand** — a synthesis page the user asked for, a correction to a promoted page — must land in that **same resolved vault**. Check `config.json` → `vault.default_path` (or whatever `--vault` you passed to `add`) before writing.

## Workflow — session transcripts (`raw/sessions/`)

Session transcripts are already produced by `llmwiki sync`; there is no `add` step, and `python3 -m llmwiki synth` is the same synthesize-then-harvest pass documented above. Reach for the hand-written workflow below only when the user wants a page synth does not produce, or when no synthesis backend is configured:

1. Read the source file(s) with the Read tool
2. Read `wiki/index.md` and `wiki/overview.md` for context
3. Write `wiki/sources/<slug>.md` using the Source Page Format
4. Update `wiki/overview.md` if substantial new info
5. Cross-link with `[[wikilinks]]` under `## Connections`
6. Flag contradictions under `## Contradictions`
7. Append to `wiki/log.md`: `## [YYYY-MM-DD] ingest | <title>`

Entity and concept pages still come from the candidate review in step 4 of the document workflow — hand-writing the source page does not make hand-writing the knowledge layer the right move. Project pages are the exception: `sync` seeds them from session metadata, and you may write one by hand when a session needs a page the seeding did not produce.

### Session-specific rules

When the source is under `raw/sessions/` (a session transcript converted by the converter):

- **Trust the frontmatter** as authoritative (project, started, model, tools_used, etc.)
- **Do not copy the `## Conversation` section verbatim** — use it as raw material to summarise
- **Extract decisions** — anything the user explicitly locked is worth a concept page; propose it through the candidate review rather than writing it directly
- **Every entry in `tools_used`** is a candidate entity
- **If `is_subagent: true`** — link to the parent session rather than creating a new project page

## Hard rules

1. `raw/` is immutable. Never modify files there.
2. Documents route through `add` (CLI or MCP) plus `synth`; never hand-write a `wiki/sources/*` page for a document.
3. Entity and concept pages come from candidate review, not from you writing files into `wiki/entities/` or `wiki/concepts/`. Project pages (`wiki/projects/`) are not harvested at all — `sync` seeds them from session metadata; hand-write one into the resolved vault only when a source needs a page that seeding did not produce.
4. No silent overwrites. Conflicting claims go under `## Contradictions`.
5. Every page has a `## Connections` section with at least one `[[wikilink]]`.
6. Frontmatter is authoritative. Always populate `title`, `type`, `tags`, `sources`, `last_updated`.
7. Resolve the vault before writing anything by hand — see the warning above.
