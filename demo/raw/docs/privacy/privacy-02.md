---
title: "Privacy (part 2/2: The claude -p synthesis exception)"
slug: privacy-02
project: privacy
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/privacy.md"
content_sha256: 3c4b9e2990e174d9a504cb5659f664f12a04d39d3226091c3823378bdada5ae0
---

> Part 2 of 2 of **Privacy** — The claude -p synthesis exception.

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

The `.github/workflows/pages.yml` workflow deploys a public demo site to `https://alexandermakarov.github.io/llm-wiki/` on every tag push. It uses the **synthetic corpus** committed under `demo/`, not your real session history. Your actual wiki is never touched by this workflow.

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
