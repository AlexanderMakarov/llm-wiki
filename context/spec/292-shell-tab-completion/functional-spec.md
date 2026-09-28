# Functional Specification: Shell TAB Completion for llmwiki Commands

- **Roadmap Item:** GitHub Issue #294 — shell TAB completion for llmwiki subcommands
- **Status:** Approved
- **Author:** Alexander Makarov

---

## 1. Overview and Rationale (The "Why")

llmwiki has more than two dozen commands (sync, synth, build, candidates, migrate, install-agent-kit, …). Today, typing `llmwiki ` and pressing TAB suggests nothing, so users have to remember exact command names or stop and read the help text. That slows down everyday use and invites typos.

**Desired outcome:** pressing TAB after `llmwiki ` shows every command immediately, the way it does for `git` or `docker`. A typed prefix narrows the list. Completion must feel instant and add no noticeable delay to opening a new terminal.

**Success:** after running setup and opening a new terminal, a user completes any command with TAB and never has to look up a command name.

---

## 2. Functional Requirements (The "What")

**FR1 — Complete command names.** In bash and zsh, pressing TAB after `llmwiki ` lists every top-level llmwiki command.

- **Acceptance Criteria:**
  - [ ] Given completion is enabled, when the user types `llmwiki ` and presses TAB (twice in bash), then every llmwiki command is listed.
  - [ ] Given completion is enabled, when the user types `llmwiki sy` and presses TAB, then only `sync` and `synth` are offered.
  - [ ] Given completion is enabled, when the user types `llmwiki bui` and presses TAB, then the line becomes `llmwiki build `.
  - [ ] Given completion is enabled, when the user presses TAB after a command name (e.g. `llmwiki sync `), then no llmwiki command names are offered.
  - [ ] Pressing TAB shows suggestions with no perceptible delay.

**FR2 — Manual enablement from the docs.** The documentation gives one line to paste into the shell startup file (`~/.bashrc` for bash, `~/.zshrc` for zsh). This covers users who installed without the setup script.

- **Acceptance Criteria:**
  - [ ] Given a user pastes the documented line into their startup file, when they open a new terminal, then FR1's behavior works.
  - [ ] The documented line lists exactly the commands llmwiki currently offers. If a command is added or removed without updating the docs, an automated check fails.

**FR3 — Setup offers to enable completion.** When run in an interactive terminal, setup asks `Add llmwiki TAB completion to <file>? [Y/n]`. Enter or `y` means yes.

- **Acceptance Criteria:**
  - [ ] Given the default shell is bash, when the user answers yes, then `~/.bashrc` gains the completion line and setup prints which file it changed.
  - [ ] Given the default shell is zsh, when the user answers yes, then `~/.zshrc` gains the completion line and setup prints which file it changed.
  - [ ] When the user answers `n`, no startup file is changed.
  - [ ] Given setup runs non-interactively (CI, piped input) or with the documented skip setting, then no question is asked and no startup file is changed.
  - [ ] Given the default shell is neither bash nor zsh, then setup changes no file and prints the documented line for the user to add themselves.
  - [ ] Given the startup file does not exist yet, when the user answers yes, then setup creates it containing the completion line.

**FR4 — Re-running setup never duplicates, and refreshes.**

- **Acceptance Criteria:**
  - [ ] Given the completion line is already present, when setup runs again and the user answers yes, then the file still has exactly one llmwiki completion line.
  - [ ] Given a newer llmwiki version has added a command, when setup runs again and the user answers yes, then the existing line is updated to the current command list. After a new terminal, the new command completes.
  - [ ] Everything else in the startup file is left exactly as it was.

**FR5 — Documentation and release notes.**

- **Acceptance Criteria:**
  - [ ] The docs describe how to enable completion manually (bash and zsh), what setup does, and how to skip setup's question.
  - [ ] The changelog's unreleased section mentions the feature.

---

## 3. Scope and Boundaries

### In-Scope

- TAB completion of top-level command names in bash and zsh.
- A documented one-line manual setup.
- An optional setup-script step that adds the line and refreshes it on re-run.
- An automated check that keeps the listed commands matching the real commands.

### Out-of-Scope

- Completing options/flags (e.g. `--vault`) or option values.
- Completing names nested under a command (e.g. migration names after `llmwiki migrate`).
- Completing wiki content (page names, candidates, sources).
- fish, PowerShell, Windows cmd, and any other shell.
- A command that prints or generates completion scripts, and any separate completion script file.
- Completion for the `llm-wiki-add` shortcut.
- Package-manager installs (pip, Homebrew) setting up completion automatically. Those users follow the documented manual line.
- Removing the completion line (uninstall).
