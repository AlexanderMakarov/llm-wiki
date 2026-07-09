---
title: "CLI reference"
type: navigation
docs_shell: true
---

# CLI reference

**Every** `python3 -m llmwiki <subcommand>` — with every flag, realistic
examples, and expected output. If a command isn't listed here it isn't
shipping. This page is generated against the live argparse tree, so
adding a flag without documenting it will fail the guardrail test.

Global flags: `-h` / `--help` on every command, `--version` at the root.

---

## Top-level

```bash
python3 -m llmwiki --version    # → llmwiki <version>
python3 -m llmwiki --help       # list every subcommand
python3 -m llmwiki              # same as --help
```

The shorter alias `llmwiki` works too once the package is installed
(`pip install llm-notebook` or via Homebrew — see
[`deploy/pypi-publishing.md`](../deploy/pypi-publishing.md) /
[`deploy/homebrew-setup.md`](../deploy/homebrew-setup.md)).

---

## `init` — scaffold `raw/` / `wiki/` / `site/`

Creates the three data directories + seeds nine navigation files inside
`wiki/`.

```bash
python3 -m llmwiki init
```

**Flags:** none.

**Expected output:**

```
  raw/sessions/
  wiki/sources/
  wiki/entities/
  wiki/concepts/
  wiki/syntheses/
  site/
  seeded wiki/dashboard.md
  seeded wiki/index.md
  ...
```

**Idempotent.** Safe to re-run — it never overwrites files that exist.

---

## `sync` — convert `.jsonl` sessions to markdown

The workhorse. Walks every configured adapter, converts new sessions
into `raw/sessions/`, then (by default) auto-builds and auto-lints.

```bash
python3 -m llmwiki sync
python3 -m llmwiki sync --since 2026-04-01 --project llm-wiki
python3 -m llmwiki sync --adapter claude_code codex_cli
python3 -m llmwiki sync --no-auto-build --no-auto-lint
python3 -m llmwiki sync --vault "~/Documents/Obsidian Vault"
python3 -m llmwiki sync --vault ~/my-vault --allow-overwrite
python3 -m llmwiki sync --force
```

### Flags

| Flag | What |
|---|---|
| `--adapter NAME [NAME ...]` | Limit to specific adapters. Default: every adapter with a session store on disk. |
| `--since YYYY-MM-DD` | Only sessions on/after this date (e.g. `--since 2026-04-01`). |
| `--project SUBSTRING` | Filter by project-slug substring. |
| `--include-current` | Include sessions < 60 min old (default skips live ones). |
| `--force` | Ignore the mtime state file, reconvert everything. |
| `--auto-build` / `--no-auto-build` | Rebuild `site/` after sync (default: on). |
| `--auto-lint` / `--no-auto-lint` | Run `lint` after sync (default: on). |
| `--vault PATH` | Vault-overlay mode — write new pages inside the given Obsidian / Logseq vault instead of `wiki/`. See [`guides/existing-vault.md`](../guides/existing-vault.md). |
| `--allow-overwrite` | With `--vault`: allow clobbering existing vault pages (default: refuse, append under `## Connections` instead). |
| `--status` | Show last-sync time + per-adapter counters + quarantine (does not run a sync). |
| `--recent N` | With `--status`: also show last N sync/synthesize log entries. |

> **Note:** There is no `sync --dry-run`. Use `sync --status` for observability
> or `add --dry-run` for document-intake previews. State lives in
> `llmwiki-state.json` (configured once at CLI entry via `--vault` /
> `vault.default_path`).

### Expected output (typical)

```
==> claude_code: 3 new sessions since last sync
✓ wrote 3 pages under raw/sessions/
✓ ingested into wiki/sources/ (2 new entities, 1 new concept)
✓ auto-build: site/ rebuilt (690 HTML files)
✓ auto-lint: 28 issues: 0 errors, 22 warnings, 6 info
```

### Common recipes

- Nightly cron-style sync of one project only:
  `llmwiki sync --project my-project --no-auto-lint --since $(date -v-1d +%Y-%m-%d)`
- Vault-overlay round-trip: `llmwiki sync --vault "~/Documents/Obsidian Vault"`

---

## `add` — add a document to the wiki (#16)

Converts a URL, file, or folder into a raw Markdown document under `raw/docs/`, then (by default) batch-synthesizes and rebuilds the site once for the whole run. Sources may be freely mixed and repeated.

```bash
python3 -m llmwiki add https://example.com/some-article
python3 -m llmwiki add ./notes.pdf ./research-folder/
python3 -m llmwiki add https://example.com/post --title "Custom Title" --tag research
python3 -m llmwiki add ./doc.md --project my-project --note "Imported from Slack"
python3 -m llmwiki add https://example.com/post --dry-run
```

### Flags

| Flag | What |
|---|---|
| `--title TEXT` | Override title derivation (single source only). |
| `--project NAME` | Group under `raw/docs/<NAME>/` instead of the doc's own slug. |
| `--tag TAG` | Extra frontmatter tag (repeatable). |
| `--note TEXT` | Blockquote note prepended to the document body. |
| `--no-synthesize` | Skip the post-add synthesis pass. |
| `--no-build` | Skip the post-add site rebuild. |
| `--render` | Force the headless-browser layer for URLs (needs playwright). |
| `--no-render` | Never use the headless-browser layer. |
| `--dry-run` | Convert and report, write nothing, run nothing. |
| `--force-new` | Always land a new snapshot even when the converted body matches an existing doc (#22). |
| `--vault PATH` | Write under the given vault's `raw/docs/` instead of the repo. |

URL sources go through a layered pipeline (markdown negotiation → extraction → render escalation) before landing as Markdown.

---

## `build` — compile the static HTML site

Turns `wiki/` markdown into `site/` HTML.

```bash
python3 -m llmwiki build
python3 -m llmwiki build --out ~/public_html
python3 -m llmwiki build --search-mode tree
python3 -m llmwiki build --synthesize --claude /usr/local/bin/claude
python3 -m llmwiki build --vault ~/my-vault --out ~/site
```

### Flags

| Flag | What |
|---|---|
| `--out PATH` | Output directory. Default: `./site/`. |
| `--synthesize` | Call the `claude` CLI for overview synthesis (experimental). |
| `--claude PATH` | Path to the `claude` binary. Default: `/usr/local/bin/claude`. |
| `--search-mode {auto,tree,flat}` | Search routing mode (#53). `auto` picks tree vs flat from heading depth; `tree` / `flat` force the mode. Default: `auto`. |
| `--vault PATH` | Vault-overlay mode — build from an existing Obsidian / Logseq vault. Output still lands at `--out`. |

### Expected output (final lines)

```
  wrote search-index.json (7 KB meta) + 30 chunks (904 KB total) · tree mode · 64% deep pages
  wrote 7 AI-consumable exports: ai-readme.md, graph.jsonld, llms-full.txt, llms.txt, robots.txt, rss.xml, sitemap.xml
  wrote site/graph.html (interactive graph viewer)
  wrote site/prototypes/index.html (6 prototype states)
  wrote site/docs/ (94 editorial pages: hub + tutorials + style guide)
==> build complete: 703 HTML files, 61 MB
```

---

## `serve` — start a local HTTP server

```bash
python3 -m llmwiki serve
python3 -m llmwiki serve --port 9000
python3 -m llmwiki serve --dir ~/public_html
python3 -m llmwiki serve --open
```

### Flags

| Flag | What |
|---|---|
| `--dir PATH` | Directory to serve. Default: `./site/`. |
| `--port N` | Port. Default: `8765`. |
| `--host ADDR` | Bind address. Default: `127.0.0.1`. Use `0.0.0.0` to share on LAN. |
| `--open` | Open the browser at the root URL after starting. |

**Stdlib only** — it's `http.server` underneath. Safe for local use;
don't expose to the public internet.

---

## `adapters` — list every adapter + its status

```bash
python3 -m llmwiki adapters
```

**Flags:** none.

**Expected output:**

```
Registered adapters:
  name              default   configured    description
  ----------------  --------  ------------  ----------------------------------------
  chatgpt           no        -             ChatGPT — parses conversations.json …
  claude_code       yes       ✓            Claude Code — reads ~/.claude/projects/
  codex_cli         no        ✓            Codex CLI — reads ~/.codex/sessions/
  copilot           no        -             GitHub Copilot — reads VS Code …
  cursor            no        -             Cursor — reads VS Code workspaceStorage
  gemini_cli        no        -             Gemini CLI — reads ~/.gemini/
  jira              no        -             Jira — reads via REST API
  meeting           no        -             Meeting transcripts (VTT/SRT)
  obsidian          no        -             Obsidian — reads a vault
  opencode          no        -             OpenCode / OpenClaw sessions
  web_clipper       no        -             Obsidian Web Clipper intake
```

Columns: **default** (runs when you don't pass `--adapter`), **configured**
(adapter sees a valid session store on this machine).

---

## `graph` — build the knowledge graph

```bash
python3 -m llmwiki graph                              # builtin wikilink graph
python3 -m llmwiki graph --engine graphify             # AI-powered graph (requires graphifyy)
python3 -m llmwiki graph --format json
python3 -m llmwiki graph --format html
```

### Flags

| Flag | What |
|---|---|
| `--format {json,html,both}` | Output format(s). Default: `both`. |
| `--engine {builtin,graphify}` | Graph engine. `builtin` = stdlib wikilink graph. `graphify` = AI-powered with community detection, confidence-scored edges, god nodes. Requires `pip install graphifyy`. Default: `builtin`. |

**Builtin engine:** Emits `graph/graph.json` (nodes + edges) and/or `graph/graph.html`
(vis-network interactive viewer). The interactive version is also
auto-copied into `site/graph.html` on every `build`.

**Graphify engine:** Runs the [Graphify](https://github.com/safishamsi/graphify) pipeline:
tree-sitter AST extraction for code, semantic analysis for docs, Leiden community
detection, god-node analysis. Outputs to `graphify-out/` (graph.json, graph.html,
GRAPH_REPORT.md) and copies to `graph/` for build compatibility. Install:
`pip install llm-notebook[graph]` or `pip install graphifyy`.

---

## `export` — AI-consumable site exports

Single positional argument picks the format.

```bash
python3 -m llmwiki export llms-txt
python3 -m llmwiki export llms-full-txt
python3 -m llmwiki export jsonld
python3 -m llmwiki export sitemap
python3 -m llmwiki export rss
python3 -m llmwiki export robots
python3 -m llmwiki export ai-readme
python3 -m llmwiki export all --out ~/custom-site
```

### Positional

| Value | Writes |
|---|---|
| `llms-txt` | `site/llms.txt` — llmstxt.org spec |
| `llms-full-txt` | `site/llms-full.txt` — flattened plain-text corpus (≤ 5 MB) |
| `jsonld` | `site/graph.jsonld` — schema.org entity graph |
| `sitemap` | `site/sitemap.xml` |
| `rss` | `site/rss.xml` |
| `robots` | `site/robots.txt` |
| `ai-readme` | `site/ai-readme.md` |
| `all` | all of the above |

### Flags

| Flag | What |
|---|---|
| `--out PATH` | Output directory. Default: `./site/`. |

---

## `lint` — run 14 wiki-quality rules

```bash
python3 -m llmwiki lint
python3 -m llmwiki lint --json
python3 -m llmwiki lint --fail-on-errors
python3 -m llmwiki lint --rules link_integrity,orphan_detection
python3 -m llmwiki lint --include-llm
python3 -m llmwiki lint --wiki-dir ~/another-wiki
```

### Flags

| Flag | What |
|---|---|
| `--wiki-dir PATH` | Wiki dir. Default: `./wiki`. |
| `--rules NAMES` | Comma-separated rule names. Default: all applicable. |
| `--include-llm` | Also run the three LLM-powered rules (requires a callback wired in). |
| `--json` | JSON output. |
| `--fail-on-errors` | Exit 1 if any error-severity issues. |

### Rules

8 structural (`frontmatter_completeness`, `frontmatter_validity`,
`link_integrity`, `orphan_detection`, `content_freshness`,
`entity_consistency`, `duplicate_detection`, `index_sync`) + 3 LLM-powered
(`contradiction_detection`, `claim_verification`, `summary_accuracy`) +
2 v1.1+ (`stale_candidates`, `cache_tier_consistency`).

### Expected output

```
  scanned 31 pages
  28 issues: 0 errors, 22 warnings, 6 info

## link_integrity (22)
  [warning] entities/GPT5.md: broken wikilink [[MultimodalModels]]
  ...
```

---

## `candidates` — approval workflow

Positional `action` picks `list` / `promote` / `merge` / `discard`.

```bash
python3 -m llmwiki candidates list
python3 -m llmwiki candidates list --stale --stale-days 60
python3 -m llmwiki candidates list --json
python3 -m llmwiki candidates promote --slug NewEntity
python3 -m llmwiki candidates promote --slug NewEntity --kind concepts
python3 -m llmwiki candidates merge --slug DuplicateFoo --into Foo
python3 -m llmwiki candidates discard --slug BogusEntity --reason "LLM hallucinated"
```

### Flags

| Flag | What |
|---|---|
| `--slug NAME` | Candidate slug. **Required** for `promote` / `merge` / `discard`. |
| `--into NAME` | For `merge`: target slug. |
| `--reason TEXT` | For `discard`: why (written to archive's `.reason.txt`). |
| `--kind {entities,concepts,sources,syntheses}` | Subtree. Auto-detected if omitted. |
| `--wiki-dir PATH` | Wiki dir. Default: `./wiki`. |
| `--stale` | With `list`: only stale candidates. |
| `--stale-days N` | Staleness threshold. Default: 30. |
| `--json` | JSON output for `list`. |

See [`guides/existing-vault.md`](../guides/existing-vault.md) for the
round-trip semantics when a candidate lives inside a vault.

---

## `synthesize` — LLM-backed source-page synthesis

```bash
python3 -m llmwiki synthesize --check            # probe the backend
python3 -m llmwiki synthesize --estimate         # cost preview, no API calls
python3 -m llmwiki synthesize --force            # re-synth everything
python3 -m llmwiki synthesize                    # real run
```

### Flags

| Flag | What |
|---|---|
| `--check` | Probe backend availability + exit (0 if reachable). |
| `--force` | Ignore state, re-synth every source. |
| `--estimate` | Print cached-vs-fresh token + dollar estimate (#50). |
| `--vault PATH` | Read/write under the vault root; configures the active `llmwiki-state.json`. |

Backend is picked from `synthesis.backend` in `config.json` /
`sessions_config.json` (`dummy` by default, `ollama` for local,
`claude` for synchronous `claude -p`). See
[`configuration.md`](../configuration.md#synthesis-backend).

> **Removed in v1.4.0:** `--list-pending` and `--complete` (agent-delegate
> pending prompts). Use `synthesis.backend: claude` instead.

### Auto-tagging (#351)

Every `synthesize` call now produces **topical** tags alongside the
deterministic baseline.  The synthesizer emits a
`<!-- suggested-tags: prompt-caching, rag, github-actions -->` block
as the first line of its response; the pipeline parses it, strips it
from the body, and merges the tags into frontmatter with:

- **Baseline preserved** — adapter, project slug, model family stay.
- **Maintainer wins** — on `--force`, whatever you added via
  `llmwiki tag add` is kept at the front of the list.
- **Stop-word filter** — the LLM can't re-add boilerplate tags
  (`session`, `summary`, `claude-code`, etc.).
- **Cap 5** — max 5 AI tags per page to prevent drift.
- **Near-dup rejection** — `prompt-cache` is blocked when
  `prompt-caching` is already on the page (threshold 0.80 + prefix
  check).

No extra API round-trip — rides the existing synthesis call, so cost
estimates from `--estimate` are unchanged.  If the backend returns no
suggested-tags block (dummy backend, malformed output), the page still
ships with baseline tags.

---

## `queue` — inspect and run unified queue

Manage the unified vault queue in `llmwiki-state.json`.

```bash
python3 -m llmwiki queue
python3 -m llmwiki queue enqueue --task-type add_doc --source https://example.com
python3 -m llmwiki queue run --vault /path/to/vault --limit 20
```

### Positional

| Value | What |
|---|---|
| `status` | Print queue counts, task-type breakdown, state path, and oldest pending timestamp. |
| `enqueue` | Add one task (`add_doc`, `session_sync`, `synthesize`, `build`). |
| `run` | Execute pending tasks serially (up to `--limit`). |

### Flags

| Flag | What |
|---|---|
| `--task-type {add_doc,session_sync,synthesize,build}` | Task kind for `enqueue`. |
| `--source TEXT` | Source payload for `add_doc` enqueue. |
| `--limit N` | Max tasks to process in one `run` call. Default: `20`. |
| `--vault PATH` | Vault root used for task execution and state lookup. |
| `--state-file PATH` | Override direct state file path. |

---

## `migrate-state` — one-time legacy state migration (v1.4.0)

Migrates legacy dotfiles (`.llmwiki-state.json`, `.llmwiki-synth-state.json`, `.llmwiki-queue.json`, `.llmwiki-quarantine.json`, `.llmwiki-pending-prompts/`) into the unified `llmwiki-state.json`.

Implementation lives at `scripts/migrate_state_v1_4_0.py`; the CLI is a thin wrapper.

```bash
python3 scripts/migrate_state_v1_4_0.py
python3 scripts/migrate_state_v1_4_0.py --state-file /path/to/vault/llmwiki-state.json
python3 -m llmwiki migrate-state
python3 -m llmwiki migrate-state --state-file /path/to/vault/llmwiki-state.json
```

### Flags

| Flag | What |
|---|---|
| `--state-file PATH` | Explicit target state file (defaults to configured vault path). |

The command is idempotent and prints cleanup suggestions for migrated legacy files.

---

## `consolidate-topics` — dedupe + describe topics (#54)

One-time LLM pass over the topic list (not the sessions) that merges
duplicate topic spellings (`LLM-Wiki` / `LLMWiki` / `llm wiki`) into
one canonical node and writes short descriptions, caching the result
in `.llmwiki-topics.json` for `llmwiki graph` / `llmwiki build`.

```bash
python3 -m llmwiki consolidate-topics                # emit the LLM prompt
python3 -m llmwiki consolidate-topics --complete reply.json
python3 -m llmwiki consolidate-topics --complete -    # read the reply from stdin
```

### Flags

| Flag | What |
|---|---|
| `--complete PATH` | Ingest the LLM's JSON reply (file path, or `-` for stdin) and write the topic cache. Without this flag, the prompt is printed instead. |
| `--vault PATH` | Read/write the topic cache inside the given vault instead of the repo. |

Re-run after large ingest batches so near-duplicate topic spellings
don't fragment the knowledge graph.

---

## `version` — print the installed version

```bash
python3 -m llmwiki version
python3 -m llmwiki --version
```

Both print `llmwiki <version>`.

---

## `query` — search the knowledge graph

```bash
python3 -m llmwiki query "what projects is Pratiyush working on"
python3 -m llmwiki query "Flutter mobile" --depth 2 --budget 1000
```

### Flags

| Flag | What |
|---|---|
| `--depth N` | BFS traversal depth. Default: `3`. |
| `--budget N` | Max output tokens. Default: `2000`. |

Requires Graphify (`pip install llm-notebook[graph]`). Run `llmwiki graph` first
to build the graph.

---

## `all` — run the full pipeline

Convenience entry point that runs `build` → `graph` → `export all` → `lint`
in order. This is the one command to run after `sync` to produce a
CI-ready site.

```bash
python3 -m llmwiki all
python3 -m llmwiki all --graph-engine builtin   # skip optional graphify
python3 -m llmwiki all --skip-graph --strict    # fail CI on any lint issue
```

### Flags

| Flag | What |
|---|---|
| `--out DIR` | Output dir for build + export. Default: `site/`. |
| `--search-mode {auto,tree,flat}` | Forwarded to `build`. Default: `auto`. |
| `--graph-engine {builtin,graphify}` | Forwarded to `graph`. Default: `graphify`. |
| `--skip-graph` | Skip the graph step entirely (useful when graphify is not installed). |
| `--fail-fast` | Stop at the first non-zero step. Default: continue, report the worst exit code. |
| `--strict` | Exit `2` if `lint` reports any errors/warnings. |

Exit codes:

- `0` — every step succeeded.
- non-zero — forwarded from the first (or worst) failing step.
- `2` — `--strict` and lint reported issues.

---

## Exit codes (conventions)

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Operation failed (user-visible error) |
| `2` | Usage error (bad flags, missing file, etc.) |

Subcommands document their own non-zero exit conditions where relevant
(`lint --fail-on-errors`).

---

## Related

- **[Slash commands](slash-commands.md)** — the `/wiki-*` surface used from Claude Code.
- **[UI reference](ui.md)** — every screen + nav surface on the compiled site.
- **[Configuration](../configuration.md)** · **[Full configuration reference](../configuration-reference.md)**.
