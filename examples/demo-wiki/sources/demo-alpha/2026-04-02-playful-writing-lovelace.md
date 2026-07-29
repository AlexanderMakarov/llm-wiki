---
title: "Session: playful-writing-lovelace — 2026-04-02"
type: source
tags: [claude-code, session-transcript, demo, demo-alpha, claude, argparse, subcommands, i18n, pytest]
date: 2026-04-02
source_file: raw/sessions/demo-alpha/2026-04-02-playful-writing-lovelace.md
project: demo-alpha
model: claude-opus-4-6
last_updated: 2026-07-29
---
## Summary

Added a `greet` subcommand to the [[Demo-Alpha]] CLI using argparse subparsers, supporting English and French greetings via `--lang` flag. The existing single-argument CLI was refactored to use subparsers and a dispatch pattern. Tests were written for default and localized greetings, all passing before commit.

## Key Claims

- The implementation uses an argparse dispatch pattern, storing command handlers in `args.func` and invoking them after parsing
- The `greet` subcommand accepts `--name` (default: `"world"`) and `--lang` (choices: `["en", "fr"]`, default: `"en"`)
- A GREETINGS dictionary maps language codes to greeting prefixes, making the localization extensible
- The refactored CLI includes a fallback to print help when no subcommand is selected (by checking `hasattr(args, "func")`)

## Key Quotes

> "I'll refactor to subparsers with `greet` as the first subcommand." — the plan to migrate from a single-argument to a multi-command architecture

> "The CLI now supports `democli greet --lang fr --name alice`." — confirmation of the feature working end-to-end

## Connections

- [[Demo-Alpha]] — the CLI project receiving the new feature
- [[Argparse]] — the standard library used for command parsing and subcommand dispatch
- [[Pytest]] — the test framework used to validate the implementation