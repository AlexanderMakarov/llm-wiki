---
title: "Slash commands reference (part 4/4: Agent-kit skills)"
slug: slash-commands-reference-04
project: reference-slash-commands
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/slash-commands.md"
content_sha256: f3ee075d173ec4adfbd89b4e36ec37e1e0338ff4a016aa6702da2f7ac518551e
---

> Part 4 of 4 of **Slash commands reference** — Agent-kit skills.

## Agent-kit skills

The kit also ships four **skills** — the model invokes these on its own when what you ask for matches their description, so they cover the same work without you remembering a slash command. They land under `skills/` in the same `--dest` as the commands.

| Skill | What it does | Typical trigger |
|---|---|---|
| `llmwiki-sync` | Converts new agent sessions into `raw/sessions/` (`llmwiki sync`), then ingests what arrived | "sync the wiki", "catch me up", a question that needs recent sessions |
| `llmwiki-ingest` | Ingests one document or folder: `add` (CLI or MCP `wiki_add`) → `synth` → candidate review → `build`. Documents never become hand-written pages | "ingest this", "add this to the wiki", `/wiki-ingest` |
| `llmwiki-query` | Answers a question from the wiki, with `[[wikilink]]` citations, and offers to save a substantial answer under `wiki/syntheses/` | "what did I decide about X?", `/wiki-query` |
| `llmwiki-all` | Runs the whole pipeline end-to-end — sync → synth → build → graph → lint — and reports each stage | "run everything", "full pipeline", `/wiki-all` |

The skill is named `llmwiki-all`; the slash command it wraps is `/wiki-all`. Upgrading from a release that shipped the skill as `wiki-all` prunes the old copy when you re-run `llmwiki install-agent-kit --dest PATH` (the prune is by content, so a copy you edited is left alone and reported as `kept`).

---

## How the slash commands get installed

`llmwiki install-agent-kit --dest PATH` copies the packaged
`wiki-*.md` command files and the `skills/` folder into an agent directory —
`~/.claude` (Claude Code), `~/.cursor` (Cursor), `~/.codex` (Codex CLI) for
every project on the machine, or `.claude` for just the project you are
working in. The agent picks them up from there with no further setup.

For an agent with a different layout, point `--dest` at (or copy the installed
files into) its own command and skill directories — the file format is
portable. The destination table and the pruning rules are in
[`cli.md`](cli.md#install-agent-kit--copy-packaged-slash-commands-and-skills-109).

---

## Extending

To add a new slash command:

1. Create `llmwiki/agent_kit/commands/wiki-<name>.md` with a one-line
   docstring on line 1 (that's the summary Claude Code surfaces).
2. Describe the workflow in prose. Reference existing CLI commands
   rather than embedding shell in the body.
3. Run `/wiki-lint` — the `docs/reference/` guardrail test (see
   `tests/test_docs_structure.py`) will pick up the new command.
4. Document it here — the CI guard requires every
   `llmwiki/agent_kit/commands/*.md` file to have a matching `###` entry, and
   the count line above to match how many there are. A maintainer-only command
   goes in `.claude/commands/` and is described in
   [`../maintainers/README.md`](../maintainers/README.md) instead.

---

## Related

- **[CLI reference](cli.md)** — the underlying `python3 -m llmwiki …` surface.
- **[UI reference](ui.md)** — every screen on the compiled site, with what's reachable from where.
- **[Tutorial 03 — Use with Claude Code](../tutorials/03-use-with-claude-code.md)** — the minimum daily loop built on these commands.
