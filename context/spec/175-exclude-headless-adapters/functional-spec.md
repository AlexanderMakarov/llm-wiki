# Functional Specification: Skip automated sessions from every coding-agent source

- **Roadmap Item:** GitHub [#180](https://github.com/AlexanderMakarov/llm-wiki/issues/180) — extend the “skip automated sessions” filter beyond Claude Code
- **Status:** Approved
- **Author:** Aleksandr Makarov
- **Related (out of this change):** [#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2) Cursor IDE ingest; [#182](https://github.com/AlexanderMakarov/llm-wiki/issues/182) config/install enablement for every shipped source

---

## 1. Overview and Rationale (The "Why")

Summarizing the wiki can itself launch a non-interactive agent run. If that run is treated like a normal chat, it gets collected and summarized again — cost and noise. That loop is already blocked for Claude Code’s automated launches. The same class of “no human at the keyboard” runs from other coding agents (especially Cursor Agent CLI, and other CLIs we already parse) still look like ordinary sessions.

Interactive chats stay valuable: outcomes of automation often reappear inside a human session; that human session is what should be summarized, not the silent automation itself.

**Desired outcome.** Under the default “skip automated sessions” setting, every **working** coding-agent source either skips non-interactive launches the way Claude already does, or documents a clear special rule (OpenClaw: interactive except background modes like dreaming). The built docs state which agents can supply sessions today, what “automated” means per source, and stop claiming Codex is a future stub.

**Success.** Default sync and cost-estimate drop the same automated set; Cursor Agent CLI automation is covered; ordinary OpenClaw chats stay; docs match product reality for the sources this change touches.

---

## 2. Functional Requirements (The "What")

### R1 — Same skip policy for every working coding-agent CLI

- **As a** user with the default skip-automated setting on, **I want** automated launches from Claude Code, Cursor Agent CLI, Codex CLI, and other working coding CLIs treated the same, **so that** synthesis cannot feed on its own silent runs.

**In scope for this behavior (working session sources today):** Claude Code, Codex CLI, Cursor Agent CLI, OpenClaw (with R3), OpenCode, Copilot CLI, Copilot Chat, ChatGPT export (N/A for automation — R4), Gemini CLI and Cursor IDE only as “document / N/A until they can detect launches” (scaffold — see boundaries).

- **Acceptance Criteria:**
  - [ ] Given an interactive chat from a working coding-agent source, when I sync and when I estimate synthesis cost, then that chat stays eligible.
  - [ ] Given a clearly non-interactive / scripted / agent-CLI launch from Claude Code, Cursor Agent CLI, Codex CLI, OpenCode, or Copilot CLI (when the store exposes enough evidence), when I sync with the default setting, then the session is not collected; when I estimate synthesis cost, then it is not counted as pending.
  - [ ] Given the skip-automated setting is turned off, when I sync and estimate, then those automated launches are included.
  - [ ] Given an older collected session with no launch marker, when I estimate or synthesize, then it stays eligible (no silent reclassification); re-sync is required to classify it.

### R2 — Cursor Agent CLI only (not Cursor IDE)

- **As a** Cursor user, **I want** interactive IDE chats kept (once IDE ingest exists) and only non-interactive Agent CLI runs skipped today, **so that** human work stays in the wiki while silent automation does not.

- **Acceptance Criteria:**
  - [ ] Given a non-interactive Cursor Agent CLI run, when I sync with the default setting, then it is skipped; the estimate omits it the same way.
  - [ ] This change does not claim to fix Cursor IDE `state.vscdb` ingest — that remains [#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2).
  - [ ] Docs distinguish Cursor Agent CLI (works) from Cursor IDE (not ingested yet).

### R3 — OpenClaw: interactive by default; skip dreaming-alike background modes

- **As an** OpenClaw user, **I want** ordinary gateway chats kept and only identifiable background modes (e.g. dreaming) skipped, **so that** real conversations still become wiki knowledge.

- **Acceptance Criteria:**
  - [ ] Given a normal interactive OpenClaw session, when I sync with the default setting, then it is collected and stays eligible.
  - [ ] Given an OpenClaw background mode such as dreaming (when the store can identify it), when I sync with the default setting, then it is skipped like other automated runs.
  - [ ] Docs state this OpenClaw rule next to the other sources.

### R4 — Sources with no automation launch to detect

- **As a** reader of the docs, **I want** note/export sources called out as “this filter does not apply,” **so that** I do not expect Claude-style skipping there.

- **Acceptance Criteria:**
  - [ ] Obsidian (hand-written notes intake — not agent chats) and ChatGPT export are documented as not applicable for automated-launch detection, with a test that locks that claim.
  - [ ] Scaffold sources that cannot yet detect launches (Cursor IDE, Gemini CLI as of today) are documented as N/A / not yet, not silently reclassified.

### R5 — Sync feedback stays the current style

- **As a** user running sync, **I want** the existing headless-skip summary behavior, **so that** the command output stays familiar.

- **Acceptance Criteria:**
  - [ ] When automated sessions are skipped under the default setting, sync reports them the same way it already reports Claude headless skips (count in the filter summary), without requiring a new per-agent breakdown line.

### R6 — Docs: support map + per-source “automated” meaning + fix stale claims

- **As a** user reading the built site docs, **I want** one clear section that lists which agents can supply sessions today, how each is turned on with today’s product (including that some need an explicit adapter choice until [#182](https://github.com/AlexanderMakarov/llm-wiki/issues/182)), and what “automated” means for that agent, **so that** I am not left guessing from “coming in v0.2” text.

- **Acceptance Criteria:**
  - [ ] Configuration / getting-started (and thus built `site/docs/…` after a docs build) include a dedicated “which agents are supported” section matching current behavior for every registered session source.
  - [ ] Stale claims that Codex CLI is only a stub / “will be supported in v0.2” are removed or corrected.
  - [ ] Cursor Agent CLI vs Cursor IDE is explained; IDE gap points at #2.
  - [ ] For each working coding-agent source, docs say what counts as automated, that the default is to skip those, and how to turn the filter off.
  - [ ] OpenClaw’s “interactive except dreaming-alike” rule appears in that section.
  - [ ] Obsidian is described as notes intake (not an agent chat source) and remains outside automated-launch detection.

---

## 3. Scope and Boundaries

### In-Scope

- Detect, mark, and skip automated launches for working coding-agent sources under the existing default filter
- Cursor Agent CLI coverage (highest-priority gap after Claude)
- OpenClaw: keep interactive; skip dreaming / similar when identifiable
- Docs support map + per-source automated meaning; fix outdated Codex wording; clarify Cursor CLI vs IDE
- Tests: interactive kept / automated skipped / filter off / legacy unmarked
- Changelog / upgrade note when previously collected automated rows start being skipped on synthesis after re-sync (legacy unmarked files stay visible until then)

### Out-of-Scope

- Changing the default of the skip-automated setting (stays on)
- Filtering interactive IDE chats
- Changing the separate subagent include/exclude setting
- Implementing Cursor IDE `state.vscdb` parsing ([#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2))
- Making every adapter load on bare sync / install interview for enablement + paths ([#182](https://github.com/AlexanderMakarov/llm-wiki/issues/182)) — docs may describe today’s opt-in surprise, not fix it here
- Inventing automation detection for Obsidian notes or ChatGPT export
- New sync UI or per-agent skip dashboard
- Other roadmap items
