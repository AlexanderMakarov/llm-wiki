# Product Definition: llm-wiki

- **Version:** 1.0
- **Status:** Proposed

---

## 1. The Big Picture (The "Why")

### 1.1. Project Vision & Purpose

Turn coding-agent session history into a living, interlinked knowledge base you can query and browse — so past work compounds instead of disappearing into chat logs.

### 1.2. Target Audience

Primary: individual developers and power users who live in Claude Code, Cursor, and similar agents and want their sessions to become durable knowledge. Secondary: small indie teams and open-source maintainers who want a shared wiki from agent work without a heavy PKM setup.

### 1.3. User Personas

- **Persona 1: "Alex the Solo Builder"**
  - **Role:** Ships personal and side projects with coding agents day to day.
  - **Goal:** Recover decisions and context from last month’s chats via a searchable wiki and a local browsable site — not another SaaS notes app.
  - **Frustration:** Valuable agent work vanishes into per-tool chat logs; re-explaining the same context across projects and agents wastes time.

### 1.4. Success Metrics

- Any AI agent on the machine can get a learned knowledge summary from other agents’ sessions across all projects in a couple of seconds.
- There is a visual representation of saved knowledge areas so a human can understand the landscape in a few seconds and then explore in depth.
- Agents automate reliable low-level work (keyword extraction, summarization); humans review agents’ higher-level consolidation into entities and concepts — correcting hallucinations and thin-context mistakes — so both people and LLMs explore faster.

---

## 2. The Product Experience (The "What")

### 2.1. Core Features

- Ingest from agents — sync/convert session history from Claude, Cursor, and similar into immutable raw markdown
- Wiki synthesis — structured wiki pages (sources, entities, concepts, index, overview) from raw sessions
- Cross-project knowledge access — agents and humans query/search the wiki across projects on the machine
- Agent-driven consolidation into entities/concepts, with human review of that higher-level work (promote, merge, discard, correct) — not hand-authoring every page from scratch
- Browsable site / visual overview — static site (and related views) so humans see knowledge areas at a glance and open pages in depth
- Lint, knowledge graph, and reflect — quality checks, link graph, and higher-order reflection as first-class capabilities

### 2.2. User Journey

Daily path is agent-first: work in any supported agent, sync/synth (or continuous ingest) feeds the wiki — agents handle low-level extraction and summarization automatically — and later agents query the shared wiki in seconds when starting related work. In parallel, the both-loops pattern: agents propose higher-level entities and concepts; humans periodically review that consolidation (catching hallucinations and missing context), then browse the visual overview and drill into pages — so curated knowledge benefits both humans and LLMs.

Primary product surfaces for that journey: MCP (for any agent as a *consumer*) and the static site (for humans). Server mode is not part of the main experience.

---

## 3. Project Boundaries

### 3.1. What's In-Scope for this Version

- Core loop: sync/ingest → synth/sources/harvest → candidate review → build site; local CLI; Claude + Cursor as session *sources*; query/search for agents; basic visual browse
- Cross-project / machine-wide wiki access so any agent can read summaries across projects in seconds
- Lint, knowledge graph, and reflect as first-class (not deferred niceties)
- MCP so *any* agent can consume the wiki (consumer ≠ source adapter)
- Consolidate the repo to be user-friendly and intuitive, with hints everywhere for newbies
- Cut out useless features or restore broken ones left from the original fork of https://github.com/Pratiyush/llm-wiki
- Use GitHub issues as the backlog of current bugs and features to prioritize

### 3.2. What's Out-of-Scope (Non-Goals)

- No cloud PKM SaaS — no hosted accounts, no multi-tenant web product, no replacing Obsidian/Notion as a full notes app
- Do not cover every coding agent as a session *source* in this version (too hard); MCP may still serve any agent as a knowledge consumer
- No unsupervised publish of higher-level knowledge — agents already consolidate raw data into entities and concepts, but humans must review that work because agents can hallucinate or lack enough context; low-level work (keyword extraction, summarization) stays fully automated because agents/LLMs are reliable enough there
- No mobile app or third-party productivity-suite deep integrations as requirements
- No “server” mode as a primary deliverable — main outputs are MCP and the static site
