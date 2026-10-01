---
title: "Cut shell startup time by deferring completions (marnitask)"
type: source
tags: [session, session-transcript, dotfiles, claude, shell-startup-optimization, lazy-loading, shell-completions, performance-profiling, shell-startup-performance, completion-caching]
date: 2026-07-22
source_file: raw/sessions/dotfiles/2026-06-29T15-52-dotfiles-shell-startup-profiling.md
project: dotfiles
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

Optimized shell startup time in dotfiles by deferring completion script loading to first use instead of eager loading at session start. Startup latency improved from approximately 900ms to under 200ms (roughly a 5x improvement). The implementation caches completions per session and gracefully handles missing tools. Changes affect interactive sessions only.

## Key Claims

- Shell startup time was dominated by eagerly loading completion scripts, including for tools not installed on the machine
- Lazy-loading completion scripts on first use reduced startup time from ~900ms to <200ms  
- Shell completions work on first tab press with a one-time per-session caching cost
- The optimization is scoped to interactive sessions only; headless execution paths remain unaffected
- Existing CLI documentation already covers the lazy-load flag; only a CHANGELOG entry is required for release notes

## Key Quotes

> "Startup went from roughly nine hundred milliseconds to under two hundred" — quantifies the performance improvement from switching to lazy-loaded completions

> "the first tab press pays the load cost once, then it is cached for the session" — explains the caching strategy that makes lazy-loading practical for end users

> "This change is interactive-session only" — clarifies the scope to exclude headless/non-interactive execution paths

## Connections

- [[Shell]] (entity) — The shell environment where startup performance was optimized through deferred completion loading.
  - fact: Interactive shell startup reduced from ~900ms to <200ms by deferring completion script initialization.
  - fact: Completions load on first tab press with per-session caching.

- [[Configuration]] (entity) — Documentation approach for the optimization.
  - fact: CLI reference already documents the lazy-load flag; release notes need only a one-line CHANGELOG entry.