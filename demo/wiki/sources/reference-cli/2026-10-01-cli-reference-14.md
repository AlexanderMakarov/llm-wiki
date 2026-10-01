---
title: "CLI reference (part 14/19: install-agent-kit — copy packaged slash commands and skills (#109))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, agent-kit, slash-commands, version-tracking]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

Describes the `install-agent-kit` CLI command, which distributes packaged slash commands and skills from the llmwiki pip package to agent directories (Claude Code, Cursor, Codex CLI, or project-local). The command uses a manifest file to track installed versions, detect user edits and outdated copies, and safely prune retired commands without touching user files.

## Key Claims

- The command copies `commands/` and `skills/` from the llmwiki package to a destination directory specified via `--dest`, making them accessible to the relevant agent
- A manifest file (`.llmwiki-agent-kit.json`) records what was installed, enabling classification of files as unchanged, outdated (from older llmwiki), or customised (user-edited) on re-runs
- Customised files receive `.bak` backups before being overwritten; outdated files are overwritten without backup since they are llmwiki's own bytes
- Pruning of retired commands uses SHA256 digests from the manifest, never filenames, ensuring user edits and pre-manifest files are never deleted
- `--dry-run` mode reports staleness and changes without writing anything

## Key Quotes

> "A pip install carries the user-facing `/wiki-*` slash commands and skills inside the package (`llmwiki/agent_kit/`). This command copies `commands/` and `skills/` beneath a directory you name so Claude Code (or any agent that reads that layout) can see them."
— Establishes the command's purpose: distributing packaged commands to agent environments

> "Only files llmwiki itself wrote are ever removed, a prune makes no backup; only files are removed — never directories."
— Safety guarantee for pruning: only files llmwiki wrote are ever deleted

## Connections

- [[llmwiki]] (entity) — packages and distributes the slash commands and skills installed by this command
  - fact: The agent kit is bundled in the llmwiki pip package under `llmwiki/agent_kit/`.

- [[Agent Kit]] (entity) — the packaged collection of slash commands and skills managed by this command
  - fact: The agent kit maintains a manifest of installed files to track versions and detect customisations.

- [[Claude Code]] (entity) — IDE extension receiving the agent kit via `~/.claude`
  - fact: Users install to `~/.claude` to make slash commands available across all projects.

- [[Cursor]] (entity) — code editor receiving the agent kit via `~/.cursor`
  - fact: The command can target `~/.cursor` because Cursor reads top-level `commands/` and `skills/` directories.

- [[Codex CLI]] (entity) — CLI tool receiving the agent kit via `~/.codex`
  - fact: Users install to `~/.codex` to make slash commands available across all projects.

## Contradictions

None identified.