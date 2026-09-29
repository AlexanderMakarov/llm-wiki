---
title: "Cut shell startup time by deferring completions (marnitask)"
type: source
tags: [session, session-transcript, dotfiles, claude, shell-startup-optimization, lazy-loading, shell-completions, performance-profiling, shell-startup-performance, completion-caching]
date: 2026-07-19
source_file: raw/sessions/dotfiles/2026-06-29T15-52-dotfiles-shell-startup-profiling.md
project: dotfiles
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

Optimized shell startup time by deferring completion script loading until first use. Startup time was reduced from approximately 900ms to under 200ms for interactive shells through lazy loading on first tab press, with session-level caching. Headless shells remain unaffected. Minimal documentation added (one-line CHANGELOG entry).

## Key Claims

- Shell startup time reduced from approximately 900ms to under 200ms by deferring completion script loading.
- Completion scripts are now loaded lazily on first use (first tab press) rather than eagerly at startup.
- The lazy-loading optimization applies only to interactive shells; headless sessions are unaffected.
- Tools with missing installations are skipped gracefully rather than failing silently.
- First-use completion incurs a one-time load cost that is cached for subsequent completions in the session.

## Key Quotes

> "Startup went from roughly nine hundred milliseconds to under two hundred." — demonstrating the magnitude of performance improvement achieved by deferring completion loading.

> "the first tab press pays the load cost once, then it is cached for the session" — explaining the trade-off and user experience of the optimization.

> "headless fixtures stay excluded from default synth. This change is interactive-session only." — clarifying that only interactive shells are affected by the optimization.

## Connections

- [[Dotfiles]] (entity) — the shell configuration project being optimized.
  - fact: Shell startup time reduced from ~900ms to ~200ms through lazy-loading of completion scripts.
- [[Configuration]] (entity) — documentation for the change.
  - fact: A one-line CHANGELOG entry was added under Unreleased to document the startup optimization.
- [[Shell]] (entity) — the subject of the startup performance optimization work.
  - fact: The optimization distinguishes between interactive and headless shell sessions.

## Contradictions

None identified.