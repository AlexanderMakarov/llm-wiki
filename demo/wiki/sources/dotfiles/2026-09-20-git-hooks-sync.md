---
title: "Version the git hooks instead of copying them"
type: source
tags: [session, session-transcript, dotfiles, claude, git-hooks, configuration-sync, config-sync]
date: 2026-09-20
source_file: raw/sessions/dotfiles/2026-08-31T15-28-dotfiles-git-hooks-sync.md
project: dotfiles
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

The session describes a solution to prevent git hooks from drifting across machines: moving pre-push hooks into a tracked repository directory and configuring git to use that path via the setup script. This makes hooks versioned artifacts updated via normal git pull workflow. A performance optimization—checking only pushed files rather than the entire tree—keeps hook execution fast enough to prevent developers from bypassing it.

## Key Claims

- Pre-push hooks were drifting between machines because they lived outside the tracked repository
- Moving hooks into a tracked directory and pointing git's hooks path at it makes them versioned configuration artifacts updatable via git pull
- The setup script centralizes wiring the hooks path, so new clones automatically get the right configuration
- Checking only pushed files (not the whole tree) maintains fast execution, reducing friction that might cause developers to skip the hook

## Key Quotes

> "Moved the hooks into a tracked directory and pointed the hooks path at it, so they are versioned like anything else and updating is a pull."
— The core solution: leverage git's native hooks path configuration to version control hook scripts as repository artifacts.

> "the hook itself checks only the files in the push rather than the whole tree, which keeps it fast enough that nobody is tempted to skip it"
— Performance consideration ensuring compliance without friction.

## Connections

- [[Configuration]] (entity) — systematic management of git hooks as versioned configuration artifacts
- [[Dotfiles]] (entity) — personal configuration repository pattern combining hook scripts and setup automation