---
title: "Upgrade guide (part 3/7: Unreleased — promote writes Key Facts with an LLM (#103))"
slug: upgrade-guide-03
project: upgrade-guide
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/UPGRADING.md"
content_sha256: 1edde415b51f8cacf9995db66240407df90211d0b78f27234d578b0f7b9b29e3
---

> Part 3 of 7 of **Upgrade guide** — Unreleased — promote writes Key Facts with an LLM (#103).

## Unreleased — promote writes Key Facts with an LLM (#103)

- **`llmwiki candidates promote` now needs a synthesis backend.** Promoting a page with an empty `## Key Facts` fails with `KeyFactsBackendError` unless `synthesis.backend` is `claude` or `ollama` in `config.json`. The candidate stays in `wiki/candidates/` so you can retry after configuring one. Pages that already have Key Facts, and pages whose sources never describe them, promote without any backend.
- **`llmwiki candidates merge` no longer pastes the candidate body** when the candidate is a harvest stub. Its `sources:` and Connections links are unioned into the target page and the name goes under `## Aliases`. Reviewer-written candidates still get their prose appended under `## Candidate merge — <date>`.
- **`/wiki-candidates` should use the CLI promote path** for this — do not invent a separate free-text enhance pass for the common empty-Key-Facts case.
- **Pages promoted by an earlier build carry machine-assembled Key Facts.** Those bullets were clipped from the line nearest a wikilink, so some state a fact about a different subject. Rewrite them with `llmwiki candidates rewrite-key-facts --slug <Name>` (or `--all` for every entity/concept). That also drops pasted harvest-stub `## Candidate merge` blocks left by the old merge behaviour.

## Unreleased — lint skips `wiki/archive/`

- **`llmwiki lint` no longer scans archived pages.** `wiki/archive/` is history — demoted pages and candidates you discarded — and it was being linted like the trusted layer.
- **Your warning count may go up on the first lint after upgrading.** The archived copy of a discarded candidate used to satisfy `[[wikilinks]]` pointing at it, so those links were silently counted as resolving. They were already broken; lint just stopped hiding them. Fix them by promoting a real page, or leave them if the target genuinely should not exist.
- Archived pages also stop counting toward `orphan_detection` and stop aging into `stale_candidates`, so those two rules get quieter.

## Unreleased — `llmwiki synth` rename (#90)

- **`llmwiki synth` is the primary command.** Default: synthesize pending sources, then harvest entity/concept candidates. Prefer it over `synthesize`.
- **`llmwiki synthesize` is deprecated.** It still runs (scripts keep working) but prints a warning and defaults to sources-only — the old behaviour — so upgrading does not silently write a large candidate backlog. Prefer `llmwiki synth` (or `synth --sources-only` / `synth --candidates-only`).
- **`all --with-synth` / `watch`** call `synth` (sources + candidates). Classification retries omitted names once; if still incomplete, the run fails closed (writes nothing) and names the cause. Use a backend that returns `name: entity|concept` lines.
- Slash: `/wiki-synth` preferred; `/wiki-synthesize` remains as a deprecated wrapper.

## Unreleased — candidates review gate on Home / Analytics (#84)

- **Home** shows an **Eligible sources** table (Raw → To synthesize → Synthesized → On disk; shell-handled input counts — see #81) and a **Knowledge layer** table (Candidates → Entities / Concepts; review via agent Commands). Candidates = pending `wiki/candidates/` pages (not the estimate `Candidates (pre-run state):` harvestable figure). Entities/Concepts = trusted pages after promote.
- **Every `llmwiki build`** recounts pending/stale candidates and trusted entity/concept counts into `synth.pipeline` before copying `llmwiki-state.js` into `site/` — promote/discard no longer leave a stale Home table until the next estimate.
- **Commands** agent rows are one-shot: `cd <llm-wiki-checkout> && claude|agent|codex "/wiki-candidates"` (Purpose: review/edit candidates). Slash commands load from the checkout, not the vault. Gemini CLI stays adapter-scaffold — no Home launcher.
- **Analytics** adds a **Candidates to review** section (pending + stale). Zeros are intentional: a synthesize-only vault still shows that the review gate exists.
- **No auto-promote.** Trusted hubs still require `llmwiki candidates promote|merge|discard` or agent `/wiki-candidates` / `/wiki-ingest`.
