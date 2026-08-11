---
title: "Slash commands reference (part 4/4: Governance / maintainer)"
slug: slash-commands-reference-04
project: slash-commands-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/slash-commands.md"
content_sha256: b914ad5a59ba24c268c483ba5ec07399a0c9cbe9939abfcc4d7a50b7216c9763
---

> Part 4 of 4 of **Slash commands reference** — Governance / maintainer.

## Governance / maintainer

### `/maintainer`

Meta-skill that loads all llmwiki governance docs (`CONTRIBUTING.md`,
`CODE_OF_CONDUCT.md`, `docs/maintainers/*`) and exposes the three
maintainer slash commands below.

Use before doing anything governance-related.

### `/release`

Walk through the llmwiki release process step by step — tag, changelog
cut, GitHub Release note, PyPI publish (via OIDC), Homebrew tap bump,
Docker image push.

### `/triage-issue`

Apply labels + milestone + priority to a new GitHub issue using the
llmwiki triage rules.

**Example:**

```
/triage-issue 280
```

---

## AWOS delivery

Hired via `/awos-hire` (#114). Decisions and stages live under `context/product/` (especially `delivery-flow.md`). Prefer Cursor `/awos-flow` / Claude `/awos:flow` when changing those decisions.

### `/fix-bug`

Drive one bug (GitHub Issue) through diagnosis → scoped fix + regression test → verify → independent review (full write-up printed in chat) → PR. Subagent-heavy; keeps the owning AWOS spec honest when behavior changes.

**Example:**

```
/fix-bug 114
```

### `/implement-feature`

Drive one feature (spec / issue) through implement → test → independent review (full write-up printed in chat) → PR per `context/product/delivery-flow.md`.

**Example:**

```
/implement-feature <spec-or-issue>
```

---

## How the slash commands get installed

The repo ships `.claude/commands/*.md` — Claude Code picks them up
automatically when it opens the repo (no separate install step).

For **Codex CLI / Cursor / Gemini CLI / other agents**, copy the
`.claude/commands/wiki-*.md` files into the corresponding skill
directory for that agent (typically `.codex/skills/` or
`.agents/skills/`) — the file format is portable across agents.

---

## Extending

To add a new slash command:

1. Create `.claude/commands/wiki-<name>.md` with a one-line docstring
   on line 1 (that's the summary Claude Code surfaces).
2. Describe the workflow in prose. Reference existing CLI commands
   rather than embedding shell in the body.
3. Run `/wiki-lint` — the `docs/reference/` guardrail test (see
   `tests/test_docs_structure.py`) will pick up the new command.
4. Document it here; the CI guard requires every `.claude/commands/*.md`
   to have a matching entry.

---

## Related

- **[CLI reference](cli.md)** — the underlying `python3 -m llmwiki …` surface.
- **[UI reference](ui.md)** — every screen on the compiled site, with what's reachable from where.
- **[Tutorial 03 — Use with Claude Code](../tutorials/03-use-with-claude-code.md)** — the minimum daily loop built on these commands.
