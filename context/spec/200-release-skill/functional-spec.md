# Functional Specification: Cross-agent release skill

- **Roadmap Item:** [#209](https://github.com/AlexanderMakarov/llm-wiki/issues/209) — feat: cross-agent `/release` skill for cutting tagged releases
- **Status:** Approved
- **Author:** Aleksandr Makarov

---

## 1. Overview and Rationale (The "Why")

Maintainers cut tagged product releases with an AI coding agent. Today the written release checklist is incomplete or wrong in places (wrong default branch name, always mark the release as pre-release, invent a second “create release” step that the automation already does). The Claude-only slash walkthrough was skipped for the last two real cuts; agents improvised in chat and repeated the same footguns (local leftover wiki folder failing tests; changelog acceptance tests breaking when Unreleased is emptied).

**Desired outcome:** one shared release skill that any supported coding agent can load, that walks a correct checklist, keeps editorial judgment with the agent and a human gate before publishing, and matches how releases actually ship after the tag is pushed.

**Success:** the next release cut is driven by invoking this skill (or its `/release` wrapper), not by reinventing the checklist in freeform chat; maintainer docs no longer contradict the automation.

---

## 2. Functional Requirements (The "What")

### FR1 — One cross-agent skill

- **As a** maintainer using Claude Code, Cursor, Codex, or a similar agent, **I want** one release skill written in plain agent instructions, **so that** every agent follows the same cut process.
  - **Acceptance Criteria:**
    - [ ] A skill named for release cutting exists in the contributor/maintainer agent surface (not only as a Claude slash file).
    - [ ] Claude and Cursor can invoke it as `/release` (or documented equivalent); Codex (and peers that read repo agent docs) are told where the skill lives.
    - [ ] The skill is not part of the end-user `install-agent-kit` wiki command pack (maintainer-only).

### FR2 — Half-scripted walkthrough with human publish gate

- **As a** maintainer, **I want** the skill to walk preflight → version bump → changelog/upgrade-guide editorial → commit/tag → wait for my OK → push → watch automation, **so that** releases stay deliberate.
  - **Acceptance Criteria:**
    - [ ] Preflight covers: default branch green, no critical-priority open bugs, local tests and lint, build when relevant, and a warning if a leftover root `wiki/` folder would fail demo self-containment checks.
    - [ ] The agent proposes the version and Theme line; the human can correct them before the cut commit.
    - [ ] Push of the branch tip and version tag does not happen until the human explicitly approves in the session.
    - [ ] After push, the skill waits on the release automation and reports the public release URL (or failure).

### FR3 — Agent owns editorial release notes

- **As a** maintainer, **I want** the agent to move Unreleased notes into the new version section, refresh the upgrade guide headings, and keep older shipping notes discoverable for acceptance checks, **so that** readers get a coherent release and CI stays green.
  - **Acceptance Criteria:**
    - [ ] Skill instructs promoting Unreleased → dated version section with Theme; empty Unreleased scaffold remains.
    - [ ] Skill instructs updating upgrade-guide Unreleased headings to the new version (or equivalent compaction the agent judges needed).
    - [ ] Skill calls out that emptying Unreleased must not break tests that look for older shipping bullets (use the existing changelog helper behavior).
    - [ ] The skill **scripts** the cut: numbered steps the agent runs with existing tools (`gh`, `ruff`, `pytest`, `git`, file edits) — not freeform improvisation.
    - [ ] No separate `scripts/release-*.sh` helpers in this change (the skill is the scripted flow; bash wrappers stay out of scope unless decided later).

### FR4 — Docs match reality

- **As a** maintainer reading the release process doc, **I want** instructions that match the default branch and post-tag automation, **so that** I am not told to push `master`, always pre-release, or create the GitHub Release twice.
  - **Acceptance Criteria:**
    - [ ] Release process doc and skill say the default branch is `main`.
    - [ ] Post-tag: trust the release workflow for GitHub Release + signing; optional PyPI when publishing is enabled; no blanket always-prerelease after 1.0.
    - [ ] Claude slash `/release` (if kept) is a thin wrapper that loads the skill / process — not a second divergent checklist.
    - [ ] Maintainer README and slash-command reference describe the skill accurately.
    - [ ] CHANGELOG Unreleased notes the addition.

### FR5 — Lessons from recent cuts

- **As a** maintainer, **I want** the skill to name known pitfalls from v2.0.0 and v2.1.0, **so that** the next cut does not rediscover them.
  - **Acceptance Criteria:**
    - [ ] Root leftover `wiki/` called out.
    - [ ] Changelog shipping-notes helper / acceptance fallout called out.
    - [ ] Watch CI on the release commit and the tag’s release workflow.
    - [ ] Direct push to `main` for the release commit is acknowledged as the maintainer path (with human approval), distinct from normal PR flow.

---

## 3. Scope and Boundaries

### In-Scope

- Contributor/maintainer cross-agent release skill + thin agent wrappers/docs
- Correcting `RELEASE_PROCESS.md` and related maintainer/slash reference text
- CHANGELOG Unreleased entry
- Tests or docs-currency checks needed for packaging parity with other maintainer skills/commands

### Out-of-Scope

- Fully unattended releases (no human approve before push/tag)
- Invoking release from `/implement-feature` packaging stage (boundary lives in specs / delivery flow — not as a line in the skill checklist)
- Enabling PyPI publishing itself
- Separate `scripts/release-*.sh` helpers (this change scripts the flow via the skill; bash wrappers are a later decision if wanted)
- End-user agent-kit packaging of `/wiki-*` commands
