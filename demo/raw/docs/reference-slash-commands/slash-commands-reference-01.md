---
title: "Slash commands reference (part 1/4)"
slug: slash-commands-reference-01
project: reference-slash-commands
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/reference/slash-commands.md"
content_sha256: 27e61bf4e1fec0567f035bd800d927b554d63ef2038d5014d6a732e649596f37
---

> Part 1 of 4 of **Slash commands reference**.

---
title: "Slash commands reference"
type: navigation
docs_shell: true
---

# Slash commands reference

Every `/wiki-*` command `llmwiki install-agent-kit` ships — what it does,
what it runs under the hood, and a realistic invocation example. Use these
inside **Claude Code**. The command files live in the installable package and
land in an agent directory via `llmwiki install-agent-kit --dest PATH`.

Maintainer and AWOS delivery commands (`/release`, `/fix-bug`, `/implement-feature`) are not part of the vault pipeline and are not installed by the agent kit — they are described in [`../maintainers/README.md`](../maintainers/README.md).

All **12 commands in the vault pipeline**, in the order you meet them:

| Command | What it does |
|---|---|
| [`/wiki-init`](#wiki-init) | Scaffold an empty vault (`raw/`, `wiki/`, `site/`) |
| [`/wiki-sync`](#wiki-sync) | Convert new agent sessions into `raw/` |
| [`/wiki-ingest`](#wiki-ingest-path) | Ingest one file or folder into `raw/` |
| [`/wiki-synth`](#wiki-synth) | Synthesize pending raw into `wiki/sources/`, then harvest candidates |
| [`/wiki-candidates`](#wiki-candidates) | Triage pending candidate stubs |
| [`/wiki-query`](#wiki-query-question) | Answer a free-form question from the wiki |
| [`/wiki-update`](#wiki-update-page) | Edit one wiki page in place |
| [`/wiki-lint`](#wiki-lint) | Check wiki quality — orphans, broken links, stale pages |
| [`/wiki-graph`](#wiki-graph) | Build the knowledge graph from `[[wikilinks]]` |
| [`/wiki-reflect`](#wiki-reflect) | Higher-order reflection pass over the whole wiki |
| [`/wiki-build`](#wiki-build) | Regenerate the static HTML site |
| [`/wiki-all`](#wiki-all) | Run the whole pipeline end-to-end |

---

## Decision tree: which tool runs when?

### CLI vs slash

| You want to… | Use |
|---|---|
| …run a check in CI, a cron job, or a shell script | **CLI** (`python3 -m llmwiki …`) |
| …chain commands with `&&` / pipe to `jq` | **CLI** |
| …have the model read output + take follow-up actions | **slash** (inside Claude Code / Codex) |
| …answer a free-form question ("what did I decide about X?") | **slash** (`/wiki-query`) |
| …do one-shot builds, graph generation | either — slashes wrap the CLI |

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
