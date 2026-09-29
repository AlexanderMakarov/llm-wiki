---
title: "Getting started (part 2/2: Three commands after install)"
slug: getting-started-02
project: getting-started
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/getting-started.md"
content_sha256: da0d0f50f9fdf3b2b102da40e3d4083436abcdec03b0a35a2d2cdee745770ee1
---

> Part 2 of 2 of **Getting started** — Three commands after install.

## Three commands after install

With `vault.default_path` set (step 2 above), these all read and write the vault, not the clone:

```bash
llmwiki sync     # pull new sessions from your agent store → <vault>/raw/sessions/<project>/*.md
llmwiki synth    # fill wiki/sources/ and harvest wiki/candidates/ (then review)
llmwiki build    # compile <vault>/raw/ + <vault>/wiki/ → <vault>/site/
```

`llmwiki all` runs all three in one go, then builds the graph and reports quality findings.

**Day-to-day for agents:** point your MCP client at `python3 -m llmwiki.mcp` so tools like `wiki_search` / `wiki_read_page` hit the same vault (see [MCP reference](reference/mcp.md)). **For humans:** Open `<vault>/site/index.html` after `build` (plain files; nothing has to keep running) to check pipeline state, metrics, and settled entities/concepts — and try:

- **⌘K** or **Ctrl+K** — command palette
- **/** — focus the search bar
- **g h / g p / g s** — jump to home / projects / sessions
- **j / k** — navigate sessions table
- **?** — keyboard shortcut help

### Add a non-session document

Session sync is the default path, but notes and external sources are first-class too. `llmwiki add` writes into `<vault>/raw/docs/`; the same `synth` → review candidates → `build` loop then folds them into wiki source pages alongside sessions. Mix kinds freely:

```bash
llmwiki add notes.md                  # local markdown file
llmwiki add https://example.com/post  # web page
llmwiki add ./paper.pdf               # PDF
llmwiki add ./research-folder/        # folder of docs
```

By default `add` writes raw docs and rebuilds the site so they show up under Raw / Home; it does **not** synthesize `wiki/sources/` unless you pass `--synthesize`. Run `llmwiki synth` later (or opt in on the same add) when you want wiki source pages. Pass `--no-build` to skip the site rebuild. Flags (`--title`, `--tag`, `--project`, `--dry-run`, stdin `-`, and more): [CLI reference — add](reference/cli.md#add--add-a-document-to-the-wiki-16--273).

## Next: let it run itself

You only have to do that by hand once. Hand the loop to a daily job:

```bash
llmwiki install-automation
```

The wizard asks one question — should the daily job just collect your sessions, or also summarise them into wiki pages? — then offers the optional extras and a schedule, and shows you the exact command line before it writes anything. Collecting only never contacts an AI provider; summarising does, which is why the wizard points you at `llmwiki synth --estimate` first. Every answer is also a flag, for an unattended install: [CLI reference](reference/cli.md#install-automation--set-up-the-daily-job).

## Where your data ends up

Everything lands in your **vault** directory (the `vault.default_path` from step 2), *not* the git clone:

```
/home/you/llmwiki-vault/      ← vault root (NOT …/wiki)
├── raw/sessions/             # converted transcripts
│   ├── ai-newsletter/
│   │   ├── 2026-04-04-<slug>.md
│   │   └── ...
│   └── <other-project>/
├── wiki/                     # LLM-maintained wiki pages
│   ├── index.md
│   ├── log.md
│   ├── overview.md
│   ├── sources/
│   ├── candidates/
│   ├── entities/
│   └── concepts/
├── site/                     # generated static HTML
│   ├── index.html
│   ├── search-index.json
│   ├── projects/
│   └── sessions/
└── llmwiki-state.json        # unified sync + queue + synth + quarantine state
```

The vault lives outside the repo, so it is never committed and never sent anywhere. The clone itself stays clean — only code and demo seeds. `raw/`, `wiki/` (except the committed `demo/wiki/`), `site/`, `config.json`, and `llmwiki-state.json` are gitignored; the per-path table that used to live in the README is this tree.

### Queue without auto-sync

If you are not using SessionStart hooks, drive the unified queue by hand:

```bash
llmwiki queue status
llmwiki queue run --limit 20
llmwiki migrate state   # one-time: merge legacy .llmwiki-* into llmwiki-state.json
```

Flags and output: [docs/reference/cli.md](reference/cli.md#queue--inspect-and-run-unified-queue).

## New in recent versions

- **Model pages** (`/models/`) — structured profile pages for every LLM model referenced in your sessions, with pricing, context window, and usage stats.
- **Project topics** — auto-detected topic chips on project pages, extracted from session content.
- **Multi-agent support** — sync sessions from Claude Code, Codex CLI, Copilot, Cursor, and Gemini CLI simultaneously. Each session gets a colored badge showing which agent produced it.

## Building the wiki (Karpathy layer 2)

The `sync` step populates the vault's `raw/sessions/` with markdown. To build the actual **wiki** on top of that — `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`, linked by `[[wikilinks]]` — you need an LLM in the loop. That's where Claude Code (or any supported agent) comes in.

Inside a Claude Code session at the llm-wiki repo root (with your `config.json` pointing at the vault):

```
/wiki-ingest raw/sessions/ai-newsletter/
```

The agent reads the source markdowns from the vault, writes summary pages, cross-links entities, and updates `wiki/index.md`. See [CLAUDE.md](../CLAUDE.md) for the full Ingest Workflow.

Then re-run `llmwiki build` to get the compiled wiki into the HTML site.

## Auto-sync on session start (optional)

To make sync happen automatically every time you start Claude Code, add a `SessionStart` hook to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "(python3 /absolute/path/to/llm-wiki/llmwiki/convert.py > /tmp/llmwiki-sync.log 2>&1 &) ; exit 0"
          }
        ]
      }
    ]
  }
}
```

The `( ... &) ; exit 0` pattern backgrounds the sync and makes sure it never blocks Claude Code starting.

## Next steps

- [architecture.md](architecture.md) — the 3-layer Karpathy + 8-layer build breakdown
- [configuration-reference.md](configuration-reference.md) — every CLI flag, env var, and config option
- [multi-agent-setup.md](multi-agent-setup.md) — running all 6 agents at once
- [privacy.md](privacy.md) — redaction + `.llmwikiignore` + localhost-only binding
- [deploy/github-pages.md](deploy/github-pages.md) — deploy to GitHub Pages
- [faq.md](faq.md) — common questions answered
- [troubleshooting.md](troubleshooting.md) — common errors and fixes
- [adapter-authoring.md](adapter-authoring.md) — write your own adapter
- [api-guide.md](api-guide.md) — use llmwiki as a Python library
- [adapters/claude-code.md](adapters/claude-code.md) — Claude Code adapter details
- [adapters/obsidian.md](adapters/obsidian.md) — use an Obsidian vault as an additional source
