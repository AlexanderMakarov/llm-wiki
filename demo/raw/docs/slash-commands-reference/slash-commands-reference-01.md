---
title: "Slash commands reference (part 1/4)"
slug: slash-commands-reference-01
project: slash-commands-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/slash-commands.md"
content_sha256: b914ad5a59ba24c268c483ba5ec07399a0c9cbe9939abfcc4d7a50b7216c9763
---

> Part 1 of 4 of **Slash commands reference**.

---
title: "Slash commands reference"
type: navigation
docs_shell: true
---

# Slash commands reference

Every `/wiki-*` (plus governance commands) in `.claude/commands/`,
what it does, what it runs under the hood, and a realistic invocation
example. Use these inside **Claude Code** — Codex CLI picks the same
files up via `install-skills`.

Summary of **20 commands in 5 groups**:

| Group | Commands |
|---|---|
| **Wiki pipeline** (15) | `/wiki-init` `/wiki-sync` `/wiki-ingest` `/wiki-query` `/wiki-update` `/wiki-lint` `/wiki-candidates` `/wiki-synth` `/wiki-synthesize` `/wiki-graph` `/wiki-reflect` `/wiki-build` `/wiki-serve` `/wiki-export-marp` `/wiki-all` |
| **Governance / maintainer** (3) | `/maintainer` `/release` `/triage-issue` |
| **AWOS delivery** (2) | `/fix-bug` `/implement-feature` |

---

## Decision tree: which tool runs when?

### CLI vs slash

| You want to… | Use |
|---|---|
| …run a check in CI, a cron job, or a shell script | **CLI** (`python3 -m llmwiki …`) |
| …chain commands with `&&` / pipe to `jq` | **CLI** |
| …have the model read output + take follow-up actions | **slash** (inside Claude Code / Codex) |
| …answer a free-form question ("what did I decide about X?") | **slash** (`/wiki-query`) |
| …do one-shot builds, serves, graph generation | either — slashes wrap the CLI |

**Rule of thumb:** if the output is for *you* to read + act on manually,
use the CLI. If the output should feed back into an LLM turn, use the
slash — the model sees the full stdout and can chain into the next step.

### Lint (wiki quality)

Structural and content quality for the wiki is **`llmwiki lint`** / **`/wiki-lint`** — there is no separate `eval` subcommand.

| Command | Checks | Severity model | When to run |
|---|---|---|---|
| [`llmwiki lint`](../reference/cli.md#lint--run-13-wiki-quality-rules) / `/wiki-lint` | Frontmatter completeness, `[[wikilink]]` integrity, orphans, duplicate titles, stale pages, cache-tier consistency, tag-topic convention, stale references, and the rest of the registered rules | Rules with `error` / `warning` / `info` severities; `--fail-on-errors` exits non-zero only on errors | After every `/wiki-sync` or `/wiki-build`, and in CI |

Reach for lint when a page or the corpus looks wrong: orphans, broken `[[wikilinks]]`, missing frontmatter, stale summaries. Use `--fail-on-errors` (or the automation lint-fail policy) when a non-zero exit should block a pipeline.

---
