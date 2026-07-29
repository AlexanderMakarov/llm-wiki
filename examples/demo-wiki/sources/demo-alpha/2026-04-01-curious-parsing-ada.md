---
title: "Session: curious-parsing-ada — 2026-04-01"
type: source
tags: [claude-code, session-transcript, demo, demo-alpha, claude, cli-scaffolding, pyproject-toml, argparse, subprocess-testing, python-packaging, pytest]
date: 2026-04-01
source_file: raw/sessions/demo-alpha/2026-04-01-curious-parsing-ada.md
project: demo-alpha
model: claude-sonnet-4-6
last_updated: 2026-07-29
---
## Summary

The session scaffolded a minimal Python CLI package using modern packaging standards (pyproject.toml with setuptools backend), created a single argparse-based entry point, and added a subprocess-based smoke test. The work demonstrates the essentials: project metadata, CLI registration via `[project.scripts]`, and installation/testing workflow.

## Key Claims

- A functional Python CLI package requires only three source files: `pyproject.toml`, `__init__.py`, and `cli.py`
- The `[project.scripts]` table in pyproject.toml automatically registers a CLI command name without manual shell wrappers
- Argparse-based CLI functions can be tested via subprocess invocation (`python -m democli.cli`) with stdout capture
- Editable install (`pip install -e .`) enables immediate CLI invocation and rapid iteration during development

## Key Quotes

> "You can install it in editable mode with `pip install -e .` and run `democli --name alice`."

Captures the practical two-step workflow: configuration-driven installation and immediate CLI testing.

> "a minimal Python CLI package with pyproject.toml, a single `main()` entry point, and one smoke test"

Concise summary of the complete minimal artifact—metadata, entry logic, and verification.

## Connections

This session is a self-contained technical demonstration with no dependencies on prior sessions or external wiki topics.

## Contradictions

None identified.