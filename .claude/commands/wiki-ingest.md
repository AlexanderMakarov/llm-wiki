Ingest a source document (or folder) into the llmwiki.

Usage: /wiki-ingest <path>

`$ARGUMENTS` should be a path relative to the repo root, a folder, or a URL. Examples:

- `/wiki-ingest raw/docs/some-article.md`
- `/wiki-ingest https://example.com/some-article`
- `/wiki-ingest raw/sessions/ai-newsletter/2026-04-04-kind-tinkering-hejlsberg.md`
- `/wiki-ingest raw/sessions/ai-newsletter/`
- `/wiki-ingest raw/sessions/`

## Documents (files, folders, URLs, PDFs — anything not already under `raw/sessions/`)

Route the source through the `llmwiki add` CLI instead of hand-writing a `wiki/sources/*` page:

```bash
python3 -m llmwiki add <src> --project <slug>
```

`<src>` is `$ARGUMENTS` (URL, file, or folder — repeatable). `--project <slug>` groups the doc under `raw/docs/<slug>/`; choose a slug matching the topic. The command resolves the vault (`--vault` / `config.json` → `vault.default_path`), converts the source, lands it under `raw/docs/`, synthesizes the `wiki/sources/<slug>.md` page, updates the index/overview, and rebuilds the site in one pass. Other useful flags: `--title`, `--tag` (repeatable), `--note`, `--dry-run`, `--no-synthesize`, `--no-build`.

After it runs:

1. Read the synthesized `wiki/sources/<slug>.md` page (in the resolved vault) to see what was produced.
2. Create or update `wiki/entities/<Name>.md` for any people, companies, projects, tools, libraries mentioned.
3. Create or update `wiki/concepts/<Name>.md` for any ideas, patterns, or frameworks discussed.
4. Cross-link everything with `[[wikilinks]]` under `## Connections`.
5. Flag any contradictions with existing wiki content under `## Contradictions`.
6. Append to `wiki/log.md`: `## [YYYY-MM-DD] ingest | <title>`

**Vault resolution warning**: `llmwiki add` resolves the vault for you, but every page you write by hand in steps 2–6 must go into that *same* resolved vault (check `config.json` → `vault.default_path`, or the `--vault` you passed). This repo's own `wiki/` is seed demo content — never write entity/concept pages, index, or log entries there when a real vault is configured. Only fall back to this repo's `wiki/` when no vault is configured at all.

## Session transcripts (already under `raw/sessions/`)

These were already converted by `llmwiki sync` — there's no `add` step. Follow the **Ingest Workflow** exactly as defined in `CLAUDE.md`:

1. Read the source file (or every file in the folder) using the Read tool
2. Read `wiki/index.md` and `wiki/overview.md` for current context
3. Write `wiki/sources/<slug>.md` per the Source Page Format in `CLAUDE.md`
4. Update `wiki/index.md` — add the new source under `## Sources`
5. Update `wiki/overview.md` if the source adds substantial new information
6. Create or update `wiki/entities/<Name>.md` for any people, companies, projects, tools, libraries mentioned
7. Create or update `wiki/concepts/<Name>.md` for any ideas, patterns, or frameworks discussed
8. Cross-link everything with `[[wikilinks]]` under `## Connections`
9. Flag any contradictions with existing wiki content under `## Contradictions`
10. Append to `wiki/log.md`: `## [YYYY-MM-DD] ingest | <title>`

Also apply the session-specific rules from `CLAUDE.md` §"Session-derived source specifics":

- Trust the frontmatter as authoritative metadata
- Do not copy the `## Conversation` section verbatim
- Create or update the project entity page
- Extract any explicit decisions into `wiki/concepts/`
- If there are more than ~20 files, ask the user before processing all of them

After finishing, summarise: what was added, which pages were created or updated, any contradictions found.
