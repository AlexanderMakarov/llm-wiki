---
title: "Slash commands reference (part 4/4: How the slash commands get installed)"
slug: slash-commands-reference-04
project: reference-slash-commands
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-07
source: "docs/reference/slash-commands.md"
content_sha256: 89c2c1c8024aaf4a27741adc0fc10604afbc26da69181caedf1c1317103081ac
---

> Part 4 of 4 of **Slash commands reference** — How the slash commands get installed.

## How the slash commands get installed

`llmwiki install-agent-kit --dest PATH` copies the packaged
`wiki-*.md` command files into an agent directory — `--dest .claude` for the
project you are working in, or a user-level agent directory. Claude Code picks
them up from there with no further setup.

For **Codex CLI / Cursor / Gemini CLI / other agents**, point `--dest` at (or
copy the installed `wiki-*.md` files into) the corresponding skill directory
for that agent (typically `.codex/skills/` or `.agents/skills/`) — the file
format is portable across agents.

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
