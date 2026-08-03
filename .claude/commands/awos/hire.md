---
description: Hires specialist agents — finds, installs skills, MCPs, and agents from registry, generates agent files.
argument-hint: '[focus areas, optional]'
allowed-tools: Bash(npx *), Bash(bunx *), Read, Write, Glob, Grep
---

@.awos/commands/hire.md

Project notes (Cursor + Claude):

- The recruitment MCP tool is named `search_capabilities` (not `search`).
- Prefer `bunx @provectusinc/awos-recruitment …` in this repo; fall back to `npx` only if bun is unavailable.
