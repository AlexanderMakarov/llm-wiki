# Privacy

llmwiki processes session transcripts that can contain PII, API keys, file paths, and internal URLs. Privacy is baked into the core design. This document is the full story on what llmwiki does to protect you — and where you're still responsible.

## Hard rules

These are non-negotiable and enforced in both code and CI:

1. **Redaction is ON by default.** Username, API keys, tokens, passwords, and emails are redacted before anything hits `raw/`.
2. **Nothing listens.** llmwiki ships no server; the built site is files you open in a browser.
3. **No telemetry, ever.** The tool never calls home. No usage counts, no adapter pings, no error uploads.
4. **No network by default.** Everything runs offline after install. `--synthesize` is the one exception — it calls the local `claude` binary on your machine — and it's opt-in.
5. **raw/, wiki/, site/, and .ingestion-state.json are gitignored.** They never enter version control.
6. **Privacy grep in CI.** GitHub Actions fails the build if any committed file contains the maintainer's real username.
7. **Gitleaks in CI.** Secret scanning blocks merges on any detected API key, token, or password.

## What gets redacted

Everything in this table is redacted at the **converter** layer — the moment each `.jsonl` record is parsed into markdown. The redaction happens before the file hits `raw/`.

| Pattern | What matches | Replacement |
|---|---|---|
| Username in paths | `/Users/<you>/…`, `/home/<you>/…`, and dash-encoded store segments (`-Users-<you>-…`, `-home-<you>-…`) | `/Users/USER/…`, `-Users-USER-…` |
| API key tokens | `(?i)(api[_-]?key\|secret\|token\|bearer\|password)[\"'\s:=]+[\w\-\.]{8,}` | `<REDACTED>` |
| Anthropic/OpenAI keys | `sk-[A-Za-z0-9]{20,}` | `<REDACTED>` |
| Emails | `[\w.+-]+@[a-zA-Z0-9-]+\.[\w.-]+` | `<REDACTED>` |
| Thinking blocks | `<thinking>…</thinking>` | dropped entirely (configurable) |

All patterns live in `examples/sessions_config.json` under `redaction.extra_patterns`. You can add your own (company domain, customer names, internal hostnames, etc.).

**Already-synced `raw/`:** new syncs apply encoded-segment redaction automatically. Files written before that change keep whatever was on disk (`raw/` is immutable during normal sync). To rewrite them without re-converting from agent stores (transcripts are often gone after ~30 days) and without re-synthesizing wiki pages, run `llmwiki migrate-raw-redaction --vault PATH` — see [UPGRADING.md](UPGRADING.md) and [CLI reference](reference/cli.md#migrate-raw-redaction--deterministic-username-rewrite-in-raw-56).

## What is NOT redacted by default

- **File paths that are not under your home directory.** `/opt/foo` and `/var/log/bar` are rendered as-is.
- **Relative paths.** `src/main.py` is rendered as-is.
- **Tool arguments that aren't recognised.** Bash commands get the first line preserved; Read/Write paths get the path preserved.
- **Text content inside user prompts** — because the prompt IS the signal. If you pasted a contract or a password into a prompt, it's in `raw/`.

**This is why `raw/` is gitignored and nothing llmwiki produces is served anywhere.**

## Adding your own redaction patterns

Edit `config.json`:

```jsonc
{
  "redaction": {
    "real_username": "your-unix-username",
    "replacement_username": "USER",
    "extra_patterns": [
      // defaults...
      "(?i)(api[_-]?key|secret|token|bearer|password)[\"'\\s:=]+[\\w\\-\\.]{8,}",
      "sk-[A-Za-z0-9]{20,}",
      "[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+",

      // yours:
      "acmecorp\\.internal",
      "ACME-[0-9A-Z]{6,}",
      "ghp_[A-Za-z0-9]{36}"
    ]
  }
}
```

Re-run `llmwiki sync --force` to apply the new patterns to existing sessions.

## `.llmwikiignore` — coarse-grained exclusion

For entire projects, dates, or files you never want in the wiki at all, use `.llmwikiignore`. Gitignore syntax, one pattern per line:

```
# Skip a whole project
confidential-client/

# Skip anything from before a date
*2025-*

# Skip specific slugs
ai-newsletter/2026-04-04-secret-deal-*
```

## Where your data lives

| Path | What's there | Gitignored? |
|---|---|---|
| `~/.claude/projects/*/*.jsonl` | Raw session transcripts | N/A (outside repo) |
| `<vault>/raw/sessions/` | Converted, redacted markdown | ✅ (vault lives outside the repo) |
| `<vault>/wiki/` | LLM-maintained wiki pages | ✅ |
| `<vault>/site/` | Generated HTML site | ✅ |
| `<vault>/llmwiki-state.json` | Unified sync + queue + synth state | ✅ |
| `llm-wiki/config.json` | Your config override (points at the vault) | ✅ |

`<vault>` is the directory you set as `vault.default_path`. It lives outside the git clone, so nothing under it is tracked. When no vault is configured, these paths fall back to the repo root (demo/dev use). Everything with a ✅ stays on your machine — none of it is committed, uploaded, or synced.

## The `claude -p` synthesis exception

`llmwiki build --synthesize` is the one feature that sends data off your machine. It does exactly this:

1. Builds a JSON summary of your projects (project names, session counts, dates, models — no content)
2. Calls the local `claude` binary (which Claude Code installed)
3. Gets back a 200–300 word markdown overview
4. Embeds it in `site/index.html`

Even this is off by default. You have to pass `--synthesize` explicitly. If you don't want any external API calls, just don't pass the flag — the home page still renders with project cards and stats, just without the synthesis paragraph.

## Nothing listens, nothing is fetched

llmwiki ships no server. The built site is a directory of files you open in a browser, and every script and stylesheet it loads — including the code-highlighting library and its themes — is written into `site/` at build time. Opening it offline gives the same result as opening it online, and no process of yours is reachable from the network.

If you want to share `<vault>/site` with a colleague, copy it or publish it to a static host you control. Note that it may contain redacted transcripts of your sessions — don't put it anywhere you wouldn't put those.

## GitHub Pages (Self-Demo)

The `.github/workflows/pages.yml` workflow deploys a public demo site to `https://pratiyush.github.io/llm-wiki/` on every tag push. It uses the **synthetic corpus** committed under `demo/`, not your real session history. Your actual wiki is never touched by this workflow.

## Incident response

If you accidentally commit real PII or a secret:

1. **Don't just push a fix.** The history still has it.
2. Rotate the credential immediately if it's a key/token.
3. Use `git filter-repo` or `BFG Repo-Cleaner` to rewrite history.
4. Force-push to the branch.
5. Ask any collaborators to re-clone.
6. If the repo is public and the commit was pushed, assume the secret is compromised and rotate.

## Questions?

Open an issue with the `privacy` label. Or email — but not with PII in the subject line.
