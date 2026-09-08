---
title: "CLI reference (part 2/15: remove — cascade-remove a raw doc and everything derived (#B2))"
slug: cli-reference-02
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/reference/cli.md"
content_sha256: 186543f38f0258ea703f9ef68071d930f7135ea481068df5e5b46346e0f33e99
---

> Part 2 of 15 of **CLI reference** — remove — cascade-remove a raw doc and everything derived (#B2).

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
