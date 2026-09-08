---
title: "Slash commands reference (part 4/4: How the slash commands get installed)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-slash-commands, install-agent-kit, agent-kit-commands, docs-structure-ci, multi-agent-setup, portable-agent-skills]
date: 2026-09-08
source_file: 
project: reference-slash-commands
model: 
last_updated: 2026-09-08
---
## Summary

This part of the slash-commands reference explains how wiki slash commands are installed with `llmwiki install-agent-kit --dest PATH`, which copies packaged `wiki-*.md` files into an agent directory (for example `.claude` for Claude Code). The same command file format is intended to work across Codex CLI, Cursor, Gemini CLI, and other agents when files are placed in that agent’s skill directory (often `.codex/skills/` or `.agents/skills/`). It also documents how maintainers add new commands under `llmwiki/agent_kit/commands/`, run `/wiki-lint`, and keep `docs/reference/slash-commands.md` in sync via CI guardrails in `tests/test_docs_structure.py`.

## Key Claims

- `llmwiki install-agent-kit --dest PATH` copies packaged `wiki-*.md` command files into the given agent directory; Claude Code loads them from there without extra setup when `--dest` points at `.claude` (project or user-level).
- For Codex CLI, Cursor, Gemini CLI, and similar agents, `--dest` (or a manual copy) should target that agent’s skill directory; the markdown command format is described as portable across agents.
- A new user-facing slash command is added by creating `llmwiki/agent_kit/commands/wiki-<name>.md` with a one-line summary on line 1, prose workflow referencing existing CLI commands rather than embedded shell, then validating with `/wiki-lint`.
- CI requires every file in `llmwiki/agent_kit/commands/*.md` to have a matching `###` entry in the slash-commands reference and the documented command count to match the number of kit commands.
- Maintainer-only commands belong under `.claude/commands/` and are documented in `docs/maintainers/README.md`, not in the public slash-commands reference.

## Key Quotes

> "`llmwiki install-agent-kit --dest PATH` copies the packaged `wiki-*.md` command files into an agent directory — `--dest .claude` for the project you are working in, or a user-level agent directory." — Defines the primary install path for Claude Code users.

> "For **Codex CLI / Cursor / Gemini CLI / other agents**, point `--dest` at (or copy the installed `wiki-*.md` files into) the corresponding skill directory for that agent (typically `.codex/skills/` or `.agents/skills/`) — the file format is portable across agents." — States multi-agent deployment and portability expectations.

> "the CI guard requires every `llmwiki/agent_kit/commands/*.md` file to have a matching `###` entry, and the count line above to match how many there are." — Links kit commands to reference docs and automated enforcement.

## Connections

- [[llmwiki]] (entity) — Owns `install-agent-kit`, the `agent_kit/commands/` tree, and the slash-command workflows those files describe.
  - fact: User-facing wiki commands ship as `wiki-*.md` under `llmwiki/agent_kit/commands/` and are installed via `llmwiki install-agent-kit`.
- [[Claude Code]] (entity) — Default install target via `--dest .claude`; commands are picked up without further configuration.
  - fact: Project- or user-level `.claude` is the documented destination for Claude Code.
- [[Codex CLI]] (entity) — Install/copy target is typically `.codex/skills/` using the same portable command markdown.
- [[Cursor]] (entity) — Listed among agents that use a skill directory (e.g. `.agents/skills/`) rather than `.claude` alone.
- [[Gemini CLI]] (entity) — Named alongside other non-Claude agents that consume the same portable `wiki-*.md` format.
- [[Adapters]] (concept) — Slash commands orchestrate sync/synth/build for multiple session sources; install paths differ per agent runtime even though kit files are shared.
- [[Wiki Synthesis]] (concept) — Commands such as `/wiki-synth` and `/wiki-sync` (documented in the broader reference) depend on kit install being correct before agents can run the canonical loop.
