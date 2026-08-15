---
title: "Version the git hooks instead of copying them"
type: source
tags: [session, session-transcript, dotfiles, claude, git-hooks, config-drift, pre-push-hooks, setup-automation]
date: 2026-08-02
source_file: raw/sessions/dotfiles/2026-08-02T15-28-dotfiles-git-hooks-sync.md
project: dotfiles
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

This session addressed git pre-push hooks drifting between machines because they were stored outside the repository. The solution moves hooks into a tracked directory, configures `git core.hooksPath` to reference them, and optimizes them to check only affected files. Hook updates become normal git operations, while the `--no-verify` escape hatch is preserved.

## Key Claims

- Git pre-push hooks stored outside the repository drift between machines as developers make local changes
- Moving hooks into a tracked directory and configuring git's hooks path ensures consistency, treating hook updates like any other code change (via `git pull`)
- Hook performance is critical: checking only affected files (not the entire tree) keeps validation fast enough that developers won't be tempted to bypass it
- The standard `git push --no-verify` flag remains available; the design goal is to make skipping a deliberate act rather than the default

## Key Quotes

> "The point is that skipping is a deliberate act rather than the default state." — Expressing the design principle that safeguards should be on by default while retaining developer override capability

## Connections

- [[Git]] — the version control system and hooks mechanism being improved

## Contradictions

None identified.