---
title: "CLI reference (part 1/15)"
slug: cli-reference-01
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-07
source: "docs/reference/cli.md"
content_sha256: 68214fcdadc8d21482c73af718d17b4858152fb41607ffe75ccafc726af46640
---

> Part 1 of 15 of **CLI reference**.

---
title: "CLI reference"
type: navigation
docs_shell: true
---

# CLI reference

**Every** `python3 -m llmwiki <subcommand>` — with every flag, realistic examples, and expected output. If a command isn't listed here it isn't shipping. This page is generated against the live argparse tree, so adding a flag without documenting it will fail the guardrail test.

Global flags: `-h` / `--help` on every command, `--version` at the root.

`llmwiki --help` groups commands into six lifecycle sections (same labels and order as the table below). Canonical loop: ingest (`sync` / `add`) → summarise (`synth`) → review candidates → publish (`build`). `synth` does not rebuild the site; run `build` afterwards when Home / Analytics should refresh.

---

## Top-level

```bash
python3 -m llmwiki --version    # → llmwiki <version>
python3 -m llmwiki --help       # lifecycle map of every subcommand
python3 -m llmwiki              # same as --help
```

| Group | Commands |
|---|---|
| **Start here** | `init` · `configure-sources` · `install-agent-kit` |
| **Daily loop (this order)** | `sync` · `add` · `synth` · `candidates` · `build` |
| **Run the loop for me** | `all` · `watch` · `install-automation` |
| **Look around** | `lint` · `query` · `trace` · `graph` · `adapters` · `usage` · `version` |
| **Take things out** | `remove` |
| **Rare — one-time** | `migrate` · `queue` |

The shorter alias `llmwiki` works too once the package is installed (`pip install llm-wiki-plus` or via Homebrew — see [`deploy/pypi-publishing.md`](../deploy/pypi-publishing.md) / [`deploy/homebrew-setup.md`](../deploy/homebrew-setup.md)).

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
| `--adapter NAME [NAME ...]` | Limit to / load specific adapters. Default: every ingest-ready coding-agent source with a present store and no `enabled: false`. Notes intake still needs `enabled: true`. See [multi-agent-setup.md](../multi-agent-setup.md). |
| `--since YYYY-MM-DD` | Only sessions on/after this date (e.g. `--since 2026-04-01`). Overrides durable `filters.since` / `adapters.*.since` for every source this run. Absent CLI flag: use config lookback, or unlimited if unset. See [configuration-reference.md — Sync lookback](../configuration-reference.md#sync-lookback). |
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
