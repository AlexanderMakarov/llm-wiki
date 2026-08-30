---
title: "Slash commands reference"
type: navigation
docs_shell: true
---

# Slash commands reference

Every `/wiki-*` (plus governance commands),
what it does, what it runs under the hood, and a realistic invocation
example. Use these inside **Claude Code**. User-facing `/wiki-*` files ship in the installable package and land in an agent directory via `llmwiki install-agent-kit --dest PATH`; governance commands stay in this repository's `.claude/commands/`.

Summary of **19 commands in 5 groups**:

| Group | Commands |
|---|---|
| **Wiki pipeline** (14) | `/wiki-init` `/wiki-sync` `/wiki-ingest` `/wiki-query` `/wiki-update` `/wiki-lint` `/wiki-candidates` `/wiki-synth` `/wiki-synthesize` `/wiki-graph` `/wiki-reflect` `/wiki-build` `/wiki-export-marp` `/wiki-all` |
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

## Wiki pipeline

### `/wiki-init`

**What:** scaffolds an empty llmwiki — creates `raw/`, `wiki/`, `site/`
and seeds `wiki/index.md`, `wiki/log.md`, `wiki/overview.md`, plus the
nine navigation files (`CRITICAL_FACTS.md`, `MEMORY.md`, `SOUL.md`,
`hints.md`, `hot.md`, `dashboard.md`).

**Wraps:** `python3 -m llmwiki init`.

**When to use:** first time in a fresh repo, or after deleting `wiki/`
to start over.

**Example:**

```
/wiki-init
```

Claude Code will respond by running init and surfacing which files
were seeded.

---

### `/wiki-sync`

**What:** convert new Claude Code (+ Codex + Cursor + etc.) `.jsonl`
sessions into markdown under `raw/sessions/`, then ingest into `wiki/`.

**Wraps:** `python3 -m llmwiki sync`.

**Arguments Claude may pass through:** `--dry-run`, `--since`,
`--project`, `--force`, `--vault`. Say any of them in natural language
— "sync but only sessions from this week" becomes
`--since $(date -v-7d +%Y-%m-%d)`. Durable lookback in config (`filters.since` / `adapters.*.since`) applies on bare `/wiki-sync` when `--since` is omitted — see [configuration-reference.md](../configuration-reference.md#sync-lookback).

**When to use:** at the end of each coding block. Also the only command
that triggers auto-ingest of new pages into `wiki/`.

**Example:**

```
/wiki-sync
/wiki-sync only my llm-wiki project
/wiki-sync but don't auto-build afterwards
/wiki-sync into my Obsidian vault at ~/Documents/Obsidian Vault
```

**Expected output (narrated):**

```
==> claude_code: 3 new sessions since last sync
✓ wrote 3 pages under raw/sessions/
✓ ingested into wiki/sources/
✓ auto-build: site/ rebuilt (690 HTML files)
```

---

### `/wiki-ingest <path>`

**What:** ingest **one** source document or folder into `wiki/`, or enrich / discuss pending candidates during review. Reads the file, creates / updates the matching `wiki/sources/<slug>.md`, and may propose entity/concept candidates. **Trusted hubs still require review** (`/wiki-candidates` or `llmwiki candidates promote|merge|discard`) — ingest is not an auto-promote escape hatch.

**Wraps:** the Ingest Workflow in `CLAUDE.md` (no single CLI — it's a slash-command-driven workflow that the model orchestrates).

**When to use:** you dropped a source file manually (a PDF, a Jira ticket export, a meeting transcript), or Home / Analytics show a **To review** backlog and you want agent-led discussion over candidates. For bulk stub generation from already-synthesized sources, prefer `llmwiki synth --candidates-only`.

**Examples:**

```
/wiki-ingest raw/sources/2026-04-17-incident.md
/wiki-ingest raw/jira/
/wiki-ingest ~/Downloads/meeting-transcript.vtt
```

---

### `/wiki-query <question>`

**What:** answer a question from the wiki. Reads `wiki/index.md` +
`wiki/overview.md` + any `cache_tier: L1` pages, then walks relevant
source / entity / concept pages and synthesises an answer with inline
`[[wikilinks]]` back to the originals.

**Wraps:** the Query Workflow in `CLAUDE.md`.

**When to use:** "have I solved this before?" / "when did I add X?" /
"which sessions touched Y?".

**Examples:**

```
/wiki-query when did I add the lint rules?
/wiki-query which agent did I use for refactoring the cache-tier module?
/wiki-query summarize every session about Obsidian integration
```

**Save prompt:** if the answer runs 3+ paragraphs, Claude will offer to
save it under `wiki/syntheses/<slug>.md`.

---

### `/wiki-update <page>`

**What:** surgically edit one wiki page without re-ingesting. Useful
for fixing broken wikilinks, updating stale frontmatter, adding a
missing `## Connections` line.

**When to use:** lint flagged something, you know the fix, you don't
want to re-run sync.

**Example:**

```
/wiki-update wiki/entities/RAG.md add a Connections section linking to Karpathy and llm-wiki
```

---

### `/wiki-lint`

**What:** run every registered lint rule (16 at last count — all structural / deterministic). The live number is printed by `llmwiki lint --help`.

**Wraps:** `python3 -m llmwiki lint`.

**Rules, in order:**

1. `frontmatter_completeness`
2. `frontmatter_validity`
3. `link_integrity`
4. `orphan_detection`
5. `content_freshness`
6. `duplicate_detection`
7. `index_sync`
8. `contradiction_detection` — non-filler `## Contradictions` sections
9. `claim_verification` — entity/concept claims without sources
10. `summary_accuracy` — empty `summary:` frontmatter
11. `stale_candidates`
12. `tags_topics_convention` *(G-16 · #302)*
13. `stale_reference_detection` *(G-17 · #303)*
14. `frontmatter_count_consistency`
15. `tools_consistency`
16. `stub_source_pages`

**Example:**

```
/wiki-lint
/wiki-lint just the link_integrity rule
```

---

### `/wiki-synth`

**What:** synthesize pending raw sessions/docs into `wiki/sources/`, then harvest entity/concept candidates into `wiki/candidates/` (default). Use `--sources-only` for the legacy sources-only path. Sources are two LLM jobs per run (known-names prepare + one ask per queued file); harvest is offline. Ctrl+C harvests from written pages (or prints `synth --candidates-only` after `--sources-only`) and exits 130. Do not run `consolidate-topics`.

**Wraps:** `python3 -m llmwiki synth`.

**Example:**

```
/wiki-synth
/wiki-synth with a cost estimate
/wiki-synth force a re-run of every source
/wiki-synth sources only
```

### `/wiki-synthesize`

**Deprecated** alias for `/wiki-synth`. Prefer `/wiki-synth`. Still wraps `python3 -m llmwiki synthesize` (sources-only + deprecation warning).

---

### `/wiki-candidates`

**What:** triage pending candidates — `promote`, `flip-promote`, `merge`, `discard`, or batch `apply --actions`.

**Wraps:** `python3 -m llmwiki candidates list` + follow-ups (`apply --actions` for batches). Same intents `site/candidates.html` lists, whose copyable batch feeds the same command.

**When to use:** Home **Candidates** / Analytics **Candidates to review** is non-zero, `/wiki-lint` reported `stale_candidates`, or you just ran `llmwiki synth` / `synth --candidates-only`.

Promote fills an empty `## Key Facts` offline from source `fact:` bullets (and harvest stubs); Dummy / no backend is fine (#147). Prefer the CLI action for the common case. Opt-in `llmwiki candidates rewrite-key-facts --slug <Name>` (or `--all`) still needs an LLM for trusted pages with regex-era Key Facts or pasted harvest-stub `## Candidate merge` blocks. Prefer `flip-promote` over hand-moving stubs between `candidates/entities` and `candidates/concepts`.

**Example:**

```
/wiki-candidates
```

Claude will walk the queue one at a time and offer actions per candidate.

---

### `/wiki-graph`

**What:** build the knowledge graph. Nodes = wiki pages, edges =
`[[wikilinks]]`. Emits `graph/graph.json` + `graph/graph.html`.

**Wraps:** `python3 -m llmwiki graph`.

**Example:**

```
/wiki-graph
```

Then open `site/graph.html` (auto-copied from `graph/graph.html` during
build) in a browser.

---

### `/wiki-reflect`

**What:** higher-order self-reflection pass over the whole wiki. Looks
for gaps, patterns, duplicated-topic clusters, areas where a synthesis
page would help.

**No CLI wrapper** — it's a model-orchestrated workflow that reads the
index + overview + sample of pages and outputs suggestions.

**Example:**

```
/wiki-reflect
```

Use sparingly; it's the most token-heavy command.

---

### `/wiki-build`

**What:** regenerate the static HTML site.

**Wraps:** `python3 -m llmwiki build`.

**When to use:** after manual edits to `wiki/`, or when you want to see
a fresh site without running the full sync pipeline.

**Example:**

```
/wiki-build
/wiki-build to ~/public_html
/wiki-build in tree search mode
```

---

### `/wiki-export-marp`

**What:** generate a Marp slide deck from wiki pages matching a topic.

**Wraps:** `python3 -m llmwiki export-marp --topic …`.

**Example:**

```
/wiki-export-marp topic "cache tiers"
/wiki-export-marp topic Karpathy save to ~/slides/karpathy.marp.md
```

---

### `/wiki-all`

**What:** run the full pipeline end-to-end — sync → synth → build → graph → lint. Every stage runs unless you opt out of it. AI-consumable exports (`llms.txt`, `sitemap.xml`, etc.) are written by `build`, not a separate step.

**Wraps:** `python3 -m llmwiki all`.

**When to use:** after `/wiki-sync`, when you want a CI-ready site in one shot
instead of chaining `/wiki-build` + `/wiki-graph` + `/wiki-lint` yourself.

**Example:**

```
/wiki-all
/wiki-all --no-synth
/wiki-all --graph-engine builtin
/wiki-all --skip-graph --strict
```

Pass `--strict` to turn any lint warning into a non-zero exit, which is exactly what CI wants. Pass `--skip-graph` or `--graph-engine builtin` when the optional Graphify backend is not installed. Pass `--no-sync` or `--no-synth` to leave session conversion or synthesis out of the run — `--no-synth` is the one that keeps the run away from your AI provider.

---

## Governance / maintainer

### `/maintainer`

Meta-skill that loads all llmwiki governance docs (`CONTRIBUTING.md`,
`CODE_OF_CONDUCT.md`, `docs/maintainers/*`) and exposes the three
maintainer slash commands below.

Use before doing anything governance-related.

### `/release`

Walk through the llmwiki release process step by step — tag, changelog
cut, GitHub Release note, PyPI publish (via OIDC), Homebrew tap bump,
Docker image push.

### `/triage-issue`

Apply labels + milestone + priority to a new GitHub issue using the
llmwiki triage rules.

**Example:**

```
/triage-issue 280
```

---

## AWOS delivery

Hired via `/awos-hire` (#114). Decisions and stages live under `context/product/` (especially `delivery-flow.md`). Prefer Cursor `/awos-flow` / Claude `/awos:flow` when changing those decisions.

### `/fix-bug`

Drive one bug (GitHub Issue) through diagnosis → scoped fix + regression test → verify → independent review (full write-up printed in chat) → PR. Subagent-heavy; keeps the owning AWOS spec honest when behavior changes.

**Example:**

```
/fix-bug 114
```

### `/implement-feature`

Drive one feature (spec / issue) through implement → test → independent review (full write-up printed in chat) → PR per `context/product/delivery-flow.md`.

**Example:**

```
/implement-feature <spec-or-issue>
```

---

## How the slash commands get installed

The repo ships `.claude/commands/*.md` — Claude Code picks them up
automatically when it opens the repo (no separate install step).

For **Codex CLI / Cursor / Gemini CLI / other agents**, copy the
`.claude/commands/wiki-*.md` files into the corresponding skill
directory for that agent (typically `.codex/skills/` or
`.agents/skills/`) — the file format is portable across agents.

---

## Extending

To add a new slash command:

1. Create `.claude/commands/wiki-<name>.md` with a one-line docstring
   on line 1 (that's the summary Claude Code surfaces).
2. Describe the workflow in prose. Reference existing CLI commands
   rather than embedding shell in the body.
3. Run `/wiki-lint` — the `docs/reference/` guardrail test (see
   `tests/test_docs_structure.py`) will pick up the new command.
4. Document it here; the CI guard requires every `.claude/commands/*.md`
   to have a matching entry.

---

## Related

- **[CLI reference](cli.md)** — the underlying `python3 -m llmwiki …` surface.
- **[UI reference](ui.md)** — every screen on the compiled site, with what's reachable from where.
- **[Tutorial 03 — Use with Claude Code](../tutorials/03-use-with-claude-code.md)** — the minimum daily loop built on these commands.
