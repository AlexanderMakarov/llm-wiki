# Maintainer guide

This directory is the governance scaffold for llmwiki maintainers.
Contributors should read [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md)
first — it has the short version of what this folder covers in detail.

## Docs at a glance

| File | What it's for |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | One-page system diagram + layer boundaries + what NOT to add |
| [`AWOS-CURSOR.md`](AWOS-CURSOR.md) | Cursor-compatible AWOS install (Layers A–C, recruitment MCP, companion plugins) |
| [`AGENT-WORKFLOW-ALTERNATIVES.md`](AGENT-WORKFLOW-ALTERNATIVES.md) | Cursor-ready SDD alternatives vs AWOS — #114 pitfalls, features, learning curve |
| [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md) | Canonical code-review criteria — apply to every incoming PR |
| [`RELEASE_PROCESS.md`](RELEASE_PROCESS.md) | Version bump → CHANGELOG → tag → `release.yml` checklist (canonical order; cut via `/release` skill) |
| [`TRIAGE.md`](TRIAGE.md) | Label taxonomy + triage rules + stale-issue policy |
| [`DECLINED.md`](DECLINED.md) | Graveyard of declined ideas with dates + reasons |
| [`../../context/product/roadmap.md`](../../context/product/roadmap.md) | The roadmap — phases, what is next, and which issue delivers each item |
| [`REFRESH_DEMO.md`](REFRESH_DEMO.md) | Local command that incrementally regenerates `demo/` from git-detected `docs/` changes — needs a working copy and a synth backend; never runs in CI |
| [`surfaces/`](surfaces/README.md) | Per-page behavioural specs for the built site — scan the relevant `Must` lines when reviewing a UI PR |

## Slash commands

Maintainer ops use slash wrappers plus skills under `.claude/`:

- `/triage-issue <issue-number>` — applies `TRIAGE.md` label taxonomy to a new issue
- `/release <version>` — thin wrapper that loads [`.claude/skills/release/SKILL.md`](../../.claude/skills/release/SKILL.md) and follows [`RELEASE_PROCESS.md`](RELEASE_PROCESS.md) (Claude: `.claude/commands/release.md`; Cursor: `.cursor/commands/release.md`)
- `/maintainer` — meta-skill that loads every doc in this folder and surfaces triage / release next actions

Code review uses `REVIEW_CHECKLIST.md` directly (or via the single independent review stage inside `/implement-feature` / `/fix-bug`, where the coding agent picks its own most suitable review skill or command).

See `.claude/commands/` (and `.cursor/commands/` for Cursor-facing wrappers) in the repo root for the source of each command.

## When things go wrong

- **CI red on `main`** → fix-first, roll forward, never force-push
- **Security issue reported** → see `SECURITY.md` in the repo root
- **Contributor PR stuck > 7 days** → escalate via the triage pass
  (there's a rule in `TRIAGE.md`)
- **Someone re-proposes a declined idea** → link them to the
  entry in `DECLINED.md`

## Why a dedicated maintainer folder?

Because maintainer docs have a different audience than user docs.
User docs go in `docs/` (rendered on the site). Maintainer docs
stay here — they're less polished, more operational, and they
change with the team rather than with releases.

Keep this folder short. When a doc is over one screen, prune.
