# Functional Specification: Configure every shipped session source in one place

- **Roadmap Item:** GitHub [#182](https://github.com/AlexanderMakarov/llm-wiki/issues/182) — make every shipped session source configurable in config and opt-in during install (drop core-vs-contrib sync surprise)
- **Status:** Approved
- **Author:** Aleksandr Makarov
- **Related (out of this change):** [#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2) Cursor IDE ingest; [#180](https://github.com/AlexanderMakarov/llm-wiki/issues/180) headless filter (shipped)

---

## 1. Overview and Rationale (The "Why")

Today, llmwiki ships many session sources (Claude Code, Codex CLI, Cursor Agent CLI, OpenClaw, Copilot, Gemini CLI, ChatGPT export, Obsidian notes, and others), but only two behave as “built in” on a normal sync. The rest are hidden behind a command-line flag that users must discover from docs. That split (“core” vs “contrib”) is a maintainer packaging detail, not something a new user should have to learn.

The product already documents per-source settings under a single configuration section, but listing, status, and default sync do not treat every shipped source the same way. Users who enable OpenClaw or Cursor in their settings still see those sources missing from the adapter list or inactive until they remember the extra flag.

**Desired outcome.** One mental model: every shipped source appears in the adapter roster, can be turned on or off in personal settings, uses sensible default locations when the store exists on disk, and runs on a normal sync when enabled. First-time setup should ask which sources to use and confirm paths (especially for personal notes vaults). User-facing docs describe a single support map — not “core vs contrib.”

**Safety.** Personal notes intake (Obsidian and any other non–coding-agent source) must never turn on silently; the user must explicitly opt in.

**Success.** A user with only personal settings (no special flags) can enable OpenClaw, Cursor Agent CLI, Copilot, and similar sources, see them as active in the adapter list, and have them included on sync. Setup guides a new install through source selection. Docs no longer tell users that some shipped sources are “optional plugins” or “coming in v0.2.”

---

## 2. Functional Requirements (The "What")

### R1 — One settings block per shipped source

- **As a** user, **I want** every session source llmwiki ships to have its own on/off switch and path settings in my personal configuration, **so that** I configure sources in one predictable place instead of memorizing flags.

- **Acceptance Criteria:**
  - [ ] Given I open the configuration reference or my personal settings file, when I look for a shipped source (Claude Code, Codex CLI, Cursor Agent CLI, Cursor IDE, OpenClaw, OpenCode, Copilot Chat, Copilot CLI, Gemini CLI, ChatGPT export, Obsidian), then I find a dedicated block for that source with at least: whether it is enabled, and where it reads from when paths are configurable.
  - [ ] Given I set a source to enabled with valid paths, when I run a normal sync (no source-limiting flags), then that source is included the same way Claude Code is today.
  - [ ] Given I set a source to disabled, when I run a normal sync, then that source is skipped even if its store exists on disk.

### R2 — Normal sync uses every enabled source

- **As a** user with multiple coding agents installed, **I want** a single sync command to pick up every source I have turned on, **so that** I do not run separate commands per agent.

- **Acceptance Criteria:**
  - [ ] Given OpenClaw (or Cursor Agent CLI, Copilot CLI, OpenCode, etc.) is enabled in my settings and its session store is present, when I run sync without limiting flags, then sessions from that source are converted.
  - [ ] Given a coding-agent source is enabled but its store is not present on this machine, when I run sync, then sync completes without error and that source contributes nothing (it is not treated as a failure).
  - [ ] Given I only want one source this run, when I pass an explicit source-limiting flag, then only those named sources run (existing override behavior preserved).
  - [ ] Given the default “auto” behavior for coding-agent sources (no explicit on/off), when their store exists, then they sync automatically — matching today’s Claude/Codex experience extended to all shipped coding-agent sources.

### R3 — Adapter list shows the full shipped roster

- **As a** user diagnosing setup, **I want** the adapter list command to show every shipped source with clear present / enabled / active columns, **so that** I can see at a glance what will run on the next sync.

- **Acceptance Criteria:**
  - [ ] When I run the adapter list command, then every shipped session source appears in the table (not only the two that used to be “core”).
  - [ ] For each row, **present** reflects whether that source’s store is visible on disk; **enabled** reflects my settings (automatic default, explicitly on, or explicitly off); **active** reflects whether the next sync will use it.
  - [ ] The list loads my merged personal settings (shipped defaults plus my overrides), not only the shipped example file.

### R4 — First-time setup interview (`configure-sources`)

- **As a** new user, **I want** an optional interview that turns on the session sources I actually use and confirms paths, **so that** my personal settings are correct before the first sync — regardless of whether I installed from a git clone, pip, or Homebrew.

#### Detection mechanism (how “likely session stores” are found)

Detection is **not** heuristic guessing. For every shipped adapter, llmwiki already knows default store locations (e.g. Claude → `~/.claude/projects/`, Cursor Agent CLI → `~/.cursor/chats/`, OpenClaw → `~/.openclaw/agents/`). The interview:

1. Loads the **full shipped roster** (all in-repo adapters).
2. For each adapter, runs the same **store-presence check** used by the adapter list (`present` column): “does at least one configured/default path exist on disk?”
3. Splits results into **coding-agent sources** (auto-eligible when present) vs **notes/export intake** (Obsidian, ChatGPT export, etc. — never auto-enabled).

No network calls, no parsing session files during detection — directory existence only.

#### Interview flow (interactive terminal only)

New command: **`llmwiki configure-sources`** (callable standalone or from setup).

| Step | What happens |
|------|----------------|
| Probe | Build lists: `detected` (present=yes) and `not_detected` (shipped but absent). |
| Coding-agent prompts | For each item in `detected` with `is_ai_session`, ask `Enable <name> for sync? [Y/n]` (default **yes**). |
| Notes/export prompts | For Obsidian / ChatGPT / other non-session intake, ask separately with label “notes/export intake, not agent chats” — default **no**. |
| Path confirmation | When enabling a source with configurable paths (Obsidian vault, custom OpenClaw roots, etc.), show the detected or default path and let the user edit before saving. |
| Write | Merge choices into gitignored `config.json` under `adapters.<name>` (`enabled`, `roots` / `vault_paths` / adapter-specific keys). |
| Confirm | Re-print the adapter table so `active` reflects saved choices. |

For sources in `not_detected`, offer an optional “enable with custom path?” prompt (default **no**) — advanced users only.

#### When the interview runs (by install path)

| Install path | Interview trigger |
|--------------|-------------------|
| **Git clone + `setup.sh`** | After vault/diagnostics, before optional `install-automation` prompt — only when stdin is a TTY and `LLMWIKI_SKIP_AUTOMATION` is unset (same gate as today’s automation prompt; add `LLMWIKI_SKIP_CONFIGURE_SOURCES=1` to skip). |
| **`pip install` / Homebrew** | No bundled setup script — user runs `llmwiki configure-sources` once after `init`, or edits `config.json` manually. Docs point here explicitly. |
| **`llmwiki install-automation`** | Does **not** replace the source interview; automation wizard stays about schedulers/synth. User may run `configure-sources` before or after. |
| **Non-interactive / CI** | Interview skipped entirely; safe defaults apply (coding-agent sources auto when present; notes intake off). |

- **Acceptance Criteria:**
  - [ ] Given an interactive terminal, when I run `llmwiki configure-sources`, then every shipped adapter is probed via its documented default paths, detected stores are listed, and I am prompted per the table above.
  - [ ] Given I enable OpenClaw (or Cursor Agent CLI, etc.) in the interview, when it finishes, then `config.json` contains `adapters.<name>.enabled: true` and a bare `llmwiki sync` includes that source without `--adapter`.
  - [ ] Given I enable Obsidian in the interview, when prompted, then the UI labels it as notes intake (not agent chat history) and writes `adapters.obsidian.vault_paths` with my confirmed path.
  - [ ] Given non-interactive setup (`LLMWIKI_SKIP_CONFIGURE_SOURCES=1`, non-TTY, or CI), when setup finishes, then no `config.json` adapter writes occur and Obsidian/notes intake stays off.
  - [ ] Given git-clone `setup.sh` on a TTY, when setup completes, then it offers `configure-sources` before the existing `install-automation` prompt.
  - [ ] After the interview, when I run the adapter list, then enabled sources show `active=yes` when their store is present.

### R5 — Obsidian and notes intake stay explicit opt-in

- **As a** user with an Obsidian vault, **I want** notes intake to remain off until I explicitly enable it, **so that** a default sync never ingests my personal notes vault without consent.

- **Acceptance Criteria:**
  - [ ] Given I have not explicitly enabled Obsidian (or other non–coding-agent intake) in settings, when I run a normal sync, then no notes from that intake are collected even if a vault path exists.
  - [ ] Given I explicitly enable Obsidian and provide a vault path, when I sync, then notes intake runs for that vault only.
  - [ ] Setup interview presents Obsidian as opt-in with a clear label that it is notes intake, not agent chat history.

### R6 — Documentation: one support map, no “core vs contrib” for users

- **As a** reader of getting-started and configuration docs, **I want** a single table of shipped sources with how to enable each and default paths, **so that** I am not told to use a special flag for sources that already ship with the product.

- **Acceptance Criteria:**
  - [ ] Getting-started, multi-agent setup, configuration reference, and CLI reference describe the same enablement model (settings + optional per-run source limit), without user-facing “core vs contrib” language.
  - [ ] Stale text that Codex or other sources are stubs or “coming in v0.2” is removed or corrected.
  - [ ] Each shipped source documents default store locations and which settings keys override them.
  - [ ] Obsidian is documented as explicit opt-in notes intake, separate from coding-agent session sources.
  - [ ] Cursor IDE limitations ([#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2)) remain accurately described; this change does not claim IDE ingest is complete.

---

## 3. Scope and Boundaries

### In-Scope

- Unify enablement and path settings under the documented `adapters.<name>` configuration shape for all shipped in-repo sources.
- Load every shipped adapter for listing, status, and default sync selection (not only the former “core” pair).
- Extend setup and/or install-automation with an interactive source-selection and path-confirmation step.
- Fix adapter status/listing to read the same merged config sync uses (including personal `config.json` overrides).
- Update user-facing docs, CHANGELOG, and UPGRADING notes for the behavior change.
- Preserve `--adapter` as a per-run override to limit which sources sync.
- Preserve [#180](https://github.com/AlexanderMakarov/llm-wiki/issues/180) headless-filter behavior for all coding-agent sources.

### Out-of-Scope

- External / out-of-repo plugin adapters ([#182](https://github.com/AlexanderMakarov/llm-wiki/issues/182) non-goal).
- Cursor IDE `state.vscdb` parsing ([#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2)).
- Changing headless-filter semantics ([#180](https://github.com/AlexanderMakarov/llm-wiki/issues/180) — already shipped).
- Reorganizing the internal `adapters/` vs `adapters/contrib/` package layout for maintainers (may stay; users should not see it).
- Auto-ingesting Obsidian or other notes vaults without explicit user enablement.
