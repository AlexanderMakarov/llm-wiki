# Agnix first run — verdicts (#280)

**Tool:** [agnix](https://github.com/agent-sh/agnix) **0.56.5**  
**After:** `.agnix.toml` waivers + skill frontmatter fixes + inner CI glob that skips `commands/awos/`

## Maintainer review of the first-run findings

Markdown links in skills are **not** a first-run error class here (no REF-002). Workspace-relative paths in prose (`docs/maintainers/…`) are meant to be opened from the **repo root** (where the agent is started), not resolved as filesystem links from `SKILL.md`. Agnix import rules that assume file-relative `@` paths do **not** match how we write AWOS wrappers.

| Finding | Valid bug? | What we did |
|---|---|---|
| **XML-001** on `Usage: /wiki-ingest <path>` (and query/update) | **No.** Angle-bracket placeholders are CLI convention, not XML. Applying XML-001 would force us to rewrite Usage lines that agents and humans already understand. | Disabled **XML-001** in `.agnix.toml`. XML-002/003 stay on for real mismatched tags. |
| **REF-001** on `.claude/commands/awos/*.md` `@.awos/commands/…` | **No.** Wrappers are valid AWOS Layer A imports from **repo root**. Agnix resolves them relative to the wrapper file, so it looks for `.claude/commands/awos/.awos/…`, which does not exist. `/awos:*` works. Do not rewrite imports. | Inner CI/docs **do not pass** `.claude/commands/` as a directory; they lint `.claude/commands/*.md` only. Agnix 0.56.5 `[files].exclude` is not honored for an explicit parent path, so the glob is the real guard. |
| **XP-003** hard-coded `.claude/` (implement-feature worktree recipe, `/release` skill path, etc.) | **No.** Intentional. AWOS Layer A is Claude-specific; Cursor is a generated bridge (`scripts/sync-awos-cursor-commands.sh`). Changing `.claude/` commands that Cursor must see still needs that sync. | Disabled **XP-003**. |
| **CC-SK-006** `release` skill dangerous name | **Yes.** Claude Code requires `disable-model-invocation: true` so the model does not auto-invoke `/release`. | **Fixed** in `.claude/skills/release/SKILL.md`. |
| **CC-SK-012** `gha-diagnosis` `argument-hint` without `$ARGUMENTS` | **Yes** as a Claude Code skill contract. | **Fixed** — body now uses `$ARGUMENTS`. |
| **CC-SK-017** unknown `version` on `modern-python-development` | **Yes** as unknown frontmatter (not a Claude Code skill field). | **Fixed** — removed `version`. |
| **VER-001** no `[tool_versions]` | Noise. Pin is `AGNIX_VERSION` in CI + AGNIX.md. | Disabled **VER-001**. |

## Commands (green after fixes)

```bash
npx --yes agnix@0.56.5 --format text validate llmwiki/agent_kit
npx --yes agnix@0.56.5 --format text validate .claude/skills .claude/agents .claude/commands/*.md
```

Both: **No issues found** (2026-10-06, this worktree).
