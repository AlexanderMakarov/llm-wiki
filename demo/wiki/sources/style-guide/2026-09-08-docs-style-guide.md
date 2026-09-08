---
title: "Docs style guide"
type: source
tags: [wiki-add, raw-doc, session-transcript, style-guide, tutorial-structure, evidence-first-docs, docs-guardrails, editorial-voice, documentation-style, pytest-docs]
date: 2026-09-08
source_file: 
project: style-guide
model: 
last_updated: 2026-09-08
---
## Summary

The session captures the canonical **docs style guide** for everything under `docs/`: voice (minimalism, evidence-first, no hype), a fixed tutorial skeleton enforced by structure tests, callout and code-block conventions, linking rules, and checklists for adding tutorials and reference pages. It ties editorial quality to `tests/test_docs_structure.py` and a local `llmwiki build` before shipping doc changes.

## Key Claims

- The editorial brand for llmwiki docs is **minimalism plus trust and authority**—concrete commands, numbers, and outputs instead of marketing adjectives.
- Every file under `docs/tutorials/` must use the same section order (header, Why, numbered Steps, Verify, Troubleshooting, Next), and `tests/test_docs_structure.py` enforces that layout plus link resolution from `docs/index.md`.
- Body copy must not use exclamation marks or emoji; callouts use blockquote prefixes **Trusted.**, **Warning.**, and **Result.** only, styled by `.docs-shell` CSS.
- In bash fences, `$` appears only when the block includes the command’s output on following lines; otherwise the command is shown without `$`.
- Internal doc links use relative paths ending in `.md`; external links should prefer tagged release URLs over `master`.
- When adding a tutorial, the guide assumes the current last numbered tutorial is **07** and lists eight concrete steps including updating `docs/index.md`, chaining the previous tutorial’s Next link, running the structure pytest, and opening `site/docs/tutorials/<file>.html`.

## Key Quotes

> "Minimalism + trust & authority. That's the whole brand." — frames all voice and table examples in the guide.

> "Evidence-first. Show the command. Show the expected output. Show a number. Everything else is vapor." — core rule of thumb for tutorial and reference prose.

> "If X fails, it's a bug in the docs. File an issue." — preferred stance on user confusion versus hand-holding marketing copy.

> "No exclamation marks. Ever." — hard editorial constraint on body text.

> "The doc-structure guardrail test enforces this." — explicit link between tutorial skeleton and automated checks.

## Connections

- [[llmwiki]] (entity) — the guide governs how contributors write and structure documentation for this toolchain’s `docs/` tree.
  - fact: New tutorials must be registered in `docs/index.md` and validated with `python3 -m pytest tests/test_docs_structure.py`.
- [[Static Site]] (concept) — doc changes are meant to be verified via `python3 -m llmwiki build` and visual inspection of rendered HTML under `site/docs/`.
  - fact: Relative `.md` links are rewritten to `.html` at build time; broken internal links fail the structure test.
- [[GitHub Actions]] (concept) — implied by “don’t push without running the tests,” though CI is not specified in detail here.
  - fact: Guardrails exist because docs rot silently without automated structure and link checks.
