---
title: "Version the git hooks instead of copying them"
type: source
tags: [session, session-transcript, dotfiles, claude, git-hooks, configuration-sync]
date: 2026-08-31
source_file: raw/sessions/dotfiles/2026-08-31T15-28-dotfiles-git-hooks-sync.md
project: dotfiles
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

The user discovered that git pre-push hooks were drifting across machines because they lived outside the repository. The solution versioned the hooks by tracking them in a dedicated directory and wiring git's hooks path to it, making hook updates part of the normal pull workflow. To maintain acceptable performance, the hook checks only changed files rather than the entire tree. The standard `git push --no-verify` flag remains available for cases where deliberate bypass is needed.

## Key Claims

- Git hooks stored outside the repository naturally diverge across machines due to lack of synchronization
- Versioning hooks by tracking them as repository files ensures all machines run identical hook logic
- Pre-push hooks should check only files in the current push, not the entire tree, to maintain performance acceptable enough that users won't be tempted to skip them
- The standard `git push --no-verify` flag provides an escape hatch when hook bypass is legitimately needed, making skipping an explicit choice rather than a default escape

## Key Quotes

> "Hooks drifted between machines because they lived outside the repository." — Core problem: untracked hook files diverge naturally across environments.

> "Moved the hooks into a tracked directory and pointed the hooks path at it, so they are versioned like anything else and updating is a pull." — The solution treats hooks as regular version-controlled assets.

> "the hook itself checks only the files in the push rather than the whole tree, which keeps it fast enough that nobody is tempted to skip it." — Performance optimization to prevent hook-avoidance behavior.

## Connections

- [[Dotfiles]] (project) — Personal configuration repository where git hooks are now versioned alongside other setup logic.
- [[Git Hooks]] (mechanism) — Git feature for automating pre-push validation; the primary technical subject of this session.
  - fact: Hooks can be versioned by storing them in a tracked directory and configuring git's `core.hooksPath` to use it.
  - fact: Selective file checking prevents performance degradation that would tempt users to bypass hooks.
  - fact: The `--no-verify` flag remains the standard bypass mechanism, transforming hook-skipping from a hidden workaround to an explicit decision.
