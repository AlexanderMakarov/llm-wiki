---
title: "Version the git hooks instead of copying them"
type: source
tags: [session, session-transcript, dotfiles, claude, git-hooks, configuration-drift, pre-push-hooks, hook-synchronization]
date: 2026-08-30
source_file: raw/sessions/dotfiles/2026-08-30T15-28-dotfiles-git-hooks-sync.md
project: dotfiles
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

The session addressed git hook drift across machines by versioning hooks in a tracked repository directory instead of storing them outside version control. The setup script configures git's hook path to point to the versioned directory, ensuring all machines run identical hooks when pulling updates. A performance optimization checks only files in the current push rather than the entire tree. Git's standard `--no-verify` flag remains available for deliberate bypass, making hook skipping an explicit rather than default action.

## Key Claims

- Git hooks stored outside the repository drift between machines and require manual synchronization
- Versioning hooks in a tracked repository directory and configuring git's hook path ensures consistent behavior via pull updates
- Performance optimization (checking only pushed files instead of the whole tree) makes hooks fast enough that users won't be tempted to bypass them
- Git's `--no-verify` flag allows deliberate bypass while making skipping a conscious choice rather than the default state

## Key Quotes

> "Moved the hooks into a tracked directory and pointed the hooks path at it, so they are versioned like anything else and updating is a pull."

This captures the core solution: using version control itself to distribute hook updates rather than requiring manual copying between machines.

> "The point is that skipping is a deliberate act rather than the default state."

This reflects the design philosophy that making bypass explicit (via `--no-verify`) reduces accidental hook violations.

> "The hook itself checks only the files in the push rather than the whole tree, which keeps it fast enough that nobody is tempted to skip it."

This shows the performance consideration: eliminating user friction so the hooks aren't bypassed out of frustration.

## Connections

- [[Dotfiles]] (project) — personal configuration repository where git hooks are now versioned and synchronized
  - fact: Hooks moved from outside the repository into a tracked directory with setup script configuration
  
- [[Git Hooks]] (feature) — pre-push hooks versioned and distributed through repository pull rather than manual copying
  - fact: Performance optimized to check only pushed files; git --no-verify flag remains available for deliberate bypass
  
- [[Configuration]] (concept) — managing configuration that would otherwise drift across machines by placing it under version control
  - fact: Hooks living outside version control diverge; moving them to the repository ensures all machines stay synchronized

## Contradictions

None identified.