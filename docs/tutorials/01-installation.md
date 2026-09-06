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

llmwiki runs **locally**. Every session transcript stays on your machine. No
telemetry, no account, no network calls at build time. The install is
deliberately boring: `pip install`, done.

---

## Step 1 — Check your toolchain

```bash
python3 --version          # expect 3.12 or newer
git --version
```

macOS and most Linux distros already ship both. Windows: install Python from
[python.org](https://python.org) and git from [git-scm.com](https://git-scm.com).

## Step 2 — Install from PyPI (recommended)

The distribution is `llm-wiki-plus`; the CLI it installs is `llmwiki`:

```bash
pip install llm-wiki-plus
llmwiki --version
```

Expected output (version string matches the latest tagged release):

```
llmwiki <version>
```

Each version tag publishes the matching release, so a brand-new version reaches PyPI when its tag is pushed — if `pip` cannot find the version you expect yet, it hasn't been tagged.

Then scaffold a vault wherever you want it:

```bash
llmwiki init --vault .
```

Or via Homebrew, once [#247](https://github.com/Pratiyush/llm-wiki/issues/247) is set up:

```bash
brew install Pratiyush/tap/llmwiki
```

## Step 3 — (Alternative) Clone and run the setup script

Use this path to run unreleased code or to change llmwiki itself:

```bash
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki
```

### macOS / Linux

```bash
./setup.sh
```

### Windows

```cmd
setup.bat
```

The setup script is idempotent. Running it twice is safe.

It will:

- Create `raw/`, `wiki/`, `site/` directories if they don't exist
- Seed `wiki/index.md`, `wiki/overview.md`, `wiki/log.md`, `wiki/CRITICAL_FACTS.md`
- Install the `markdown` pip package (only runtime dep; everything else is stdlib)
- Verify the CLI launches: `python3 -m llmwiki --version`

## Step 4 — (Optional) Install via Docker

Zero-touch, no Python on your machine:

```bash
docker run -v $PWD:/wiki ghcr.io/pratiyush/llm-wiki:latest build
```

See [deploy/docker.md](../deploy/docker.md) for the full Compose setup.

---

## Verify

```bash
llmwiki --version                      # → llmwiki <version>
llmwiki adapters                       # lists every agent adapter and whether it's configured
```

From a clone, `python3 -m llmwiki <command>` does the same thing without the CLI being on your PATH.

The `adapters` output tells you which agents have session stores on this
machine — your first sync pulls from every one marked `configured ✓`.

---

## Troubleshooting

**`command not found: python3`** — install Python from python.org and re-open your terminal.

**`setup.sh: permission denied`** — `chmod +x setup.sh` once, then re-run.

**`ModuleNotFoundError: No module named 'markdown'`** — `pip install markdown` and re-run.

**`ImportError` on Python 3.11 or older** — llmwiki requires ≥ 3.12. Upgrade Python; on macOS use `brew install python@3.12`.

---

## Next

→ **[02 · First sync](02-first-sync.md)** — point llmwiki at your session history and build the site.
