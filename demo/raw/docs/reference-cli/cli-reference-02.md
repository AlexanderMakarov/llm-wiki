---
title: "CLI reference (part 2/19: add — add a document to the wiki (#16 / #273))"
slug: cli-reference-02
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-10-01
source: "docs/reference/cli.md"
content_sha256: 8c1258c0faddb3eb988de6c7870bdada2b983cd07f6b325b78b35e680759efeb
---

> Part 2 of 19 of **CLI reference** — add — add a document to the wiki (#16 / #273).

## `add` — add a document to the wiki (#16 / #273)

Converts a URL, file, folder, or stdin in the process locale encoding (`-`) into raw Markdown under `raw/docs/`, then (by default) rebuilds the site so the new material is visible on Raw / Home. **Does not** synthesize `wiki/sources/` unless you pass `--synthesize`. Path and URL sources may be freely mixed and repeated; `-` (stdin) must be the only source in that invocation. MCP `wiki_add` is a thin proxy onto the same shared `run_add` path — see [mcp.md](mcp.md#wiki_add).

```bash
python3 -m llmwiki add https://example.com/some-article
python3 -m llmwiki add ./notes.pdf ./research-folder/
python3 -m llmwiki add https://example.com/post --title "Custom Title" --tag research
python3 -m llmwiki add ./doc.md --project my-project --note "Imported from Slack"
python3 -m llmwiki add https://example.com/post --dry-run
python3 -m llmwiki add ./doc.md --synthesize          # opt in to wiki/sources for this run
cat notes.md | python3 -m llmwiki add - --title "Piped notes"
```

Default outcome: raw file(s) written, synth-pending refreshed, site rebuilt. No new `wiki/sources/` pages from that add. Pass `--synthesize` to run synthesis on only the docs this add wrote (same rollback rules as before). Pass `--no-build` to skip the site rebuild. `--no-synthesize` is a deprecated warn+no-op alias (synthesis is already off by default) so old scripts keep working for one release.

Stdin (`add -`) and MCP `content` use the piped-text conversion path: frontmatter `source: "piped"` (never a `/tmp/…` provenance). Prefer `--title` for stdin; otherwise title derives from the first heading / body start.

**Source-layer guardrail:** pass the user's exact path, URL, or text. Do not reconstruct input from `wiki/sources/` or other derived pages unless the user asked.

### Flags

| Flag | What |
|---|---|
| `SOURCE` | URL (`http`/`https`), file, folder, or `-` for stdin in the process locale encoding. Repeatable except `-` (cannot mix with other sources). |
| `--title TEXT` | Override title derivation (single source only). |
| `--project NAME` | Group under `raw/docs/<NAME>/` instead of the doc's own slug. |
| `--tag TAG` | Extra frontmatter tag (repeatable). |
| `--note TEXT` | Blockquote note prepended to the document body. |
| `--synthesize` | Opt in to synthesize `wiki/sources/` for the docs this add wrote (off by default). |
| `--no-synthesize` | Deprecated warn+no-op; synthesis is already off by default (#273). |
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
