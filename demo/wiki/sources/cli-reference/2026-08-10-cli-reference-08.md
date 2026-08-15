---
title: "CLI reference (part 8/8: watch — near-real-time maintain when sessions finish)"
type: source
tags: [wiki-add, raw-doc, session-transcript, cli-reference, watch-polling, automation-scheduler, completion-detection]
date: 2026-08-10
source_file: 
project: cli-reference
model: 
last_updated: 2026-08-11
---
## Summary

Documents two CLI commands that automate [[LLM-Wiki]] maintenance workflows. `watch` polls adapter session stores at a configurable interval and triggers the full maintain cycle (`sync` → `synthesize` → `build`) when sessions complete, using adapter-specific completion heuristics and enforcing single-flight concurrency. `install-automation` sets up OS-level scheduled automation (systemd timers on Linux, launchd on macOS) with three operation profiles and optional agent sync hooks, writing automation status for site dashboards.

## Key Claims

- The `watch` command detects session completion via per-adapter heuristics: Claude's `stop_reason`, Cursor's last role detection, and Codex events; adapters without a completion signal fall back to a 2-second file modification time (mtime) settle before triggering
- `watch` enforces single-flight semantics: only one maintain iteration runs at a time; concurrent changes set a dirty flag and retry after the current run completes
- Sync operations in `watch` may time out (~180 seconds); `synthesize` and `build` steps have no timeout
- `install-automation` offers three profiles (A: sync with auto-build; B: sync without auto-build + synthesize + build; C: all steps + skip graph build)
- Systemd timer units use `Persistent=true` to ensure missed scheduled runs catch up after system reboot
- Agent hooks are disabled by default and explicitly not recommended; users should prefer the OS scheduler or `watch` instead

## Key Quotes

> "Polls adapter session stores on an interval and runs maintain when a session looks finished. Uses per-adapter turn-complete heuristics (Claude `stop_reason`, Cursor last role, Codex events)."

> "Single-flight: only one maintain iteration at a time (`sync` → `synthesize` → `build` by default). Changes that arrive during a run set a dirty flag and retry after it finishes."

> "Agent hooks default to skip — press Enter at the prompt to install nothing; type `install` to opt in (not recommended; prefer the OS scheduler or `watch`)."

## Connections

- [[LLM-Wiki]] — the maintain, synthesis, and build automation these commands orchestrate
- Adapter completion signaling — leverages per-adapter semantics (Claude, Cursor, Codex) for robust session detection
- File system monitoring — mtime settle provides a fallback for adapters without explicit completion signals
- Concurrency control — single-flight pattern prevents overlapping maintain runs during high-frequency session completion

## Contradictions

None identified (wiki is still in early stages; no conflicting content on record).