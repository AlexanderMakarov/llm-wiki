# Agnix first run — verdicts (#280)

**Tool:** [agnix](https://github.com/agent-sh/agnix) **0.56.6**  
**After:** `.agnix.toml` waivers + skill frontmatter fixes + directory validate of `.claude/commands` (including `commands/awos/`)

## Maintainer review of the first-run findings

Markdown links in skills are **not** a first-run error class here (no REF-002). Workspace-relative paths in prose (`docs/maintainers/…`) are meant to be opened from the **repo root** (where the agent is started), not resolved as filesystem links from `SKILL.md`.

| Finding | Valid bug? | What we did |
|---|---|---|
| **XML-001** on `Usage: /wiki-ingest <path>` (and query/update) | **No.** Angle-bracket placeholders are CLI convention, not XML. Applying XML-001 would force us to rewrite Usage lines that agents and humans already understand. | Disabled **XML-001** in `.agnix.toml`. XML-002/003 stay on for real mismatched tags. |
| **REF-001** on `.claude/commands/awos/*.md` `@.awos/commands/…` | **Was a false positive on 0.56.5** (file-relative join). **Fixed upstream** in agnix **0.56.6** ([agent-sh/agnix#1629](https://github.com/agent-sh/agnix/issues/1629)): workspace root is preserved for nested scans. Wrappers stay `@.awos/…` from repo root. | Validate `.claude/commands` as a **directory** (no top-level-only glob workaround). |
| **XP-003** hard-coded `.claude/` (implement-feature worktree recipe, `/release` skill path, etc.) | **No.** Intentional. AWOS Layer A is Claude-specific; Cursor is a generated bridge (`scripts/sync-awos-cursor-commands.sh`). Changing `.claude/` commands that Cursor must see still needs that sync. | Disabled **XP-003**. |
| **CC-SK-006** `release` skill dangerous name | **Yes.** Claude Code requires `disable-model-invocation: true` so the model does not auto-invoke `/release`. | **Fixed** in `.claude/skills/release/SKILL.md`. |
| **CC-SK-012** `gha-diagnosis` `argument-hint` without `$ARGUMENTS` | **Yes** as a Claude Code skill contract. | **Fixed** — body now uses `$ARGUMENTS`. |
| **CC-SK-017** unknown `version` on `modern-python-development` | **Yes** as unknown frontmatter (not a Claude Code skill field). | **Fixed** — removed `version`. |
| **VER-001** no `[tool_versions]` | Noise. Pin is `AGNIX_VERSION` in CI + AI-LINTING.md. | Disabled **VER-001**. |

## Commands (green after fixes)

```bash
npx --yes agnix@0.56.6 --format text validate llmwiki/agent_kit
npx --yes agnix@0.56.6 --format text validate .claude/skills .claude/agents .claude/commands
```

Both: **No issues found** (2026-10-06, this worktree, agnix 0.56.6).
