---
title: "CLI reference (part 14/19: install-agent-kit — copy packaged slash commands and skills (#109))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, agent-kit, manifest-tracking, file-pruning, backup-strategy]
date: 2026-09-28
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-28
---
## Summary

The `install-agent-kit` CLI command copies packaged slash commands and skills from the llmwiki package into agent directories (Claude Code, Cursor, Codex CLI, or local projects). It uses a manifest file (`.llmwiki-agent-kit.json`) with content digests to classify file updates as outdated, customised, or unchanged, and automatically prunes retired commands while preserving user-edited files based on content—never file names.

## Key Claims

1. The `--dest` flag is required; the command does not guess at agent directory conventions and supports multiple destinations (`~/.claude`, `~/.cursor`, `~/.codex`, or project-local `.claude/`).

2. File updates are classified by content digests: outdated files (matching known llmwiki bytes) are replaced without backup; customised files (unrecognised bytes) are backed up to `.bak` before replacement; unchanged files are left alone.

3. Pruning is gated on content digests from two sources: a hardcoded list of retired paths with their historical digests, and the manifest file recording what the current install placed. Only files matching known digests are deleted; unrecognised files and customised retired commands are preserved.

4. The manifest file (`.llmwiki-agent-kit.json`) should be committed to git alongside commands and skills so later upgrades can recognise their own files for cleanup and enable correct classification of updates.

5. Contributor-only commands and skills (fix-bug, implement-feature, release) remain in the repository's `.claude/` tree and are not distributed as part of the package.

## Key Quotes

> "The files are plain markdown and the format is portable, so an agent with a different layout can take the same `commands/` and `skills/` folders."

Highlights the agent-independence of the command/skill format, enabling reuse across different tools and layouts.

> "No `.bak` — these are llmwiki's own bytes, so a backup of them is noise, and writing one can overwrite a real backup beside it."

A precise design decision: outdated files (known llmwiki installs) are not backed up to avoid noise and collisions with real user backups.

> "Because only bytes llmwiki itself wrote are ever removed, a prune makes no backup; only files are removed — never directories."

Articulates the conservative pruning strategy: content-gating ensures user files and customised commands are never touched.

## Connections

- [[llmwiki]] (entity) — the package providing the install-agent-kit command and the agent kit system
  - fact: The command is accessed as `python3 -m llmwiki install-agent-kit`.
  - fact: Agent kit contents (commands and skills) are stored in `llmwiki/agent_kit/` within the package.

- [[Claude Code]] (entity) — an agent tool that reads installed commands and skills
  - fact: Installing to `~/.claude` makes the kit available to Claude Code across all projects on the machine.

- [[Cursor]] (entity) — an agent tool that reads the installed kit
  - fact: Cursor reads top-level `commands/` and `skills/` folders via `--dest ~/.cursor`.

- [[Codex CLI]] (entity) — another agent tool that reads the installed kit
  - fact: Codex CLI can access the kit when installed to `~/.codex`.

- [[Manifest Tracking]] (concept) — using content digests to track and classify installed files
  - fact: The manifest file `.llmwiki-agent-kit.json` records the path and SHA256 of each installed file.
  - fact: Enables classification of files as outdated, customised, or unchanged based on content matching rather than modification times.

## Contradictions

None identified.