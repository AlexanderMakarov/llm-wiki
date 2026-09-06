---
title: "01 · Installation"
type: tutorial
docs_shell: true
---

# 01 · Installation

**Time:** 5 minutes
**You'll need:** Python 3.12+, `git`, and at least one AI-coding agent already installed with session history on disk.
**Result:** A working `llmwiki` CLI on your PATH (or runnable via `python3 -m llmwiki`).

---

## Why this matters

llmwiki runs **locally**. Every session transcript stays on your machine. No telemetry, no account, no network calls at build time. The install is deliberately boring: pick one path below, then verify.

---

## Step 1 — Check your toolchain

```bash
python3 --version          # expect 3.12 or newer
git --version
```

macOS and most Linux distros already ship both. Windows: install Python from [python.org](https://python.org) and git from [git-scm.com](https://git-scm.com).

## Step 2 — Install (pick one)

The day-to-day command is always `llmwiki`. The PyPI distribution name is `llm-wiki-plus` (PyPI already has an unrelated `llmwiki`, and rejects `llm-wiki` as too similar).

### Option A — PyPI (recommended)

```bash
pip install llm-wiki-plus
llmwiki --version
```

Expected output (version string matches the latest tagged release):

```
llmwiki <version>
```

Each version tag publishes the matching release. If `pip` cannot find the version you expect yet, that tag has not been pushed.

Then scaffold a vault wherever you want it:

```bash
llmwiki init --vault .
```

### Option B — Homebrew

Once the tap from [#212](https://github.com/AlexanderMakarov/llm-wiki/issues/212) is live:

```bash
brew install AlexanderMakarov/tap/llmwiki
```

The formula name stays `llmwiki` (not `llm-wiki-plus`); it installs from the GitHub release tarball.

### Option C — Clone (unreleased code or contributing)

```bash
git clone https://github.com/AlexanderMakarov/llm-wiki.git
cd llm-wiki
```

macOS / Linux:

```bash
./setup.sh
```

Windows:

```cmd
setup.bat
```

The setup script is idempotent. It scaffolds `raw/` / `wiki/` / `site/`, installs the `markdown` runtime dep, and checks `python3 -m llmwiki --version`.

### Option D — Docker

Zero-touch, no Python on your machine. Image URLs are tracked in [#211](https://github.com/AlexanderMakarov/llm-wiki/issues/211); see [deploy/docker.md](../deploy/docker.md) for Compose and the current image name.

---

## Verify

```bash
llmwiki --version                      # → llmwiki <version>
llmwiki adapters                       # lists every agent adapter and whether it's configured
```

From a clone, `python3 -m llmwiki <command>` does the same thing without the CLI being on your PATH.

The `adapters` output tells you which agents have session stores on this machine — your first sync pulls from every one marked `configured ✓`.

---

## Troubleshooting

**`command not found: python3`** — install Python from python.org and re-open your terminal.

**`setup.sh: permission denied`** — `chmod +x setup.sh` once, then re-run.

**`ModuleNotFoundError: No module named 'markdown'`** — `pip install markdown` and re-run.

**`ImportError` on Python 3.11 or older** — llmwiki requires ≥ 3.12. Upgrade Python; on macOS use `brew install python@3.12`.

---

## Next

→ **[02 · First sync](02-first-sync.md)** — point llmwiki at your session history and build the site.
