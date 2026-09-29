---
title: "Getting started (part 1/2)"
type: source
tags: [wiki-add, raw-doc, session-transcript, getting-started, vault-setup, agent-detection, shell-completion, multi-agent-support, config-json]
date: 2026-09-28
source_file: 
project: getting-started
model: 
last_updated: 2026-09-28
---
## Summary

This is the first part of the LLM Wiki getting started guide, covering installation, vault setup, agent detection, and shell completion configuration. It emphasizes that [[llmwiki]] requires only Python ≥3.12 and git, keeping personal data in a vault directory separate from the code repository. The setup process is idempotent and offers optional configuration of multiple coding-agent sources via [[Adapters]].

## Key Claims

- LLM Wiki requires Python ≥ 3.12, git, and existing sessions from at least one supported agent (Claude Code, Codex CLI, Cursor Agent CLI, OpenClaw, Copilot, or Gemini); agents are auto-detected by default.
- A vault (personal data directory) is completely separate from the code repository, ensuring transcripts and wiki pages never land in git; the vault location is configured via `config.json` under `vault.default_path`.
- The setup process is idempotent: it installs the markdown runtime dependency, runs `llmwiki adapters` to detect agents, and reports sync status without creating vault structure inside the clone.
- Multiple coding agents are ingested simultaneously through [[Adapters]]; a bare `llmwiki sync` runs every enabled agent source whose store exists on disk.
- Shell completion for bash and zsh is installed optionally during setup via `./setup.sh` and stored in `~/.bashrc` or `~/.zshrc` (or `~/.bash_profile` on macOS).

## Key Quotes

> "Your transcripts, wiki pages, and built site live in a separate **vault** directory *outside* the repo, so personal data never lands in git."

The vault architecture is fundamental — it separates the engine code from user data.

> "A bare `llmwiki sync` runs every **enabled** coding-agent source whose store exists on disk."

This demonstrates how [[Adapters]] enable detection and ingestion from multiple agents simultaneously.

> "No `npm`, no `brew`, no database, no account."

LLM Wiki is self-contained with minimal external dependencies.

## Connections

- [[llmwiki]] (entity) — the core product; this guide is its primary on-ramp.
  - fact: Installation requires Python ≥ 3.12, git, and sessions from at least one supported agent.
  - fact: The vault (personal data directory) stays separate from the code repo.
  - fact: Setup is idempotent and scaffolds vault structure only in the external vault directory, never in the clone.

- [[Adapters]] (entity) — the mechanism enabling multi-agent session ingestion.
  - fact: Adapters detect and ingest sessions from Claude Code, Codex CLI, Cursor Agent CLI, OpenClaw, Copilot, and Gemini.
  - fact: `llmwiki adapters` lists detected agents; `llmwiki configure-sources` probes stores and configures adapter settings interactively.

- [[Claude Code]] (entity) — a supported session source; sessions ingested from `~/.claude/projects/...`.

- [[Codex CLI]] (entity) — a supported session source via [[Adapters]].

- [[Cursor]] (entity) — a supported session source (referenced as "Cursor Agent CLI").

- [[GitHub Copilot]] (entity) — a supported session source (referenced as "Copilot").

- [[Gemini CLI]] (entity) — a supported session source (referenced as "Gemini").

## Contradictions

None identified.