---
title: "Getting started (part 1/2)"
slug: getting-started-01
project: getting-started
type: source
tags: [wiki-add, raw-doc]
date: 2026-10-01
source: "docs/getting-started.md"
content_sha256: f632f2ff25f720f7c59ae4aca09de7dd17461bfff04b1f593035cdeb6f9eee2f
---

> Part 1 of 2 of **Getting started**.

# Getting started

5-minute quickstart. By the end you'll have a browsable wiki of every coding-agent session you've ever run.

## Prerequisites

- Python ≥ 3.12
- `git`
- Sessions from at least one supported agent already on disk (Claude Code, Codex CLI, Cursor Agent CLI, OpenClaw, Copilot, Gemini, etc.) — see [multi-agent-setup.md](multi-agent-setup.md) for default paths.

A bare `llmwiki sync` runs every **enabled** coding-agent source whose store exists on disk. Configure sources in `config.json` under `adapters.<name>` or run `llmwiki configure-sources` after install. Use `--adapter <name>` to limit a single run.

That's it. No `npm`, no `brew`, no database, no account.

## Install

The git clone holds **code + demo seeds only**. Your transcripts, wiki pages, and built site live in a separate **vault** directory *outside* the repo, so personal data never lands in git. (See [the README](../README.md) for the product overview.)

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
  name              present   enabled     active   description
  claude_code       yes       auto        yes      Claude Code — reads ~/.claude/projects/...
  openclaw          yes       explicit    yes      OpenClaw — reads configured roots...
```

Run `llmwiki configure-sources` after install to probe stores and write `adapters.<name>` settings. The interview asks a shared lookback first (default today−30) and shows Sessions · Earliest · In last 30 days per source before Enable; skip configure to keep unlimited history. Full support map: [multi-agent-setup.md](multi-agent-setup.md). Lookback keys: [configuration-reference.md](configuration-reference.md#sync-lookback).

### Shell completion

Pressing TAB after `llmwiki ` lists every command, and a typed prefix narrows the list (`llmwiki sy` offers `sync` and `synth`). Only command names complete — not flags, and not names under a command. Only the `llmwiki` entry point completes; `python3 -m llmwiki` does not.

On macOS / Linux, `./setup.sh` offers this at the end when run in an interactive terminal: it asks `Add llmwiki TAB completion to ~/.bashrc? [Y/n]` (or `~/.zshrc` when your login shell is zsh), and on yes writes the line below and prints which file it changed. Re-running setup replaces that line with the current command list instead of adding a second one, and leaves the rest of the file alone. On macOS, bash users get `~/.bash_profile` instead of `~/.bashrc`, because Terminal and iTerm start bash as a login shell, which does not read `~/.bashrc`. For any other shell it changes nothing and prints the bash line for you to add yourself. Set `LLMWIKI_SKIP_COMPLETION=1` to skip the question; it is never asked when setup runs non-interactively.

To enable it by hand (for example after `pip install`), paste the line for your shell into its startup file and open a new terminal.

bash — `~/.bashrc` (`~/.bash_profile` on macOS):

```bash
_llmwiki_complete() { COMPREPLY=(); if [ "$COMP_CWORD" -eq 1 ]; then COMPREPLY=($(compgen -W "init sync build usage adapters configure-sources graph lint queue migrate install-agent-kit candidates synth add remove search query trace version all watch install-automation" -- "${COMP_WORDS[1]}")); fi; }; complete -o default -F _llmwiki_complete llmwiki # llmwiki-completion
```

zsh — `~/.zshrc`:

```zsh
(( $+functions[compdef] )) || { autoload -Uz compinit && compinit; }; _llmwiki_complete() { _arguments '1:command:(init sync build usage adapters configure-sources graph lint queue migrate install-agent-kit candidates synth add remove search query trace version all watch install-automation)' '*::arg:_files'; }; compdef _llmwiki_complete llmwiki # llmwiki-completion
```
