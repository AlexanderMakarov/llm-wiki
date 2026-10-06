# AI tooling lint

CI and local checks validate **shipped agent kit** (`llmwiki/agent_kit`) and **inner maintainer agent markdown** (skills, agents, commands including nested AWOS wrappers). The engine can change; the job is linting AI tooling, not a vendor name.

Current engine: [agnix](https://github.com/agent-sh/agnix) **0.56.6** (dev/CI only — not a Python runtime dependency). Pin lives in `.github/workflows/pr-lint.yml` as `AGNIX_VERSION` and here. Bump both when upgrading. CI still fetches that exact version from npm at job time (`npx --yes`); there is no repo `package-lock.json` for this tool.

Requires Node.js (for `npx`). No repo `package.json` is required.

## Local commands (scoped — same as CI)

From the repository root:

```bash
# Shipped user agent kit (packaged by install-agent-kit)
npx --yes agnix@0.56.6 --format text validate llmwiki/agent_kit

# Inner maintainer surfaces (skills, agents, commands including commands/awos/)
npx --yes agnix@0.56.6 --format text validate .claude/skills .claude/agents .claude/commands
```

GitHub Actions annotation output (matches CI):

```bash
npx --yes agnix@0.56.6 --format github validate llmwiki/agent_kit
npx --yes agnix@0.56.6 --format github validate .claude/skills .claude/agents .claude/commands
```

Machine-readable summary:

```bash
npx --yes agnix@0.56.6 --format json validate llmwiki/agent_kit
```

Explain a rule:

```bash
npx --yes agnix@0.56.6 explain XML-001
```

## What we do not scan

Full-repo `agnix .` (demo vault, `wiki/`, `raw/`, etc.) is intentionally **out of scope** — too noisy and not agent-kit surfaces.

## First-run triage (#280)

Verdicts and waivers: [`context/spec/280-shrink-test-suite/agnix-first-run.md`](../../context/spec/280-shrink-test-suite/agnix-first-run.md). Config: [`.agnix.toml`](../../.agnix.toml). After those, scoped validate (kit + inner `.claude/` trees) is expected **green**. Agnix **0.56.6** fixes project-root `@` imports for nested wrappers ([agent-sh/agnix#1629](https://github.com/agent-sh/agnix/issues/1629)), so `.claude/commands` is validated as a directory (including `commands/awos/`).
