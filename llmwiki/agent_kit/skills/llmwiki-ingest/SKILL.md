---
name: llmwiki-ingest
description: Ingest one source document (or a folder of them) into the llmwiki. Use when the user drops a new markdown file, PDF, or URL into the wiki and asks you to process it. The user will typically say "ingest this", "add this to the wiki", "process this file into the wiki", or point at a file under `raw/`.
---

# llmwiki-ingest

## What this skill does

Turns a source (file, folder, URL, or PDF) into wiki content following the Karpathy LLM Wiki pattern. The path taken depends on what kind of source it is:

- **Documents** (files, folders, URLs, PDFs that are not `raw/sessions/` transcripts) route through the `llmwiki add` CLI, which converts, lands the raw doc, synthesizes the `wiki/sources/<slug>.md` page, and rebuilds — you do not hand-write the source page yourself.
- **Session transcripts** already under `raw/sessions/` are summarized by hand per the existing workflow (they were already converted by `llmwiki sync`; there's nothing left to "add").
- **Entity, concept, and project pages**, for either path, are written manually by you.

## When to use

- User says "ingest this file", "add this to the wiki", "process this into the wiki"
- User runs the `/wiki-ingest` slash command
- User says "sync the wiki" — in that case, the `llmwiki-sync` skill runs the converter first, then invokes this skill for each new file

## Workflow — documents (files, folders, URLs, PDFs)

Anything that isn't already a `raw/sessions/` transcript is a **document**. Do not hand-write a `wiki/sources/*` page for it — route it through the CLI:

1. Run the add command:
   ```bash
   python3 -m llmwiki add <src> --project <slug>
   ```
   `<src>` may be a URL, a file path, or a folder (repeatable — pass several sources in one invocation to batch the synthesize/build pass). `--project <slug>` groups the doc under `raw/docs/<slug>/` instead of letting it derive its own slug; pick a slug that matches the topic/project being ingested. Useful extra flags: `--title` (override title derivation, single source only), `--tag` (repeatable), `--note` (blockquote prepended to the body), `--dry-run` (convert and report, write nothing), `--no-synthesize` / `--no-build` (skip those passes if you intend to batch several `add` calls before a final build).
2. `llmwiki add` resolves the vault itself (see the warning below), writes the converted doc under `raw/docs/`, records synth state, synthesizes the `wiki/sources/<slug>.md` page, updates `wiki/index.md` / `wiki/overview.md`, and rebuilds the site — that's the whole document pipeline in one command.
3. Read the resulting `wiki/sources/<slug>.md` page in the resolved vault to see what was synthesized.
4. Create/update entity pages (`wiki/entities/<TitleCase>.md`) for any people, companies, products, tools, libraries mentioned in the synthesized page.
5. Create/update concept pages (`wiki/concepts/<TitleCase>.md`) for any ideas, patterns, or decisions discussed.
6. Create/update project pages (`wiki/projects/<kebab-case>.md`, `type: project`) for any codebase or work stream mentioned — a project is its own page kind, never an entity page.
7. Cross-link everything with `[[wikilinks]]` under `## Connections`.
8. Flag contradictions under `## Contradictions` if the new source conflicts with existing wiki content.
9. Append to `wiki/log.md`: `## [YYYY-MM-DD] ingest | <title>`

### ⚠️ Vault resolution — read before writing anything by hand

`llmwiki add` resolves the target vault itself (`--vault`, else `config.json` → `vault.default_path`, else the current working directory), so step 1 is always safe as written. Everything you write **by hand** in steps 4–8 (entity pages, concept pages, project pages, index/log edits) must land in that **same resolved vault**:

- Check `config.json` → `vault.default_path` (or whatever `--vault` you passed to `add`) before writing any manual page.
- Do not write entity/concept/project pages into a different tree than the one `add` just used.

## Workflow — session transcripts (`raw/sessions/`)

Session transcripts are already produced by `llmwiki sync`; there's no `add` step. Summarize them by hand per this **Ingest Workflow**:

1. Read the source file(s) with the Read tool
2. Read `wiki/index.md` and `wiki/overview.md` for context
3. Write `wiki/sources/<slug>.md` using the Source Page Format
4. Update `wiki/index.md` — new entry under `## Sources`
5. Update `wiki/overview.md` if substantial new info
6. Create/update entity pages (`wiki/entities/<TitleCase>.md`)
7. Create/update concept pages (`wiki/concepts/<TitleCase>.md`)
8. Create/update the project page (`wiki/projects/<kebab-case>.md`, `type: project`)
9. Cross-link with `[[wikilinks]]` under `## Connections`
10. Flag contradictions under `## Contradictions`
11. Append to `wiki/log.md`: `## [YYYY-MM-DD] ingest | <title>`

### Session-specific rules

When the source is under `raw/sessions/` (a session transcript converted by the converter):

- **Trust the frontmatter** as authoritative (project, started, model, tools_used, etc.)
- **Do not copy the `## Conversation` section verbatim** — use it as raw material to summarise
- **Create the project page** at `wiki/projects/<project-slug>.md` (`type: project`, slug from the frontmatter `project` field) with a `## Sessions` list
- **Extract decisions** into `wiki/concepts/` — anything the user explicitly locked
- **Extract tools used** — every entry in `tools_used` is a candidate entity
- **If `is_subagent: true`** — link to the parent session rather than creating a new project page

## Hard rules

1. `raw/` is immutable. Never modify files there.
2. Documents route through `llmwiki add`; never hand-write a `wiki/sources/*` page for a document.
3. No silent overwrites. Conflicting claims go under `## Contradictions`.
4. Every page has a `## Connections` section with at least one `[[wikilink]]`.
5. Frontmatter is authoritative. Always populate `title`, `type`, `tags`, `sources`, `last_updated`.
6. Resolve the vault before writing anything by hand — see the warning above.
