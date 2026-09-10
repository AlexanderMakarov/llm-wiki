# Functional Specification: Session subtitles from assigned names and scored fallback

- **Roadmap Item:** Session list and detail subtitles should prefer the name the user (or agent) already gave the session; otherwise score user prompts and take the best — including maintenance-only sessions
- **Status:** Approved
- **Author:** Alexander Makarov
- **Issue:** [#249](https://github.com/AlexanderMakarov/llm-wiki/issues/249) (merges former #250; addresses symptom [#246](https://github.com/AlexanderMakarov/llm-wiki/issues/246))

---

## 1. Overview and Rationale (The "Why")

Operators browse sessions by a short subtitle under the session title (on the sessions index cards and on the session detail hero). Today that subtitle is often wrong: it can pick a mid-session follow-up line, misuse English-only filters, or ignore the name the user already set in the agent UI (or the agent’s own auto-title).

**Desired outcome.** When a session has an assigned name in its source agent, that name is the subtitle. When it does not, every user prompt is scored (type, then earlier position, then a little length); the highest wins — so a session that only ran a maintenance command can still show that command, and a later real task still beats earlier `/clear` / `/model` / `/theme`-style prompts. Weights are tuned with the operator on real sessions before shipping. No knowledge re-summarization is required to adopt this.

**How we measure success.** Assigned names win when present. Otherwise the top-scoring prompt (truncated to 120 characters) is the subtitle. Maintenance-only sessions are not blank. Operator-accepted eval on real sessions matches the shipped weights.

---

## 2. Functional Requirements (The "What")

### R1 — Prefer the assigned session name as the subtitle

- **As an** operator, **I want** the session subtitle to be the name I (or the agent) already assigned in the coding agent, **so that** the wiki matches what I already named the work.

Rules:

- If the source agent stores a **user-assigned rename**, that becomes the subtitle.
- Else if it stores an **agent auto-title**, that becomes the subtitle.
- That assigned name is shown after the same privacy scrubbing as other session text.
- Turn-based scoring must **not** replace a non-empty assigned name.

- **Acceptance Criteria:**
  - [ ] Given a Claude Code session the user renamed in the UI, when the session is imported, then the sessions index card and session detail hero subtitle show that rename (not a derived conversation line).
  - [ ] Given a Claude Code session with no user rename but with an agent auto-title, when imported, then the subtitle shows that auto-title.
  - [ ] Given a Cursor CLI session that has an assigned chat/session name in its store, when imported, then the subtitle uses that name the same way.
  - [ ] Given an assigned name exists, when import also has noisy early user turns, then the subtitle still stays the assigned name.

### R2 — Score every user prompt; pick the highest (fallback)

- **As an** operator, **I want** a sensible short subtitle even when the agent never named the session, **so that** cards and the hero are still scannable — including sessions whose only action was a maintenance command, without later tiny corrections stealing the subtitle.

Rules (fallback only; skipped when R1 applies):

1. Collect user prompts after **per-agent format cleanup** (each agent turns its own envelopes into readable lines — not a Claude-only global special case).
2. Score in order: **type** → **earlier position** → **length (0..120 only)**.  
   - Type bands: slash-with-**long** args and prose share the high band; slash-with-**short** args are lower (config-like); bare slash is lowest (only if nothing else). Long vs short args = character count of the argument text, not “looks like an issue URL.”  
   - Example: `/fix-bug xxxxx` then `merge with --admin` → subtitle is `/fix-bug xxxxx`.  
   - Example: `/clear` then `/model …` then `/theme …` then a real task sentence → subtitle is the task sentence.  
   - Example: only `/mcp` → subtitle is `/mcp`.
3. Position outweighs length. Length adds only via `min(prompt_length, 120)` — longer than 120 does not score higher than 120.
4. Truncate the displayed winner at **120** characters.
5. No LLM. No English soft-ack / continuation lists. Operator eval on real sessions before freezing weights.

- **Acceptance Criteria:**
  - [ ] Given `/fix-bug …` then later `merge with --admin`, when imported, then the subtitle is `/fix-bug …`.
  - [ ] Given `/clear` → `/model …` → `/theme …` → later task prose, when imported, then the subtitle is the task prose.
  - [ ] Given only `/mcp`, when imported, then the subtitle is `/mcp`.
  - [ ] Given a winner longer than 120 characters, when imported, then display truncates at 120 and length scoring did not prefer “even longer than 120.”
  - [ ] Given Claude Code and Cursor CLI fixtures, when tests run, then assigned-name preference and scored fallback hold.
  - [ ] Given an operator eval on multiple real sessions, when weights/rules are corrected, then shipped weights match what the operator accepted.

### R3 — Adapter inventory and documentation

- **As an** operator reading release notes / docs, **I want** to know which agents contribute assigned names and how subtitles are chosen, **so that** I know when to rename in the agent UI vs when fallback applies.

- **Acceptance Criteria:**
  - [ ] Given the change ships, when the operator reads the changelog / upgrading note, then it states: assigned names win; scored fallback otherwise; optional re-import refreshes old subtitles; **no** full knowledge re-summarization is required.
  - [ ] Given the PR, when reviewing adapter coverage, then each session adapter is listed as “has assigned-name source X” or “no assigned name in store.”

### R4 — No forced wiki re-summarization

- **As an** operator, **I want** adopting this change without re-running summarization over my whole wiki, **so that** subtitle quality does not imply a costly rebuild of knowledge pages.

- **Acceptance Criteria:**
  - [ ] Given the operator upgrades and imports only new sessions, when they browse, then new sessions get the new subtitle rules and old sessions keep prior subtitles until optionally re-imported.
  - [ ] Given docs describe refresh, when the operator follows them, then they are told how to re-import transcripts for subtitle refresh — not to re-summarize the wiki.

---

## 3. Scope and Boundaries

### In-Scope

- Session subtitle on index cards and session detail hero.
- Assigned name first; else scored fallback (type → position → length).
- Delete old English soft-ack / continuation / description chrome-skip heuristics from the description path.
- Truncate at **120**; short prompts remain valid.
- Operator eval on real sessions before freezing weights.
- Claude Code + Cursor CLI; adapter inventory; docs/tests.
- Addressing the #246 symptom via this feature.

### Out-of-Scope

- Changing the synthetic main session title line (`Session: … — date`) unless decided later.
- Mandatory vault-wide forced re-import or any knowledge re-summarization.
- English soft-ack / continuation lists; LLM-based scoring; GitHub-issue special regexes.
- Hard-excluding maintenance slash commands from ever being the subtitle.
- Renaming sessions inside the static site UI.
- Other roadmap items not listed in #249.

---

## 4. Decisions locked

1. **Truncate max:** **120** characters.
2. **Second adapter:** **Cursor CLI**.
3. **Fallback:** score user prompts (type bands → position → length 0..120) → top. Slash+long-args and prose share the high band (so `/fix-bug …` beats later `merge with --admin`); bare slash is last resort; short-arg slashes lose to later high-band prompts.
4. **Format cleanup:** per-adapter `normalize_user_prompt` (Claude XML cleanup is Claude’s override, not convert-global).
5. **Old description heuristics:** remove from the description path.
6. **Weights:** provisional until operator eval; then freeze.
