---
title: "Cut shell startup time by deferring completions"
type: source
tags: [session, session-transcript, dotfiles, claude, startup-performance, shell-completions, lazy-loading, performance-profiling]
date: 2026-05-31
source_file: raw/sessions/dotfiles/2026-05-31T15-52-dotfiles-shell-startup-profiling.md
project: dotfiles
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

Session optimized shell startup time by identifying and deferring completion script loading. Profiling revealed that eagerly loading completion scripts—even for tools not installed—dominated the startup cost. Refactoring to lazy-load completions on first tab press reduced startup from ~900ms to <200ms, with the one-time load cost on first completion request being acceptable and cached for the session.

## Key Claims

- Completion scripts were loaded eagerly at shell startup, consuming the majority of startup time (~700ms of ~900ms total)
- Lazy loading completions (deferring until first tab press) achieved a 4.5× speedup in startup time
- Completions that reference missing tools now skip gracefully instead of failing silently
- The first tab press after shell launch incurs the load cost once per session, then completions are cached

## Key Quotes

> "Most of the time was loading completion scripts eagerly, including several for tools not installed on this machine."
— Identified root cause via profiling

> "Startup went from roughly nine hundred milliseconds to under two hundred."
— Quantified performance gain from deferral strategy

> "The first tab press pays the load cost once, then it is cached for the session. Noticeable only if you are looking for it."
— Trade-off analysis: acceptable latency on first use in exchange for faster startup

## Connections

- [[Shell]] — shell startup and configuration behavior
- [[Configuration]] — dotfiles and shell configuration management