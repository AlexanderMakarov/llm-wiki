---
title: "CLI reference (part 1/19)"
slug: cli-reference-01
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/cli.md"
content_sha256: 80394a36c35bb48cc2c8a5640d51d9180b601f9274c4cb944e18a4be261b1dbc
---

> Part 1 of 19 of **CLI reference**.

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
| **Look around** | `lint` · `search` · `query` · `trace` · `graph` · `adapters` · `usage` · `version` |
| **Take things out** | `remove` |
| **Rare — one-time** | `migrate` · `queue` |

The shorter alias `llmwiki` works too once the package is installed (`pip install llm-wiki-plus` or via Homebrew — see [`deploy/pypi-publishing.md`](../deploy/pypi-publishing.md) / [`deploy/homebrew-setup.md`](../deploy/homebrew-setup.md)).

TAB completion of these command names in bash and zsh is one line in your shell startup file, which `./setup.sh` offers to add — see [Shell completion](../getting-started.md#shell-completion).

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
