---
title: "Version the git hooks instead of copying them"
type: source
tags: [session, session-transcript, dotfiles, claude, git-hooks, configuration-sync, config-sync, machine-sync, setup-automation]
date: 2026-09-23
source_file: raw/sessions/dotfiles/2026-08-31T15-28-dotfiles-git-hooks-sync.md
project: dotfiles
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

Resolved git hook synchronization drift across machines by moving pre-push hooks into the repository and versioning them with the rest of the codebase. A setup script automates wiring the hooks path during initialization, and the hook checks only files in the push (rather than the whole tree) to maintain acceptable performance and prevent users from skipping the check.

## Key Claims

- Git hooks maintained outside the repository cause drift between machines with different versions
- Moving hooks into a tracked directory and configuring `git.core.hooksPath` enables version control and pull-based updates
- Setup scripts can automate initial wiring of the hooks path during development environment initialization
- Limiting pre-push hook scope (scanning only pushed files) is critical to maintaining performance and adoption

## Key Quotes

> "Moved the hooks into a tracked directory and pointed the hooks path at it, so they are versioned like anything else and updating is a pull." — demonstrates treating git hooks as first-class repository artifacts

> "kept it fast enough that nobody is tempted to skip it" — performance optimization as a prerequisite for developer adoption of safety checks

## Connections

- [[Git]] (entity) — version control system providing hooks mechanism for enforcing pre-push validation
- [[Shell]] (entity) — scripting language used to implement pre-push hook logic and setup automation
- [[Dotfiles]] (entity) — configuration management practice of versioning development environment setup and initialization scripts in a repository