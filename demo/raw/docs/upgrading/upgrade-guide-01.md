---
title: "Upgrade guide (part 1/8)"
slug: upgrade-guide-01
project: upgrading
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/UPGRADING.md"
content_sha256: c3075657888a257c11c0c2658857c42e4c57a45b7e70f26eac2aec1c3b5b4614
---

> Part 1 of 8 of **Upgrade guide**.

---
title: "Upgrade guide"
type: navigation
docs_shell: true
---

# Upgrade guide

How to upgrade between `llmwiki` releases. Most releases are drop-in (`pip install -U llm-wiki-plus` or `brew upgrade llmwiki`) — this page documents the exceptions: schema migrations, config changes, and behaviour flips that affect what happens on your next `sync`.

The canonical per-release detail is [CHANGELOG.md](https://github.com/AlexanderMakarov/llm-wiki/blob/main/CHANGELOG.md) — this guide focuses on "what might break".

## Unreleased — discard rewrites links to the discarded name (#282)

Optional one-time cleanup. `candidates discard` now turns every `[[link]]` to the discarded name into plain text (or, with `--redirect PAGE`, into `[[PAGE|text]]` plus a `## Aliases` entry on that page), and the synth topic vocabulary no longer offers discarded names. Candidates you discarded **before** this release still have links pointing into `wiki/archive/`, which `lint` reports under `link_integrity`. Clean them up offline — no LLM call, `raw/` never written, safe to re-run:

```bash
llmwiki migrate discarded-topic-links --vault /path/to/vault --dry-run
llmwiki migrate discarded-topic-links --vault /path/to/vault
# point some names at an existing page instead of unlinking them:
llmwiki migrate discarded-topic-links --vault /path/to/vault --redirect "Old Name=ExistingPage"
```

The same run moves candidate stubs that a `/` in their name had filed into a subfolder (`candidates/entities/A/B thing.md`) to their flat path (`candidates/entities/A-B thing.md`); an existing file at the flat path is never overwritten and is reported as a conflict. Rebuild afterwards: `llmwiki build --vault <vault>`. `discard()` callers in Python now receive a `DiscardResult` — use `.path` for the archived file.

**Expect suggestions on the first run if you ever used `candidates merge`.** A merged candidate's links belong on the page it was merged into, and a survivor page only answers to the merged-away name through the `## Aliases` entry that merges started recording in #139. For an older merge — or one whose survivor you later renamed or re-filed — the archived `reason.txt` is the last record of where those links point. The migration therefore leaves such a name linked and prints what it thinks the page is, exiting 1:

```text
merged, left linked: 1
  - Old Name — merged into foo (587 links)
      --redirect "Old Name=code-foo"
```

Check each suggested page, then re-run with those `--redirect` lines (`--redirect "Old Name=code-foo"`), which points the links at the survivor and records the alias so the next run reports nothing. If a name really was noise rather than a merge, `--force` unlinks it like any dismissal. The rest of the run applies either way, so you can take the redirects in a second pass.

## Unreleased — `add` / `wiki_add` no longer synthesize by default (#273)

Behaviour flip, no data migration. Scripts and agents that expected synth-on-add must opt in:

- **Default:** `llmwiki add` and MCP `wiki_add` write raw docs and rebuild the site; they do **not** create `wiki/sources/` pages.
- **Opt in:** pass `--synthesize` (CLI) or `synthesize: true` (MCP) on the same invocation, or run `llmwiki synth` afterward.
- **`--no-synthesize`:** warn+no-op for one release (synthesis is already off); remove it when convenient.
- **`--no-build` / `no_build`:** still skip the site rebuild.
- **Stdin / MCP text:** `llmwiki add -` and MCP `content` record `source: "piped"` (no tempfile provenance).

## Unreleased — synth clean stop on Ctrl+C or backend usage limit (#181)

Behaviour flip, no data migration. Scripts and schedulers that read exit codes should check these:

- **New exit code `75`:** `synth` and `all` exit `75` when the synthesis backend (Claude CLI, Cursor Agent CLI or Ollama) reports an exhausted usage quota in its error message. The run stops starting new sources, finishes the pages in flight, harvests what landed, and leaves the rest pending (`Deferred:` in `wiki/log.md`) instead of logging one error per remaining source. Treat `75` as "retry after the reset time", not as a failure. A plain rate-limit `429` ("Too Many Requests") is still a per-source error.
- **`all` no longer returns `0` after Ctrl+C:** an interrupted synth step now makes `all` exit `130` (later stages still run for the pages that landed). A second Ctrl+C while in-flight pages finish kills the Claude / Cursor CLI processes and ends the run at once; with Ollama it waits for in-flight requests up to the Ollama timeout.
- **Lint failure no longer masks earlier codes:** `all --lint-fail …` used to return `2` even when an earlier step had failed; now the code of the earliest failing step wins — lint's `2` applies only when no earlier step failed.
- **Reinstall automation:** wrappers installed by `install-automation` before this release always logged `EXIT:0`. Run `llmwiki install-automation` again so the log's `EXIT:` line and the scheduler both see the real exit code.
