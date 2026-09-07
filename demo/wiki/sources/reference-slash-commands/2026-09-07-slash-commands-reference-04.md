---
title: "Slash commands reference (part 4/4: How the slash commands get installed)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-slash-commands, agent-kit, installation, cross-agent-support]
date: 2026-09-07
source_file: raw/docs/reference-slash-commands/slash-commands-reference-04.md
project: reference-slash-commands
model: 
last_updated: 2026-09-07
---
## Summary

The llmwiki slash commands system provides a portable mechanism to install command files across multiple agents (Claude Code, Codex CLI, Cursor, Gemini CLI) using `llmwiki install-agent-kit --dest PATH`. The documentation specifies both the installation process and the workflow for extending the system with new commands.

## Key Claims

- `llmwiki install-agent-kit --dest PATH` copies packaged `wiki-*.md` command files into agent directories for automatic discovery
- The command file format is portable across Claude Code, Codex CLI, Cursor, and Gemini CLI without modification
- New slash commands are created in `llmwiki/agent_kit/commands/wiki-<name>.md` with a one-line docstring on line 1
- The `/wiki-lint` command validates new commands against guardrail tests in `tests/test_docs_structure.py`
- Reference documentation must include a matching `###` entry and matching count for every command file
- Maintainer-only commands go in `.claude/commands/` and are documented separately in `../maintainers/README.md`

## Key Quotes

> "`llmwiki install-agent-kit --dest PATH` copies the packaged `wiki-*.md` command files into an agent directory"

Establishes the core distribution mechanism for slash commands.

> "the file format is portable across agents"

Highlights the design goal of cross-agent compatibility.

> "Run `/wiki-lint` — the `docs/reference/` guardrail test (see `tests/test_docs_structure.py`) will pick up the new command."

Describes the validation workflow for extending the system.

## Connections

- [[llmwiki]] (project) — contains the slash commands system and agent kit
- [[Claude Code]] (tool) — automatically discovers commands from `.claude` directory without further setup
- [[Codex CLI]] (tool) — supports the portable command file format via `.codex/skills/`
- [[Cursor]] (tool) — IDE supporting the same command format via `.agents/skills/`
- [[Gemini CLI]] (tool) — agent using the portable command file format

## Contradictions

None identified.