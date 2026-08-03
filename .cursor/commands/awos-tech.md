---
description: Creates the Technical Spec — how the feature will be built.
---

# /awos-tech (Cursor)

Follow `.awos/commands/tech.md` as the source of truth (do not edit that file — the AWOS installer overwrites it).

Apply the tool mapping in `.cursor/rules/awos-cursor-runtime.mdc`.

**Multiple-choice interaction (strict):** when the AWOS prompt says `AskUserQuestion`, call Cursor's `AskQuestion` tool if it is in your tool list for this turn. Do **not** start with a numbered list in chat while `AskQuestion` is available. Use prose numbered choices **only** if `AskQuestion` is missing from your tools. Never call `AskUserQuestion` (Claude-only name).

Optional user hint (if provided after the slash command): treat it as `$ARGUMENTS` / the `<user_prompt>` in that command file.
