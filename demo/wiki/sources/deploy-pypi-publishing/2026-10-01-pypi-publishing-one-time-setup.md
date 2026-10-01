---
title: "PyPI publishing — one-time setup"
type: source
tags: [wiki-add, raw-doc, session-transcript, deploy-pypi-publishing, github-actions, release-automation, oidc]
date: 2026-10-01
source_file: 
project: deploy-pypi-publishing
model: 
last_updated: 2026-10-01
---
## Summary

This document is a one-time setup checklist for publishing [[llmwiki]] to PyPI as `llm-wiki-plus`. It explains the automated release pipeline (build → publish → smoke test → sign → GitHub release), justifies the distribution naming strategy, and provides step-by-step configuration instructions for [[GitHub Actions]] OIDC trusted publishing.

## Key Claims

1. The distribution name must be `llm-wiki-plus` because PyPI normalizes both `llmwiki` and `llm-wiki` to the same string, and `llmwiki` is already registered by another author; the shorter names are unavailable.
2. Only the *distribution* name carries the suffix; the Python import (`import llmwiki`), CLI command (`llmwiki`), and GitHub repository (`AlexanderMakarov/llm-wiki`) all remain unchanged, following the precedent of `pillow` → `import PIL`.
3. The publish step is gated by a `PYPI_PUBLISHING` variable; if disabled, the smoke test explicitly fails the entire run (no `continue-on-error`) so misconfigurations are never silently ignored.
4. OIDC trusted publisher authentication eliminates long-lived API tokens; [[GitHub Actions]] provides short-lived OIDC tokens that PyPI verifies against the pre-registered owner, repository, workflow name, and environment.
5. The one-time setup requires five sequential steps: reserve the project name on PyPI, bind GitHub as a trusted publisher, create a `release` GitHub environment, enable `PYPI_PUBLISHING=true`, and cut a signed tag to trigger the workflow.

## Key Quotes

> "Only the *distribution* name carries the suffix. The CLI command, the Python import (`import llmwiki`), and the GitHub repo (`AlexanderMakarov/llm-wiki`) are all unchanged — the same split as `pillow` → `import PIL`."

This clarifies the naming confusion: `pip install llm-wiki-plus` resolves to a package users import as `llmwiki` and invoke as `llmwiki` on the command line.

> "a tag that publishes nothing (gate off) and a tag that publishes something uninstallable both turn the whole run red instead of passing quietly (#210). No `continue-on-error`."

The smoke test design ensures that publish misconfigurations (whether the step was skipped or succeeded with an uninstallable artifact) always surface as visible failures rather than silent passes.

> "This binds the GitHub OIDC identity to PyPI so the workflow can upload without a long-lived API token."

OIDC trusted publishers improve security by using short-lived tokens scoped to specific workflow contexts, eliminating credential rotation and storage burden.

## Connections

- [[llmwiki]] (entity) — the project being published to PyPI as `llm-wiki-plus`
  - fact: The distribution name differs from the import and CLI names due to PyPI normalization rules colliding with an existing registration.
- [[GitHub Actions]] (entity) — the CI/CD platform orchestrating the release pipeline
  - fact: The `release.yml` workflow uses OIDC trusted publisher authentication to upload to PyPI without storing long-lived secrets.

## Contradictions

None identified.