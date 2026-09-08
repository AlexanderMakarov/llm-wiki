---
title: "Cut shell startup time by deferring completions"
type: source
tags: [session, session-transcript, dotfiles, claude, shell-startup-optimization, lazy-loading, shell-completions, performance-profiling]
date: 2026-06-29
source_file: raw/sessions/dotfiles/2026-06-29T15-52-dotfiles-shell-startup-profiling.md
project: dotfiles
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

Optimized shell startup time by profiling and identifying completion script loading as the main bottleneck. Implemented lazy loading of completions on first use (instead of eagerly loading them on shell initialization), reducing startup time from ~900ms to <200ms. Completions remain functional—the first tab press incurs a one-time load cost, then results are cached for the session.

## Key Claims

- Completion script loading was responsible for the majority of shell startup time (~700ms of ~900ms total)
- Some completion scripts were for tools not installed on the machine and were causing silent failures or wasting cycles
- Lazy-loading completions on first use (first tab press) achieves the same functionality while keeping startup responsive
- After optimization, startup time dropped from approximately 900ms to under 200ms
- The lazy-load cost is unnoticeable on first use (happens once per session)

## Key Quotes

> "Startup went from roughly nine hundred milliseconds to under two hundred" — quantifies the optimization impact

> "the first tab press pays the load cost once, then it is cached for the session" — explains the UX tradeoff: perceived startup is fast, but real completion overhead is deferred rather than eliminated

## Connections

- [[Dotfiles]] (project) — personal shell configuration repository where this optimization was implemented
- [[Shell Performance]] (pattern) — techniques for reducing shell initialization overhead
- [[Lazy Loading]] (pattern) — deferring expensive operations (loading completions) until they are first needed
