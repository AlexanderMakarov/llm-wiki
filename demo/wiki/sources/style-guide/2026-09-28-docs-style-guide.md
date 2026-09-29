---
title: "Docs style guide"
type: source
tags: [wiki-add, raw-doc, session-transcript, style-guide, docs-voice, tutorial-structure, link-conventions, docs-guardrails]
date: 2026-09-28
source_file: 
project: style-guide
model: 
last_updated: 2026-09-29
---
## Summary

This style guide establishes a minimal, evidence-first voice and fixed tutorial structure for all llmwiki documentation. Tutorials must have required sections in order (Why, Steps, Verify, Troubleshooting, Next); code blocks follow specific formatting rules (shell commands with/without `$` prefix depending on output, `python` not `py`); and relative links end in `.md` for static-site rewriting. A test suite (`test_docs_structure.py`) enforces structural compliance and link validity before any push.

## Key Claims

- The documentation voice is "minimalism + trust & authority"—evidence-first, active voice, no exclamation marks, only numbers (never subjective adjectives like "fast" or "robust").
- All tutorials must follow an exact skeleton with required sections in order: header, Why, numbered Steps, Verify, Troubleshooting, Next; the guardrail test enforces this structure.
- Shell code blocks include `$` prefixes only when output follows in the same block; Python uses the `python` language tag, not `py`.
- Relative links within docs must end in `.md` (rewritten to `.html` by the static-site build); external links must link to specific tagged versions, never `master`.
- New tutorials are numbered sequentially (e.g., `08-<slug>.md`), added to the `docs/index.md` table, and must pass the guardrail test before being pushed.

## Key Quotes

> "Minimalism + trust & authority. That's the whole brand for *prose*." — establishes the core voice principle.

> "Evidence-first. Show the command. Show the expected output. Show a number. Everything else is vapor." — encapsulates the editorial philosophy that disallows marketing language.

> "Don't narrate your narration. 'In this tutorial we'll…' is a tax on the reader. Start with the work." — guides against meta-commentary and unnecessary front-loading.

## Connections

- [[llmwiki]] (entity) — the project these docs serve.
  - fact: All documentation under `docs/` must follow this style guide; tutorials, reference pages, and tutorials are structured to read as if written by one careful person.
- [[Static Site]] (concept) — the docs are built into static HTML with cross-link rewriting.
  - fact: Relative `.md` links are rewritten to `.html` by the static-site build; the guardrail test validates that all internal cross-links resolve to real files.
- [[Lint Rules]] (concept) — the guardrail test suite protects docs from structural rot.
  - fact: `test_docs_structure.py` enforces tutorial sections, title consistency with filenames, disallows `<script>` and raw HTML, and verifies index links resolve.