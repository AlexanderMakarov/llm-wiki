---
description: Hires specialist agents — finds, installs skills, MCPs, and agents from registry, generates agent files.
---

# /awos-hire (Cursor)

Follow `.awos/commands/hire.md` as the source of truth (do not edit that file — the AWOS installer overwrites it).

Apply the tool mapping in `.cursor/rules/awos-cursor-runtime.mdc`.

**Multiple-choice interaction (strict):** when the AWOS prompt says `AskUserQuestion`, call native `AskQuestion` if it is already listed as a first-class tool this turn (invoke by name). Do **not** `CallDynamicTool` with `namespace: cursor` and `toolName: AskQuestion` — that tool is not in the cursor namespace. Use prose numbered choices **only** if native `AskQuestion` is missing. Never call `AskUserQuestion` (Claude-only name).

Recruitment specifics for this repo:

- Call the `awos-recruitment` MCP tool `search_capabilities` (not a tool named `search`).
- Prefer `bunx` for installs; fall back to `npx` only if `bun`/`bunx` is unavailable:

```text
bunx @provectusinc/awos-recruitment skill <names...>
bunx @provectusinc/awos-recruitment agent <names...>
bunx @provectusinc/awos-recruitment mcp <names...>
```

Hired skills/agents land under `.claude/skills/` and `.claude/agents/` — Cursor already reads those trees.
Optional user hint (if provided after the slash command): treat it as `$ARGUMENTS` / the `<user_prompt>` in that command file.
