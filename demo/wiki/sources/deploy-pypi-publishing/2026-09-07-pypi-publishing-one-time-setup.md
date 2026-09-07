---
title: "PyPI publishing — one-time setup"
type: source
tags: [wiki-add, raw-doc, session-transcript, deploy-pypi-publishing, github-actions, oidc-trusted-publisher, release-automation, release-workflow, distribution-naming, github-environments]
date: 2026-09-07
source_file: 
project: deploy-pypi-publishing
model: 
last_updated: 2026-09-07
---
## Summary

Establishes the one-time PyPI configuration required to enable `pip install llm-wiki-plus` for [[llmwiki]]. The distribution is named `llm-wiki-plus` to bypass PyPI's name-normalization rules that reject both `llmwiki` (already registered to another author) and `llm-wiki` (normalizes identically). Setup uses OIDC trusted publisher for secure, token-free uploads via [[GitHub Actions]].

## Key Claims

- The distribution must be named `llm-wiki-plus` because PyPI's name normalization renders `llm-wiki` identical to `llmwiki`, which is already registered to another author.
- The CLI command (`llmwiki`), Python import (`import llmwiki`), and GitHub repository name remain unchanged; only the distribution name carries the `-plus` suffix, following the pillow/PIL pattern.
- OIDC trusted publisher replaces long-lived credentials, configured via a GitHub environment named `release` with optional protection rules (required reviewers, wait timer, branch restrictions).
- The `PYPI_PUBLISHING` variable normally enables the `publish` job; a skipped publish indicates intentional disabling.
- The `smoke` test always runs and fails the entire workflow if the installed version doesn't match the tag, preventing silent publish/install mismatches.

## Key Quotes

> "Only the *distribution* name carries the suffix. The CLI command, the Python import (`import llmwiki`), and the GitHub repo (`AlexanderMakarov/llm-wiki`) are all unchanged — the same split as `pillow` → `import PIL`." — explains the distribution naming strategy and its precedent.

> "That gate is an escape hatch for a fork with no trusted publisher, not a normal state here: the variable is set on this repo, so a skipped `publish` means someone turned releases off." — clarifies the default state of PYPI_PUBLISHING.

## Connections

- [[llmwiki]] (project) — the application being distributed
  - fact: Published to PyPI as `llm-wiki-plus`, with CLI/import/repo names unchanged.
- [[GitHub Actions]] (platform) — the CI/CD workflow automating build, publish, and verification
  - fact: Uses OIDC trusted publisher instead of long-lived API tokens, with optional environment protection.

## Contradictions

None identified. (Historical references to `llm-notebook` as a distribution name are documented as upstream project history, not applicable to this fork's publishing scheme.)