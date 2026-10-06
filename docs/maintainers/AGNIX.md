# Agnix — agent config lint

[agnix](https://github.com/agent-sh/agnix) validates Skills, slash commands, hooks, and related agent markdown. It is **dev/CI only** — not a Python runtime dependency.

## Pinned version

CI and local runs use **`agnix@0.56.5`** (see `.github/workflows/agnix.yml` `AGNIX_VERSION`). Bump the pin in the workflow and this doc together when upgrading.

Requires Node.js (for `npx`). No repo `package.json` is required.

## Local commands (scoped — same as CI)

From the repository root:

```bash
# Shipped user agent kit (packaged by install-agent-kit)
npx --yes agnix@0.56.5 --format text validate llmwiki/agent_kit

# Inner maintainer surfaces (skills, agents, top-level commands).
# Do not pass `.claude/commands` as a directory: `commands/awos/` wrappers
# `@`-import repo-root `.awos/` and agnix REF-001 false-positives on them.
# Agnix 0.56.5 `[files].exclude` is not honored for an explicit parent path.
npx --yes agnix@0.56.5 --format text validate .claude/skills .claude/agents .claude/commands/*.md
```

GitHub Actions annotation output (matches CI):

```bash
npx --yes agnix@0.56.5 --format github validate llmwiki/agent_kit
npx --yes agnix@0.56.5 --format github validate .claude/skills .claude/agents .claude/commands/*.md
```

Machine-readable summary:

```bash
npx --yes agnix@0.56.5 --format json validate llmwiki/agent_kit
```

Explain a rule:

```bash
npx --yes agnix@0.56.5 explain XML-001
```

## What we do not scan

Full-repo `agnix .` (demo vault, `wiki/`, `raw/`, etc.) is intentionally **out of scope** — too noisy and not agent-kit surfaces.

Optional: `agent-sh/agnix@v0.56.5` composite action (`agnix-ci`) with `version: "0.56.5"` and `path:` — equivalent to the `npx` steps above.

## First-run triage (#280)

Verdicts and waivers: [`context/spec/280-shrink-test-suite/agnix-first-run.md`](../../context/spec/280-shrink-test-suite/agnix-first-run.md). Config: [`.agnix.toml`](../../.agnix.toml). After those, scoped validate (kit + inner glob, no `commands/awos/`) is expected **green**.
