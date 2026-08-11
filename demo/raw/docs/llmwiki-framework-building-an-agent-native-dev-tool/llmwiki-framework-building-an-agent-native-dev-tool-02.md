---
title: "llmwiki Framework — Building an Agent-Native Dev Tool (part 2/3: Phase 3 — Structure)"
slug: llmwiki-framework-building-an-agent-native-dev-tool-02
project: llmwiki-framework-building-an-agent-native-dev-tool
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/framework.md"
content_sha256: eaa0b1b799c976996e7f4c0abe139ab99b35aae734b1fa67f0b35a8648668fa7
---

> Part 2 of 3 of **llmwiki Framework — Building an Agent-Native Dev Tool** — Phase 3 — Structure.

## Phase 3 — Structure

Same as parent. llmwiki layout is defined in `docs/architecture.md`. Key invariants:

```
llmwiki/                      # Python package (renamed from tools/)
├── __init__.py
├── __main__.py               # enables `python3 -m llmwiki`
├── cli.py                    # argparse entry
├── convert.py                # .jsonl → markdown
├── build.py                  # markdown → HTML
├── serve.py                  # HTTP server
├── adapters/
│   ├── __init__.py           # registry
│   ├── base.py               # BaseAdapter
│   ├── claude_code.py
│   └── codex_cli.py
└── templates/
    ├── style.css             # embedded as Python string for single-file rendering
    └── script.js             # embedded as Python string

raw/, wiki/, site/            # [gitignored] data layers
bin/, docs/, examples/        # user-facing
.claude/commands/             # Claude Code slash commands (committed)
.github/workflows/            # CI (committed)
```

### Hard rule — no dual Python package

There is exactly ONE `llmwiki/` directory that is a Python package. Tools live inside it, not alongside it in a `tools/` sibling. (This is a lesson from the earlier llm-wiki workspace which had both.)

---

## Phase 4 — Content

Same as parent. For llmwiki specifically:

- **CSS/JS are Python string constants** inside `build.py` — single-file rendering, no template loader, no file watching complexity.
- **No templates directory as separate files** (the `templates/` subdirectory is a stub for future split when the files grow beyond 2000 lines).
- **Syntax highlighting** uses highlight.js loaded from a CDN at view time. No build-time syntax parsing required.

### Performance Budget (cross-cutting rule)

| Metric | Target | Measured 2026-04-08 |
|---|---|---|
| Cold build time (300 sessions) | < 15s | 9s |
| Incremental build time (no changes) | < 1s | 0.4s |
| Total static-site size (300 sessions) | < 50 MB | 24 MB |
| Per-session HTML page | < 500 KB | avg 50 KB |
| CSS + JS bundle | < 100 KB | 12 KB |

If any metric exceeds its budget, the offending change is blocked or must be preceded by a measurement + optimisation PR.

### Privacy-First rules (cross-cutting)

1. **Redaction is on by default.** Username, API keys, tokens, and emails are redacted at the converter layer, before anything hits `raw/`.
2. **No telemetry, ever.** Not even anonymised "which adapter is used". The tool never calls home.
3. **Binding default is `127.0.0.1`.** LAN or public binding requires an explicit `--host 0.0.0.0`.
4. **No cloud features.** No auth, no accounts, no sync. Everything is local.
5. **Config never stores secrets.** The config file only stores regex patterns and truncation limits.
6. **CI must pass `grep -r "pratiyush1" site/` with zero hits** on any build produced from fixtures.

### Schema-Versioning rules (cross-cutting)

1. Every adapter declares `SUPPORTED_SCHEMA_VERSIONS: list[str]`.
2. When an adapter sees a session from an unlisted version, it logs DEBUG and continues (graceful degradation).
3. Test fixtures are committed per-version — `tests/fixtures/claude_code/v2.1/*.jsonl`.
4. Major agent version bumps get their own adapter file (never a monolithic if/elif chain).

---

## Phase 5 — Contribution Setup

Same as parent plus one addition: **adapter contribution flow** (Phase 5.25).

### PR rules (reiterated from parent)

- git config user.name: `Pratiyush`
- git config user.email: `pratiyush1@gmail.com`
- No AI co-authored-by lines
- One PR per concern
- Small commits (one file group per commit)

### Library-style two-workflow CI

From parent framework. For llmwiki:

- **`ci.yml`** — lint + build smoke test on push + PR to `master`. Never publishes.
- **`pages.yml`** — deploys the self-demo site (see Phase 6.5) on tag push.

---

## Phase 5.25 — Adapter Contribution Flow (NEW)

An extensible agent tool needs a predictable way for community contributors to add support for a new agent.

### Contract

To add a new agent adapter, a PR must include:

1. **One file under `llmwiki/adapters/<agent>.py`** that:
   - Subclasses `BaseAdapter`
   - Registers itself via `@register("<agent>")`
   - Sets `session_store_path` to the agent's default location(s)
   - Declares `SUPPORTED_SCHEMA_VERSIONS`
   - Overrides `derive_project_slug()` if needed

2. **At least one fixture** under `tests/fixtures/<agent>/minimal.jsonl` (synthetic or heavily redacted).

3. **One snapshot test** under `tests/snapshots/<agent>/minimal.md`.

4. **One test** under `tests/test_<agent>_adapter.py` that loads the fixture, runs the converter, and diffs against the snapshot.

5. **One documentation page** at `docs/adapters/<agent>.md` explaining:
   - What session store path the adapter reads
   - How to verify the adapter sees sessions (`python3 -m llmwiki adapters`)
   - Known format quirks

6. **A CHANGELOG entry** under `## [Unreleased]`.

7. **One line in `README.md`** under "Works with".

### Review checklist

- [ ] Adapter declares `SUPPORTED_SCHEMA_VERSIONS`
- [ ] Fixture file is under 50 KB and contains no real PII
- [ ] Snapshot test passes locally
- [ ] `docs/adapters/<agent>.md` exists and is linked from README
- [ ] Graceful degradation: unknown record types are skipped, not crashed on
- [ ] No new runtime deps introduced

### Gate to Phase 5.5

Adapter-flow is met when the checklist above is automatable (a GitHub Actions workflow enforces it on every PR touching `llmwiki/adapters/**`).

---

## Phase 5.5 — Pre-Launch QA

Same as parent. For llmwiki specifically:

- [ ] Run `./setup.sh` on a pristine git clone
- [ ] Run `./sync.sh && ./build.sh && ./serve.sh`
- [ ] Visit http://127.0.0.1:8765/ and click through 5 random session pages
- [ ] Cmd+K opens the command palette
- [ ] `/` focuses the search bar
- [ ] Dark mode toggle works and persists
- [ ] Copy-code button works on a code block
- [ ] Copy-as-markdown button works on a session page
- [ ] `grep -r pratiyush1 site/` returns zero hits (privacy check)
- [ ] All links in README return HTTP 200
- [ ] `python3 -m llmwiki --version` prints the version
- [ ] `python3 -m llmwiki adapters` lists claude_code as available

---

## Phase 6 — Launch

Same as parent:

1. `git init`
2. Atomic commits per file group (README separate from code, tests separate from adapters, etc.)
3. `gh repo create Pratiyush/llmwiki --public`
4. `git push -u origin master`
5. `git tag v0.1.0 && git push origin v0.1.0`
6. Create GitHub Release (mark as pre-release for 0.x)

---
