# Functional Specification: Cursor AskQuestion dispatch for AWOS

- **Roadmap Item:** [#114](https://github.com/AlexanderMakarov/llm-wiki/issues/114) (Cursor-compatible AWOS) — harness mapping refinement, not a new product feature
- **Status:** Approved
- **Author:** Alexander Makarov

---

## 1. Overview and Rationale (The "Why")

AWOS prompts tell the agent to call Claude's `AskUserQuestion`. This repo maps that to Cursor's native `AskQuestion` picker ([#114](https://github.com/AlexanderMakarov/llm-wiki/issues/114)). That mapping is still correct: `AskQuestion` is a first-class Cursor tool when the host injects it.

Cursor later split first-party tools into two bags. Some stay first-class (`Read`, `Shell`, and — when present — `AskQuestion`). Others are on-demand under the `cursor` MCP namespace via `GetDynamicTools` / `CallDynamicTool`. That namespace is `CreateGoal`, `GenerateImage`, `UpdateGoal` only. `AskQuestion` was never added there. Some models (Auto, Grok 4.5) also omit native `AskQuestion`. Agents that treat "call `AskQuestion`" as "look it up in the `cursor` namespace" get `Error: Tool "AskQuestion" not found in namespace "cursor"` and skip the picker even on sessions that still have the native tool.

This is contributor-harness behaviour only. llmwiki product runtime is unchanged.

---

## 2. Functional Requirements (The "What")

1. **Native `AskQuestion` when injected.** When an AWOS prompt says `AskUserQuestion` and Cursor has already listed `AskQuestion` as a first-class tool this turn, the agent invokes it by name (same as `Read` / `Shell`) and must not fall back to a numbered list in chat first.
   - **Acceptance Criteria:**
     - [x] `.cursor/rules/awos-cursor-runtime.mdc` and the generated `/awos-*` wrappers say to call native `AskQuestion` when it is already in the first-class tool list.
     - [x] Maintainer doc [`docs/maintainers/AWOS-CURSOR.md`](../../../docs/maintainers/AWOS-CURSOR.md) Runtime mapping table matches that rule.

2. **Never `CallDynamicTool` `cursor`/`AskQuestion`.** The agent must not discover or invoke `AskQuestion` through the `cursor` MCP namespace. An empty `GetDynamicTools` search is not permission to invent that call.
   - **Acceptance Criteria:**
     - [x] The runtime rule names the failure (`Tool "AskQuestion" not found in namespace "cursor"`) and lists the actual `cursor` namespace tools (`CreateGoal`, `GenerateImage`, `UpdateGoal`).
     - [x] Layer A wrappers (`scripts/sync-awos-cursor-commands.sh`) and Layer C banners (`scripts/sync-awos-plugin-cursor.sh`) repeat the ban so slash-command context cannot miss it.

3. **Prose fallback only when native `AskQuestion` is absent.** If the host did not inject the first-class tool this turn, ask with a numbered Markdown list and wait. AWOS skip→default still applies when the user declines. Do not call a tool named `AskUserQuestion`.
   - **Acceptance Criteria:**
     - [x] The runtime rule states the prose fallback and that `AskUserQuestion` does not exist in Cursor.

---

## 3. Out of Scope

- Changing AWOS upstream prompts (they keep saying `AskUserQuestion`).
- Rewriting hired plugin skill bodies with acplugin (acplugin does not rewrite tool names).
- Forcing Auto / Grok sessions to grow a native `AskQuestion` — that is a Cursor host/model gate, not this repo.
