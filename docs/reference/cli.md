---
title: "CLI reference"
type: navigation
docs_shell: true
---

# CLI reference

**Every** `python3 -m llmwiki <subcommand>` — with every flag, realistic examples, and expected output. If a command isn't listed here it isn't shipping. This page is generated against the live argparse tree, so adding a flag without documenting it will fail the guardrail test.

Global flags: `-h` / `--help` on every command, `--version` at the root.

---

## Top-level

```bash
python3 -m llmwiki --version    # → llmwiki <version>
python3 -m llmwiki --help       # list every subcommand
python3 -m llmwiki              # same as --help
```

The shorter alias `llmwiki` works too once the package is installed (`pip install llm-notebook` or via Homebrew — see [`deploy/pypi-publishing.md`](../deploy/pypi-publishing.md) / [`deploy/homebrew-setup.md`](../deploy/homebrew-setup.md)).

---

## `init` — scaffold `raw/` / `wiki/` / `site/`

Creates the three data directories + seeds nine navigation files inside `wiki/`.

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

The workhorse. Walks every configured adapter, converts new sessions into `raw/sessions/`, reconciles `wiki/index.md` against pages on disk, then (by default) auto-builds and auto-lints.

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

- Nightly cron-style sync of one project only: `llmwiki sync --project my-project --no-auto-lint --since $(date -v-1d +%Y-%m-%d)`
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

## `remove` — cascade-remove a raw doc and everything derived (#B2)

Selects raw docs under the resolved vault's `raw/docs/` by a project name or slug glob, then removes them **together with** every artifact derived from them — the `synth.files` state keys and the `wiki/sources/` pages (part-pages included) — so a naive delete can never leave orphan pages or dangling state behind. After deletion it prunes backlinks, rebuilds `wiki/index.md`, and appends a `remove` entry to `wiki/log.md`.

```bash
python3 -m llmwiki remove old-project --dry-run      # preview the full cascade
python3 -m llmwiki remove 'old-project*' --yes        # slug glob, no prompt
python3 -m llmwiki remove taxes --vault ~/my-vault --yes
```

### Positional

| Value | What |
|---|---|
| `SELECTOR` | Project name or slug glob (e.g. `old-project*`) matched against `raw/docs/`. |

### Flags

| Flag | What |
|---|---|
| `--dry-run` | Print the full cascade (every raw file, state key, and wiki page) and change nothing. |
| `--yes` | Skip the confirmation prompt. **Required** when stdin is not a TTY — cascade deletion is never silent. |
| `--vault PATH` | Cascade against the given vault instead of the repo's own directories. |

A selector that matches nothing is a clean no-op with a message. Without `--dry-run` and without `--yes`, the command prints the cascade and asks for confirmation on a TTY, or refuses (exit 2) when there is none.

---

## `build` — compile the static HTML site

Turns `wiki/` markdown into `site/` HTML. Also writes AI-consumable exports (`llms.txt`, `llms-full.txt`, `sitemap.xml`, `rss.xml`, `robots.txt`, `graph.jsonld`, `ai-readme.md`) into the output directory — there is no separate `export` subcommand.

```bash
python3 -m llmwiki build
python3 -m llmwiki build --out ~/public_html
python3 -m llmwiki build --search-mode tree
python3 -m llmwiki build --synthesize --claude /usr/local/bin/claude
python3 -m llmwiki build --vault ~/my-vault --out ~/site
python3 -m llmwiki build --vault demo --out ./site --local-root /home/user
```

### Flags

| Flag | What |
|---|---|
| `--out PATH` | Output directory. Default: `./site/`. |
| `--synthesize` | Call the `claude` CLI for overview synthesis (experimental). |
| `--claude PATH` | Path to the `claude` binary. Default: `/usr/local/bin/claude`. |
| `--search-mode {auto,tree,flat}` | Search routing mode (#53). `auto` picks tree vs flat from heading depth; `tree` / `flat` force the mode. Default: `auto`. |
| `--vault PATH` | Vault-overlay mode — build from an existing Obsidian / Logseq vault. Output still lands at `--out`. |
| `--local-root PATH` | Value shown in place of a session's stored home directory (#109). Default: this machine's home directory, so local paths stay usable. Pass a fixed string when publishing so the same vault renders identically anywhere. Substitution applies to the `cwd` field only. |
| `--seed-project-stubs` | Create a `wiki/projects/<slug>.md` stub for any project without one (#414). Off by default — `build` is read-only on `wiki/`. |

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

## `usage` — MCP tool-usage telemetry vs synthesis cost (#26)

```bash
python3 -m llmwiki usage              # human-readable report
python3 -m llmwiki usage --json       # machine-readable totals
python3 -m llmwiki usage --compact    # roll past months into rollup.json first
```

Folds the local MCP telemetry logs into totals and prints them next to the synthesis cost persisted in state — so the "is this wiki earning its synthesis spend?" question is answerable at a glance.

The MCP server logs one JSON record per tool call to a **per-process** file under `<vault>/usage/` (`mcp-<pid>-<start>.jsonl`), merged at read time. Several server processes run at once (one per editor session), so per-process files mean zero write contention and no lock on the hot path; telemetry never touches `llmwiki-state.json`. Each record carries `tool`, `query`, `hits` (`0` = a knowledge gap or noise; `null` = the tool can't report a count), `resp_bytes`, `duration_ms`, `caller_project`, `caller_source`, `server_pid`, `server_started`. Writes are best-effort — a telemetry failure never breaks a tool call. Opt out with `LLMWIKI_MCP_TELEMETRY=0`.

**Caller attribution.** `caller_project` is resolved per call and `caller_source` says where it came from:

| `caller_source` | Meaning |
|---|---|
| `project-dir-env` | The workspace path a client auto-injects into the server's environment. **Claude Code** sets `CLAUDE_PROJECT_DIR` (≥ v2.1.139) into every stdio MCP server — zero config — and spawns one server per session, so it is a stable per-caller signal available at the first call. |
| `client-root` | The client's own workspace directory, obtained via an MCP `roots/list` request. Attributed to the first root when a client reports several. |
| `path` | A path argument carrying the caller's working directory encoded into one segment (`…/-home-dev-code-my-app/…`), used for clients that offer neither of the above. |
| `unattributed` | No caller-scoped signal — `caller_project` is `unknown`. |

They are tried in that order. All three project sources feed one shared `slugs.project_slug_from_abs_path`, so a project resolves to the same slug whether it arrived through telemetry or through session ingestion (and thus keys onto its own project page).

**Client coverage.** Claude Code attributes every call with no setup, via `CLAUDE_PROJECT_DIR`. **Cursor** currently provides no zero-config signal — it advertises the `roots` capability but returns `Method not found` on the actual `roots/list` call, and injects no workspace env var — so its calls fall to the path heuristic where a path argument is present, else `unknown`, until it ships a fix. The server's own `os.getcwd()` is never used: a client may launch the server anywhere (Claude Code's desktop app uses `$HOME`), so it is unrelated to the caller's project.

Unattributed calls are counted in the totals but never presented as a project: they print as `(unattributed)` here and are excluded from the site's "Heaviest project by MCP usage" card. Records written by an earlier version carry no `caller_source` and are read as unattributed regardless of the project name they hold, because that name is the server process's own working directory rather than the caller's. The same applies to a `usage/rollup.json` written before this change — the raw records behind it are already deleted, so its labels are retracted rather than recomputed.

**Daily series (#52).** `usage/daily.json` stores per-day MCP call totals (`mcp_calls`, `retrievals`, `writes`, `session_reads`, `doc_reads`, `other_reads`, `by_tool`, attribution counts) so Analytics activity heatmaps survive `--compact`. Compact folds retiring JSONL files into `folded_days` before delete; each `llmwiki build` refreshes the live overlay from non-folded files without double-counting. The CLI report itself is unchanged — the Analytics page is the primary surface. See [State persistence](state-persistence.md).

Scope is MCP calls only — `file://` static-site browsing stays untracked.

### Flags

| Flag | What |
|---|---|
| `--json` | Emit the aggregated totals (`consumption` + `cost`) as JSON. |
| `--compact` | Fold whole past months into the kept-forever `usage/rollup.json` and delete their raw logs before reporting. |
| `--vault PATH` | Read telemetry from this vault instead of the repo root. |
| `--state-file PATH` | State file to read the synthesis-cost estimate from. |

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

Columns: **default** (runs when you don't pass `--adapter`), **configured** (adapter sees a valid session store on this machine).

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

**Builtin engine:** Emits `graph/graph.json` (nodes + edges) and/or `graph/graph.html` (vis-network interactive viewer) plus sibling `graph-viewer.js` and `vis-network.min.js`. The interactive trio is also auto-copied into `site/` on every `build`, so the graph works offline from the built static site without a CDN fetch.

**Graphify engine:** Runs the [Graphify](https://github.com/safishamsi/graphify) pipeline: tree-sitter AST extraction for code, semantic analysis for docs, Leiden community detection, god-node analysis. Outputs to `graphify-out/` (graph.json, graph.html, GRAPH_REPORT.md) and copies to `graph/` for build compatibility. Install: `pip install llm-notebook[graph]` or `pip install graphifyy`.

---

## `lint` — run 17 wiki-quality rules

```bash
python3 -m llmwiki lint
python3 -m llmwiki lint --json
python3 -m llmwiki lint --fail-on-errors
python3 -m llmwiki lint --rules link_integrity,orphan_detection
python3 -m llmwiki lint --wiki-dir ~/another-wiki
```

### Flags

| Flag | What |
|---|---|
| `--wiki-dir PATH` | Wiki dir. Default: `./wiki`. |
| `--rules NAMES` | Comma-separated rule names. Default: all applicable. |
| `--json` | JSON output. |
| `--fail-on-errors` | Exit 1 if any error-severity issues. |

### Rules

17 structural rules (all deterministic — no LLM): `frontmatter_completeness`, `frontmatter_validity`, `link_integrity`, `orphan_detection`, `content_freshness`, `duplicate_detection`, `index_sync`, `contradiction_detection`, `claim_verification`, `summary_accuracy`, `stale_candidates`, `tags_topics_convention`, `stale_reference_detection`, `frontmatter_count_consistency`, `tools_consistency`, `stub_source_pages`, `provenance_integrity`.

`contradiction_detection`, `claim_verification`, and `summary_accuracy` used to hide behind `--include-llm` and advertise an LLM callback that was never wired. As of #72 they always run as structural checks: non-filler `## Contradictions` sections, entity/concept claims without sources, and empty `summary:` frontmatter. Filler bodies like `None identified.`, `None detected.`, and multi-sentence `None identified. …` elaborations are not findings (unless the section also contains an *unnegated* affirmative conflict cue such as `Contradicts earlier…`). Cues that appear only inside negation (`does not conflict with prior…`, `no claims that conflict…`) stay filler (#86).

`orphan_detection` counts inbound `[[wikilinks]]` and catalog markdown links (`[title](path.md)` that resolve to a wiki page), so pages listed only from `index.md` are not orphans. `link_integrity` resolves targets case- and punctuation-insensitively (`[[LLM-Wiki]]` → `llm-wiki.md`) but does not do substring matching.

`stub_source_pages` (#24) flags pages under `wiki/sources/` whose body is machine-generated filler — a pending sentinel (`<!-- llmwiki-pending: … -->`) or the dummy backend's `Auto-synthesized from session` body. Those sources still count as unsynthesized backlog; refill them with `llmwiki synth` on a real backend.

`provenance_integrity` (#122) emits an **error** for each broken downward hop on pages that already carry `sources:` and/or `source_file:` — missing source-summary pages or missing raw files. Pages without those fields are skipped. Repair is guided by `doctor` (#110); this rule only reports.

`stale_reference_detection` (#303 / #87) flags living pages (entities, concepts, …) whose dated claim about a target predates that target's `last_updated`. Pages under `wiki/sources/` and pages with frontmatter `type: source` are skipped — they are dated session records and cannot be "un-staled" without rewriting history.

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

Positional `action` picks `list` / `promote` / `flip-promote` / `merge` / `discard` / `apply` / `rewrite-key-facts`.

Successful `promote` / `flip-promote` / `merge` / `discard` / `apply` reconcile `wiki/index.md` (#101): dead `candidates/…` bullets are dropped, an empty `## Candidates` section is removed, and newly trusted pages are listed under Entities/Concepts. `/wiki-candidates` should call these same actions — do not run idle `sync`/`synth` just to refresh the catalog after review. Site UI: open `site/candidates.html` — it lists everything pending, takes a decision per row, and its **Apply** button prints the `candidates apply --vault … --actions -` command plus the JSON batch for the rows you decided (#97).

`promote` also writes an empty (or heading-only) `## Key Facts` (#103). It builds an evidence digest — every line where each source listed in frontmatter `sources:` / Connections names the subject, capped at 12 sources and 4 lines each — and hands it to the backend named by `synthesis.backend`, which returns 3–5 attributed bullets. Non-empty reviewer Key Facts are left alone.

Because those bullets become trusted-layer prose, promote refuses to write them without a model: with `synthesis.backend` unset or `dummy` it exits 2 with `KeyFactsBackendError` and leaves the candidate pending. Override the prompt per vault at `wiki/prompts/key_facts.md`.

`merge` folds a harvest stub into the target by unioning its `sources:` and Connections links and recording the name under `## Aliases`; a candidate containing reviewer prose still has that prose appended under `## Candidate merge — <date>`. Target may be a trusted page or another pending stub in the same kind.

`apply` runs a **batch** of the same intents in one process (the JSON shape `site/candidates.html` prints):

```bash
python3 -m llmwiki candidates apply --actions '[{"action":"promote","slug":"Foo","kind":"entities"},{"action":"promote","slug":"Prompt Caching","kind":"concepts"}]'
python3 -m llmwiki candidates apply --actions - <<'EOF'
[{"action":"discard","slug":"Bogus","kind":"entities","reason":"noise"}]
EOF
```

Already-trusted pages that still carry machine-assembled (regex) Key Facts, or pasted harvest-stub `## Candidate merge` blocks from the old merge path, are fixed with `rewrite-key-facts`:

```bash
python3 -m llmwiki candidates list
python3 -m llmwiki candidates list --stale --stale-days 60
python3 -m llmwiki candidates list --json
python3 -m llmwiki candidates promote --slug NewEntity
python3 -m llmwiki candidates promote --slug NewEntity --kind concepts
python3 -m llmwiki candidates flip-promote --slug Misfiled
python3 -m llmwiki candidates merge --slug DuplicateFoo --into Foo
python3 -m llmwiki candidates discard --slug BogusEntity --reason "LLM hallucinated"
python3 -m llmwiki candidates rewrite-key-facts --slug ExistingEntity
python3 -m llmwiki candidates rewrite-key-facts --all
```

### Flags

| Flag | What |
|---|---|
| `--slug NAME` | Page slug. **Required** for `promote` / `flip-promote` / `merge` / `discard`; or with `rewrite-key-facts`. |
| `--all` | For `rewrite-key-facts`: every entity/concept page. |
| `--into NAME` | For `merge`: target slug (trusted page or another pending stub in the same kind). |
| `--reason TEXT` | For `discard`: why (written to archive's `.reason.txt`). |
| `--kind {entities,concepts,sources,syntheses}` | Subtree. Auto-detected if omitted. |
| `--wiki-dir PATH` | Wiki dir. Default: `./wiki`. |
| `--stale` | With `list`: only stale candidates. |
| `--stale-days N` | Staleness threshold. Default: 30. |
| `--json` | JSON output for `list`. |
| `--actions JSON` | For `apply`: JSON array of `{action,slug,kind?,into?,reason?}`. Pass `-` to read the array from stdin. |

See [`guides/existing-vault.md`](../guides/existing-vault.md) for the round-trip semantics when a candidate lives inside a vault.

---

## `synth` — synthesize sources + harvest candidates

Primary command (#90). Default runs **both** lists: pending sources → `wiki/sources/`, then entity/concept candidates → `wiki/candidates/`.

```bash
python3 -m llmwiki synth --check            # probe the backend
python3 -m llmwiki synth --estimate         # cost + Candidates (pre-run state)
python3 -m llmwiki synth --force            # re-synth everything, then harvest
python3 -m llmwiki synth --sources-only     # legacy: sources only
python3 -m llmwiki synth --sessions-only    # all pending sessions (skip docs)
python3 -m llmwiki synth --docs-only        # all pending docs (skip sessions)
python3 -m llmwiki synth --candidates-only   # entity/concept candidates only
python3 -m llmwiki synth --candidates-only --min-refs 5
python3 -m llmwiki synth --path raw/sessions/<file>.md
python3 -m llmwiki synth                    # real run (sources + candidates)
```

`llmwiki synthesize` is a **deprecated** alias: it warns and defaults to `--sources-only` so existing scripts do not suddenly write candidate stubs. Prefer `synth`.

Before the first page is synthesized, a real run announces the batch: `Synthesizing 11 source(s) with ClaudeCLISynthesizer (2 at a time)` — the count is the work queue after up-to-date, ineligible, and already-claimed sources are excluded, so it is what the run will actually do. An empty queue says `Nothing to synthesize — every source is already up to date.` instead. Each result line then carries its position, `  [3/11] synthesized: <project> → <page>`, counting completed **sources** against that total; pages finish in whatever order the backend returns them, so the positions arrive out of order while the last one is always `N/N`.

`--estimate` prints the sources cost estimate with honest input units (#81): **Corpus: N eligible sources (S sessions + D docs)** and **Already synthesized: N of M eligible sources** (not page/file counts under `wiki/sources/`), then a separate **Source pages (current state): T on disk (Sess sessions + D docs + X stubs)** line for on-disk `.md` file counts. It also prints a `Candidates (pre-run state):` block — the harvestable shape of `wiki/sources/` **as it exists now**, with a note that pending sources are not yet reflected. It is not a forecast of what the next run will harvest (#113). After a successful real `synth` (not estimate), the CLI prints an end-of-run summary: `Synthesized:`, `Duration:`, optional `Tokens:` / `Cost:` when known. Harvest still prints its Candidates line once; the end summary does not repeat Candidates.

### Flags

| Flag | What |
|---|---|
| `--check` | Probe backend availability + exit (0 if reachable). |
| `--force` | Ignore state, re-synth every source. |
| `--estimate` | Print cached-vs-fresh token + dollar estimate for pending sources in eligible-source units (Corpus / Already synthesized), plus `Source pages (current state): T on disk (sessions + docs + stubs)` and `Candidates (pre-run state):` (current `wiki/sources/` shape — not a forecast of the next harvest) (#50 / #90 / #81 / #113). |
| `--sources-only` | Synthesize `wiki/sources/` only — skip candidate harvest (legacy `synthesize` behaviour). Mutually exclusive with `--candidates-only` / `--check` / `--estimate`. |
| `--sessions-only` | Synthesize only `raw/sessions/` — skip `raw/docs/`. Mutually exclusive with `--docs-only`. Combinable with `--path` / `--force` (paths under `raw/docs/` then exit 2). Incompatible with `--check` / `--estimate`. |
| `--docs-only` | Synthesize only `raw/docs/` — skip `raw/sessions/`. Mutually exclusive with `--sessions-only`. Combinable with `--path` / `--force` (paths under `raw/sessions/` then exit 2). Incompatible with `--check` / `--estimate`. |
| `--path PATH` | Synthesize only this raw session or doc under `raw/sessions/` or `raw/docs/` (repeatable; relative to the vault root, or absolute under it) (#62). Exit 2 if the path is missing or outside the vault. Still honours `filters.include_subagents` / `exclude_headless` (ineligible files are skipped even when named). Incompatible with `--check` / `--estimate`. |
| `--candidates-only` | Harvest entity/concept **candidates** from already-synthesized `wiki/sources/` into `wiki/candidates/`, then exit (#90). Reads the source layer only — never `raw/` — so it runs no per-source synthesis; cost is at most **one batched call** to classify the harvested names as entity vs concept, regardless of corpus size. Classification is fail-closed: any new target left unclassified stops the run with a non-zero exit and **writes nothing**, naming the cause (unreachable backend, incomplete/unparseable reply after retry, or unreadable source pages). Mutually exclusive with `--sources-only` / `--check` / `--estimate`. |
| `--min-refs N` | Candidate threshold: a `[[wikilink]]` target becomes a candidate when **N or more distinct source pages** name it (default: `3`). |
| `--concurrency N` | Synthesize N source pages at once, overriding `synthesis.concurrency` (default: `2`; range `1`–`16`). `1` runs strictly sequentially. Pages are I/O-bound on the backend, so the wall clock shrinks roughly in proportion; raise it only as far as your provider's rate limits and your machine allow. `all --with-synth` has no matching flag — it reads `synthesis.concurrency`. |
| `--vault PATH` | Read/write under the vault root; configures the active `llmwiki-state.json`. |

Backend is picked from `synthesis.backend` in `config.json` / `sessions_config.json` (`dummy` by default, `ollama` for local, `claude` for synchronous `claude -p`). See [`configuration.md`](../configuration.md#synthesis-backend).

> **Removed in v1.4.0:** `--list-pending` and `--complete` (agent-delegate
> pending prompts). Use `synthesis.backend: claude` instead.

### Auto-tagging (#351)

Every `synthesize` call now produces **topical** tags alongside the deterministic baseline.  The synthesizer emits a `<!-- suggested-tags: prompt-caching, rag, github-actions -->` block as the first line of its response; the pipeline parses it, strips it from the body, and merges the tags into frontmatter with:

- **Baseline preserved** — adapter, project slug, model family stay.
- **Maintainer wins** — on `--force`, whatever you added via `llmwiki tag add` is kept at the front of the list.
- **Stop-word filter** — the LLM can't re-add boilerplate tags (`session`, `summary`, `claude-code`, etc.).
- **Cap 5** — max 5 AI tags per page to prevent drift.
- **Near-dup rejection** — `prompt-cache` is blocked when `prompt-caching` is already on the page (threshold 0.80 + prefix check).

No extra API round-trip — rides the existing synthesis call, so cost estimates from `--estimate` are unchanged.  If the backend returns no suggested-tags block (dummy backend, malformed output), the page still ships with baseline tags.

---

## `synthesize` — deprecated alias for `synth --sources-only`

Kept so existing scripts do not break. Always prints a deprecation warning and defaults to sources-only (does **not** harvest candidates unless you pass `--candidates-only`). Prefer `llmwiki synth`.

```bash
python3 -m llmwiki synthesize --check
python3 -m llmwiki synthesize --estimate
python3 -m llmwiki synthesize --candidates-only   # still works; prefer synth
```

Same flags as [`synth`](#synth--synthesize-sources--harvest-candidates).

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
| `--json` | Print the migration report as JSON (script entry point only). |

The command is idempotent and prints cleanup suggestions for migrated legacy files.

It also repairs the vault (#23):

- **Legacy pending prompts are resolved, not re-queued.** Each `.llmwiki-pending-prompts/<uuid>.md` is matched against the pending sentinel pages (`<!-- llmwiki-pending: <uuid> -->`) still sitting in `wiki/sources/`. Prompts whose page has since been filled record nothing.
- **Dead `synth_request` items are purged.** The queue runner has no handler for that task type, so items left by an earlier migrator would fail forever. Re-running `migrate-state` removes them.
- **One `synthesize` task is enqueued** when — and only when — `synth.pending_total > 0` after the migration *and* no pending `synthesize` task is already queued, so re-running `migrate-state` never stacks duplicates. It drains the whole backlog; run it with `llmwiki queue run --vault <path>`.
- **Removed synthesis backends are flagged.** `synthesis.backend` values dropped in v1.4.0 (`agent`, `agent-delegate`, `agent_delegate`) silently fall back to `dummy`, which writes stub pages. The report prints a `WARNING:` telling you to set `claude`, `ollama`, or `dummy`.

Report keys: `state_file`, `migrated`, `orphan_cleanup_suggestions`, `warnings`, `pending_prompts_total`, `pending_prompts_unfilled`, `synth_request_items_purged`, `queued_synthesize`.

---

## `migrate-raw-redaction` — deterministic username rewrite in raw/ (#56)

Rewrites already-synced `raw/sessions/*.md` so home-path **and** dash-encoded agent-store segments use the `USER` placeholder (`-Users-<you>-…` → `-Users-USER-…`). In-place string rewrite only — does **not** re-convert from `~/.claude/projects` / Cursor stores, does **not** touch `wiki/`, and does **not** enqueue `synthesize`.

Prefer this over `llmwiki sync --force` when redaction completeness in existing `raw/` matters: agent transcripts are usually retained only ~30 days, so older sessions often have no source left to re-convert; force-sync followed by re-synth also burns LLM tokens for no benefit.

Implementation: `scripts/migrate_raw_encoded_username.py`; the CLI is a thin wrapper. After migrating, rebuild so `site/` picks up any display changes: `llmwiki build --vault PATH`.

```bash
python3 -m llmwiki migrate-raw-redaction --vault /path/to/vault --dry-run
python3 -m llmwiki migrate-raw-redaction --vault /path/to/vault
python3 scripts/migrate_raw_encoded_username.py --vault /path/to/vault --dry-run
```

### Flags

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `raw/sessions/`. |
| `--dry-run` | Report files that would change; write nothing. |
| `--real-username NAME` | Override `redaction.real_username` (default: config / `$USER`). |
| `--replacement-username NAME` | Override placeholder (default: `USER`). |

Idempotent: already-redacted files count as `unchanged`. Private local vaults that never publish `raw/` can skip this and only run `llmwiki build` after upgrading (see [UPGRADING.md](../UPGRADING.md)).

---

## `migrate-tools-used` — expand CallMcpTool frontmatter from origin stores

Rewrites `tools_used` and `tool_counts` in already-synced `raw/sessions/*.md` when the originating agent session file still exists. Re-reads records through the session adapter and applies the same `tool_use_recorded_names` expansion `llmwiki sync` uses (`CallMcpTool` → `mcp__{server}__{tool}`). In-place frontmatter update only — does **not** touch `wiki/`, does **not** enqueue `synthesize`, and **never** invents MCP names when the origin store is gone (TTL / deleted sessions count as `skipped_missing_origin` and stay unchanged).

Implementation: `scripts/migrate_tools_used_mcp.py`; the CLI is a thin wrapper. After migrating, rebuild so analytics and the site pick up the new tool names: `llmwiki build --vault PATH`.

```bash
python3 -m llmwiki migrate-tools-used --vault /path/to/vault --dry-run
python3 -m llmwiki migrate-tools-used --vault /path/to/vault
python3 scripts/migrate_tools_used_mcp.py --vault /path/to/vault --dry-run
```

### Flags

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `raw/sessions/`. |
| `--dry-run` | Report files that would change; write nothing. |
| `--config PATH` | Optional `sessions_config.json` override (record filters). |

Origin resolution prefers the vault's `llmwiki-state.json` sync keys (`adapter::home-relative-path`), then falls back to a glob under the adapter session store by `sessionId`. Claude Code JSONL is fully supported; Cursor and other non-JSONL stores work when the state key or glob resolves a readable origin path. Missing origins leave `CallMcpTool` entries intact for `wiki_adoption` body fallback.

---

## `migrate-page-kinds` — retype pages off the removed question/comparison kinds (#109)

`llmwiki/schema.py` lists five knowledge kinds — `source`, `entity`, `concept`, `project`, `synthesis`. A hand-written page declaring `type: question` or `type: comparison` is a `frontmatter_validity` **error**, and this migration clears it: each such page is retyped to `concept` and moved into `wiki/concepts/` **keeping its filename**, then `wiki/questions/` and `wiki/comparisons/` lose their `_context.md` and are pruned once empty.

Inbound links are left alone on purpose. `[[wikilinks]]` resolve by filename, never by folder, so a page that keeps its name keeps every inbound link and no referring page needs editing.

Two safety rules: a page whose filename is already taken in `wiki/concepts/` is retyped where it stands and reported as a collision rather than overwriting anything, and a removed folder still holding other content is left in place and reported rather than deleted. A vault with no removed-kind page prints `nothing to migrate` and exits 0 without writing.

Implementation: `llmwiki/migrate_page_kinds.py` — in the package rather than under `scripts/`, so it runs from a pip or Homebrew install with no checkout. After migrating, rebuild so `site/` picks up the new locations: `llmwiki build --vault PATH`.

```bash
python3 -m llmwiki migrate-page-kinds --vault /path/to/vault --dry-run
python3 -m llmwiki migrate-page-kinds --vault /path/to/vault
python3 -m llmwiki lint --vault /path/to/vault --rules frontmatter_validity
```

### Flags

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `wiki/`. |
| `--dry-run` | Report what would change; write nothing. |

Idempotent: a second run finds nothing to migrate. On a run that changed something the command reconciles `wiki/index.md` and appends `## [YYYY-MM-DD] migrate | page kinds` to `wiki/log.md`.

---

## `consolidate-topics` — dedupe + describe topics (#54)

One-time LLM pass over the topic list (not the sessions) that merges duplicate topic spellings (`LLM-Wiki` / `LLMWiki` / `llm wiki`) into one canonical node and writes short descriptions, caching the result in `.llmwiki-topics.json` for `llmwiki graph` / `llmwiki build`.

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

Re-run after large ingest batches so near-duplicate topic spellings don't fragment the knowledge graph.

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

Requires Graphify (`pip install llm-notebook[graph]`). Run `llmwiki graph` first to build the graph.

---

## `trace` — print downward provenance to raw transcripts (#122)

Walk a wiki page’s encoded chain to its source summaries and raw files. Uses only frontmatter (`sources:`, `source_file:`) — no body excerpts. Missing hops are marked; the walk still succeeds.

```bash
python3 -m llmwiki trace Demo --vault /path/to/vault
python3 -m llmwiki trace wiki/entities/Demo.md --vault /path/to/vault
```

### Positional

| Arg | What |
|---|---|
| `PAGE` | Vault-relative wiki path (`wiki/entities/Foo.md`) or a resolvable page name/stem under `wiki/`. |

### Flags

| Flag | What |
|---|---|
| `--vault PATH` | Trace under this vault (reads `wiki/` + `raw/`). Without it, uses `config.json` `vault.default_path` or the repo demo content. |

### Expected output

One line per hop: `role`, title, location; missing hops append ` (missing)`. A page with no provenance prints the page line plus `(no further provenance)`.

```
page    Demo  wiki/entities/Demo.md
source  Kickoff session  wiki/sources/kickoff.md
raw     Kickoff transcript  raw/sessions/2026-01-01T12-00-demo-kickoff.md
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Walk completed (including chains with missing hops). |
| `1` | Starting page could not be resolved (or locator unsafe / empty). |
| `2` | Configured `--vault` / default vault path is unusable. |

Guided repair of broken hops will live under `doctor` (#110); this command only prints the chain.

---

## `all` — run the full pipeline

Convenience entry point that runs `[sync?]` → `[synthesize?]` → `build` → `graph` → `lint` in order. AI-consumable exports (`llms.txt`, `sitemap.xml`, etc.) are written by `build`, not a separate step. This is the one command to run after agent sessions land to produce a CI-ready site.

```bash
python3 -m llmwiki all
python3 -m llmwiki all --with-sync              # convert sessions first
python3 -m llmwiki all --with-synth             # synthesize wiki/sources/ before build
python3 -m llmwiki all --with-sync --with-synth # full refresh from agent stores
python3 -m llmwiki all --graph-engine builtin   # skip optional graphify
python3 -m llmwiki all --skip-graph --strict    # fail CI on any lint issue
```

### Flags

| Flag | What |
|---|---|
| `--out DIR` | Output dir for `build`. Default: `site/`. |
| `--search-mode {auto,tree,flat}` | Forwarded to `build`. Default: `auto`. |
| `--graph-engine {builtin,graphify}` | Forwarded to `graph`. Default: `graphify`. |
| `--skip-graph` | Skip the graph step entirely (useful when graphify is not installed). |
| `--fail-fast` | Stop at the first non-zero step. Default: continue, report the worst exit code. |
| `--strict` | Exit `2` if `lint` reports any errors/warnings. |
| `--with-sync` | Run `sync --no-auto-build` before synthesize/build (convert agent sessions first). |
| `--with-synth` | Run `synthesize` before build (fills `wiki/sources/` from `raw/`; may invoke an LLM — default off for cost discipline, #383). |
| `--synth-force` | With `--with-synth`: pass `--force` to synthesize (re-synthesize all sessions). |
| `--vault PATH` | Run every step against this vault instead of the repo. |

Exit codes:

- `0` — every step succeeded.
- non-zero — forwarded from the first (or worst) failing step.
- `2` — `--strict` and lint reported issues.

---

## `watch` — near-real-time maintain when sessions finish

Polls adapter session stores on an interval and runs maintain when a session looks finished. Uses per-adapter turn-complete heuristics (Claude `stop_reason`, Cursor last role, Codex events). Mid-tool / permission loops stay deferred until the adapter reports safe. Adapters without a finished-signal still trigger after a 2s mtime settle — not a multi-minute quiesce.

Single-flight: only one maintain iteration at a time (`sync` → `synthesize` → `build` by default). Changes that arrive during a run set a dirty flag and retry after it finishes. Sync may time out (~180s); synthesize and build have no timeout.

```bash
python3 -m llmwiki watch
python3 -m llmwiki watch --adapter claude_code cursor
python3 -m llmwiki watch --interval 10 --settle 3
python3 -m llmwiki watch --dry-run
python3 -m llmwiki watch --no-synthesize --no-build
python3 -m llmwiki watch --vault ~/my-vault
```

### Flags

| Flag | What |
|---|---|
| `--adapter NAME [NAME ...]` | Limit to specific adapters. Default: every adapter with a session store on disk. |
| `--interval SECONDS` | Poll interval. Default: `5`. |
| `--settle SECONDS` | Mtime settle before ready check for adapters without a finished-signal. Default: `2`. |
| `--dry-run` | Detect finished sessions only; do not run maintain. |
| `--no-synthesize` | Skip the synthesize step. |
| `--no-build` | Skip the build step. |
| `--vault PATH` | Maintain this vault instead of the repo. |

---

## `install-automation` — daily scheduler + optional agent hooks

Interactive wizard (or pass `--yes` for non-interactive) that writes OS scheduler unit files, optional agent sync hooks, and automation status for the site Home panel. Profiles: **A** = `sync` (auto-build on); **B** = `sync --no-auto-build` → `synthesize` → `build`; **C** = `all --with-sync --with-synth --skip-graph`. Asks for daily run time (default `08:00`). Linux systemd timers use `Persistent=true` so a missed run catches up after boot. Logs land under XDG state (`~/.local/state/llmwiki/` by default). Writes `.llmwiki/automation-status.json` under the vault for the Home panel. Agent hooks default to skip — press Enter at the prompt to install nothing; type `install` to opt in (not recommended; prefer the OS scheduler or `watch`).

```bash
python3 -m llmwiki install-automation
python3 -m llmwiki install-automation --yes --profile B --hour 9 --minute 30
python3 -m llmwiki install-automation --yes --profile C --watch-enabled
python3 -m llmwiki install-automation --yes --synth-backend ollama --units-dir ~/.config/systemd/user
python3 -m llmwiki install-automation --vault ~/my-vault
```

### Flags

| Flag | What |
|---|---|
| `--yes` | Non-interactive: use flags and defaults; never installs hooks. |
| `--profile {A,B,C}` | Scheduler command profile. Default: `A`. |
| `--hour N` | Daily run hour (24h). Default: `8`. |
| `--minute N` | Daily run minute. Default: `0`. |
| `--synth-backend NAME` | Synthesis backend for automation status (interactive mode also writes `synthesis.backend` to `config.json`). |
| `--units-dir PATH` | Directory for systemd unit / launchd plist files. Default: `.llmwiki/units/` under the repo. |
| `--watch-enabled` | Record `watch` as enabled in automation status (does not start `watch`). |
| `--force-platform {linux,macos,windows}` | Override platform detection for unit format. |
| `--vault PATH` | Vault root for `automation-status.json`. |

---

## Exit codes (conventions)

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Operation failed (user-visible error) |
| `2` | Usage error (bad flags, missing file, etc.) |

Subcommands document their own non-zero exit conditions where relevant (`lint --fail-on-errors`).

---

## Related

- **[Slash commands](slash-commands.md)** — the `/wiki-*` surface used from Claude Code.
- **[UI reference](ui.md)** — every screen + nav surface on the compiled site.
- **[Configuration](../configuration.md)** · **[Full configuration reference](../configuration-reference.md)**.
