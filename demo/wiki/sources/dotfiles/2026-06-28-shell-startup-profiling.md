---
title: "Cut shell startup time by deferring completions"
type: source
tags: [session, session-transcript, dotfiles, claude, shell-startup, lazy-loading, completion-caching]
date: 2026-06-28
source_file: raw/sessions/dotfiles/2026-06-28T15-52-dotfiles-shell-startup-profiling.md
project: dotfiles
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

Profiled shell startup to identify performance bottleneck: completion scripts were loaded eagerly, including many for uninstalled tools. Implemented lazy loading of completions, deferred until first use and cached per-session. Startup improved from approximately 900ms to under 200ms while preserving tab-completion functionality.

## Key Claims

- Completion script loading was the primary cause of slow shell startup (~900ms)
- Lazy loading reduced startup time to under 200ms
- Uninstalled tool completions now skip gracefully rather than failing silently
- Completions work on first use with a one-time load cost paid on first tab press
- Completion cache persists for the session after initial load

## Key Quotes

> "Most of the time was loading completion scripts eagerly, including several for tools not installed on this machine." — Root cause identification from startup profiling

> "Startup went from roughly nine hundred milliseconds to under two hundred." — Quantified performance improvement

> "The first tab press pays the load cost once, then it is cached for the session." — Explanation of the tradeoff in lazy-loading approach

## Connections

- [[Shell]] (system) — the command-line environment being optimized for faster startup
  - fact: Completion script loading was the primary performance bottleneck
- [[Configuration]] (concept) — dotfiles as the vehicle for shell startup optimization
- [[Lazy Loading]] (technique) — strategy to defer resource loading until first use
  - fact: Completions are loaded on first tab press and cached per-session

## Contradictions

None identified.