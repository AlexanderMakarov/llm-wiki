# Getting started

5-minute quickstart. By the end you'll have a browsable wiki of every coding-agent session you've ever run.

## Prerequisites

- Python ≥ 3.12
- `git`
- Sessions from at least one supported agent already on disk:
  - **Claude Code** — `~/.claude/projects/`
  - **Codex CLI** — `~/.codex/sessions/`
  - **GitHub Copilot Chat** — VS Code workspaceStorage
  - **GitHub Copilot CLI** — `~/.copilot/session-state/`
  - **Cursor** — Cursor IDE workspaceStorage
  - **Gemini CLI** — `~/.gemini/`

llmwiki auto-detects whichever agents you have installed. No configuration needed.

That's it. No `npm`, no `brew`, no database, no account.

## Install

The git clone holds **code + demo seeds only**. Your transcripts, wiki pages, and built site live in a separate **vault** directory *outside* the repo, so personal data never lands in git. (See [the README](../README.md#personal-data-stays-outside-the-repo) for the full rationale.)

### 1. Clone the code and set up a venv

Clone anywhere — the directory is just the engine, not your data.

**macOS / Linux**

```bash
git clone git@github.com:AlexanderMakarov/llm-wiki.git
cd llm-wiki
python3 -m venv .venv && source .venv/bin/activate
./setup.sh
```

**Windows**

```cmd
git clone https://github.com/AlexanderMakarov/llm-wiki.git
cd llm-wiki
python -m venv .venv && .venv\Scripts\activate
setup.bat
```

`setup.sh` / `setup.bat` is idempotent and:

1. Installs the `markdown` runtime dep via `pip install --user`. Syntax highlighting runs in the browser via highlight.js, so the build stays stdlib-only.
2. Runs `llmwiki adapters` to show which agents are detected.
3. Reports `sync --status` so you see how many sessions *would* convert.

> setup **does not** scaffold `raw/`, `wiki/`, `site/` inside the clone — that data belongs in your vault (step 2). If no vault is configured yet, setup warns and points you here instead of growing data in the git checkout.

### 2. Create a vault and point `config.json` at it

Make an empty directory anywhere for your personal data, then tell llmwiki where it is via a gitignored `config.json` at the repo root:

```bash
mkdir -p ~/llmwiki-vault
cat > config.json <<'JSON'
{
  "vault": { "default_path": "/home/you/llmwiki-vault" }
}
JSON
llmwiki init          # scaffolds raw/ wiki/ site/ INTO the vault
```

With `vault.default_path` set, `sync` / `build` / `synth` / `queue` / `lint` / `init` all target the vault automatically — no `--vault` flag needed. Override it for a single run with `--vault PATH`.

### Checking detected agents

After install, run `llmwiki adapters` to see which session stores were found:

```bash
python3 -m llmwiki adapters
```

Example output:

```
Registered adapters:
  claude_code       available: yes  (Claude Code — reads ~/.claude/projects/*/*.jsonl)
  codex_cli         available: yes  (Codex CLI — reads ~/.codex/sessions/**/*.jsonl)
  copilot_chat      available: no   (GitHub Copilot Chat — reads VS Code workspaceStorage chatSessions)
  copilot_cli       available: no   (GitHub Copilot CLI — reads ~/.copilot/session-state/*/events.jsonl)
  cursor            available: yes  (Cursor IDE — reads chat history)
  gemini_cli        available: no   (Gemini CLI — reads ~/.gemini/ session history)
  obsidian          available: no   (Obsidian vault)
```

> The PDF adapter was removed in the simplification sweep — `llmwiki adapters` no longer lists it.

Any adapter marked `available: yes` will be included when you run `llmwiki sync`. See [multi-agent-setup.md](multi-agent-setup.md) for details on configuring individual agents.

## Three commands after install

With `vault.default_path` set (step 2 above), these all read and write the vault, not the clone:

```bash
llmwiki sync     # pull new sessions from your agent store → <vault>/raw/sessions/<project>/*.md
llmwiki synth    # fill wiki/sources/ and harvest wiki/candidates/ (then review)
llmwiki build    # compile <vault>/raw/ + <vault>/wiki/ → <vault>/site/
```

Open `<vault>/site/index.html` in a browser — the site is plain files, so nothing has to be running and nothing is fetched — and click around. Try:

- **⌘K** or **Ctrl+K** — command palette
- **/** — focus the search bar
- **g h / g p / g s** — jump to home / projects / sessions
- **j / k** — navigate sessions table
- **?** — keyboard shortcut help

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

The vault lives outside the repo, so it is never committed and never sent anywhere. The clone itself stays clean — only code and demo seeds.

## New in recent versions

- **Model pages** (`/models/`) — structured profile pages for every LLM model referenced in your sessions, with pricing, context window, and usage stats.
- **VS-comparisons** (`/vs/`) — auto-generated side-by-side diffs of related AI-model entities (e.g. Claude vs GPT-4).
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
