---
description: Breaks the Tech Spec into a task list for engineers.
---

# /awos-tasks (Cursor)

Follow `.awos/commands/tasks.md` as the source of truth (do not edit that file — the AWOS installer overwrites it).

Apply the tool mapping in `.cursor/rules/awos-cursor-runtime.mdc`.

**Multiple-choice interaction (strict):** when the AWOS prompt says `AskUserQuestion`, call native `AskQuestion` if it is already listed as a first-class tool this turn (invoke by name). Do **not** `CallDynamicTool` with `namespace: cursor` and `toolName: AskQuestion` — that tool is not in the cursor namespace. Use prose numbered choices **only** if native `AskQuestion` is missing. Never call `AskUserQuestion` (Claude-only name).

Optional user hint (if provided after the slash command): treat it as `$ARGUMENTS` / the `<user_prompt>` in that command file.
