# Maintainer slash commands

The five commands maintainers and contributors run from this repository's
`.claude/commands/`. Claude Code picks them up automatically when it opens
the repo — there is no install step, and `llmwiki install-agent-kit` does
not ship them.

For the vault pipeline (`/wiki-*`) see
[`../reference/slash-commands.md`](../reference/slash-commands.md).

---

## Governance / maintainer

### `/maintainer`

Meta-skill that loads all llmwiki governance docs (`CONTRIBUTING.md`,
`CODE_OF_CONDUCT.md`, `docs/maintainers/*`) and exposes the three
maintainer slash commands below.

Use before doing anything governance-related.

### `/release`

Maintainer-only. Thin wrapper around [`../../.claude/skills/release/SKILL.md`](../../.claude/skills/release/SKILL.md): preflight on `main`, version bump, CHANGELOG/UPGRADING editorial, local commit+tag, **human gate before push**, then watch `.github/workflows/release.yml` (GitHub Release + Sigstore; PyPI only when `PYPI_PUBLISHING` is enabled). Canonical checklist order: [`RELEASE_PROCESS.md`](RELEASE_PROCESS.md). Usage: `/release <version>`.

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
