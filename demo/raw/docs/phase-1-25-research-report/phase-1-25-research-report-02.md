---
title: "Phase 1.25 — Research Report (part 2/3: Per-repo analysis)"
slug: phase-1-25-research-report-02
project: phase-1-25-research-report
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/research.md"
content_sha256: 38ce338d0adda637c856de5cd5eeab0485842848f83af1b0e5b0ae87c2afff0b
---

> Part 2 of 3 of **Phase 1.25 — Research Report** — Per-repo analysis.

## Per-repo analysis

### Pure-markdown skills

#### [kfchou/wiki-skills](https://github.com/kfchou/wiki-skills)
- **Shape:** Claude Code plugin. 6 markdown files, 0 Python files.
- **Strength:** Minimal, well-scoped. Pure schema + slash commands.
- **Gap:** No static HTML output. No multi-agent support. No session-transcript adapter — input is "any markdown".
- **Lesson:** The "Claude Code plugin" distribution mode is clean — ship as a plugin + a few .md files, zero runtime deps.

#### [Astro-Han/karpathy-llm-wiki](https://github.com/Astro-Han/karpathy-llm-wiki)
- **Shape:** "One skill" marketed as Agent Skills-compatible. 6 markdown, MIT.
- **Strength:** Explicitly targets the Agent Skills ecosystem.
- **Gap:** Same as above — no session-aware ingestion, no HTML rendering.
- **Lesson:** There's a clean "one-skill" positioning angle (minimal cognitive footprint) that resonates.

#### [bashiraziz/llm-wiki-template](https://github.com/bashiraziz/llm-wiki-template)
- **Shape:** Template with 26 markdown files + 3 Python scripts. MIT.
- **Strength:** Template layout is clean and opinionated.
- **Gap:** Template alone — no session transcripts, no HTML, no adapters.
- **Lesson:** A template-first distribution is a lower-effort entry point than a full tool.

### Markdown-first + light Python

#### [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent)
- **Shape:** 11 markdown + 4 Python scripts. MIT.
- **Strength:** The best-documented schema I've read. `/wiki-ingest`, `/wiki-query`, `/wiki-lint`, `/wiki-graph` slash commands. `build_graph.py` generates a vis.js knowledge graph.
- **Gap:** Input is "drop markdown in `raw/`" — no knowledge of session transcripts. No dark mode. No search. No HTML output beyond the graph HTML.
- **Lesson:** This is the closest prior art. llmwiki inherits its directory layout and slash-command naming (`/wiki-*`).

#### [Ss1024sS/LLM-wiki](https://github.com/Ss1024sS/LLM-wiki)
- **Shape:** 25 markdown + 4 Python. Generates 30 files including stale-reporting scripts.
- **Strength:** Explicitly covers the "AI remembers nothing in new sessions" pain point in its README.
- **Gap:** No HTML viewer. No multi-agent.
- **Lesson:** The stale-reporting idea is worth borrowing — llmwiki should ship `/wiki-lint` with "stale pages" detection baked in.

#### [hsuanguo/llm-wiki](https://github.com/hsuanguo/llm-wiki)
- **Shape:** 13 markdown + 9 Python. Has a logo, more polish.
- **Strength:** The most Python-heavy of the markdown-first implementations — suggests the author hit real scale issues.
- **Gap:** Not session-aware.
- **Lesson:** Once you reach ~10 Python files, you're building a CLI. llmwiki leans into that explicitly.

### Obsidian-coupled

#### [AgriciDaniel/claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian)
- **Shape:** 50 markdown files, 0 Python. The wiki itself is real content living in Obsidian.
- **Strength:** Treats Obsidian as a first-class viewer. The `meta/` folder contains a cover GIF — good product presentation.
- **Gap:** 100% Obsidian-locked. If you don't use Obsidian, this is useless.
- **Lesson:** Obsidian is a compelling viewer for many users — llmwiki should ship an Obsidian connector as an **optional** input/output, not the only path.

#### [kytmanov/obsidian-llm-wiki-local](https://github.com/kytmanov/obsidian-llm-wiki-local)
- **Shape:** 2 markdown + 25 Python files. Uses a **local** LLM (no cloud API calls).
- **Strength:** Privacy angle — everything runs locally, no OpenAI/Anthropic API calls.
- **Gap:** Requires running a local model — heavy prerequisite.
- **Lesson:** Privacy-first positioning resonates. llmwiki's no-telemetry + local-only rules align with this.

#### [louiswang524/llm-knowledge-base](https://github.com/louiswang524/llm-knowledge-base)
- **Shape:** 10 markdown + 1 Python. Claude Code + Obsidian.
- **Strength:** Clean coupling between Claude Code (writer) and Obsidian (viewer).
- **Gap:** Assumes Obsidian is installed.
- **Lesson:** "Writer/viewer split" is a useful mental model.

#### [remember-md/remember](https://github.com/remember-md/remember)
- **Shape:** 23 markdown, 0 Python. Obsidian-compatible memory for OpenClaw + Claude Code.
- **Strength:** "Tool-portable memory" framing — "one brain, every AI tool".
- **Gap:** Focused on memory/decisions rather than wiki compilation.
- **Lesson:** The multi-agent portability angle is strong. llmwiki's adapter pattern delivers this.

### Heavy Python / hosted

#### [lucasastorian/llmwiki](https://github.com/lucasastorian/llmwiki)
- **Shape:** 1 markdown + 47 Python files. Apache 2.0. Hosted demo at [llmwiki.app](https://llmwiki.app).
- **Strength:** Has a real backend (Supabase + S3), MCP server, hosted UI. Production-grade infra.
- **Gap:** Requires Supabase + S3 + Node + MCP server to self-host. Violates llmwiki's stdlib rule hard.
- **Lesson:** This is the "full-stack" approach. llmwiki is explicitly the opposite — zero infra, all local.

#### [bitsofchris/openaugi](https://github.com/bitsofchris/openaugi)
- **Shape:** 27 markdown + 48 Python files. "Your augmented knowledge base for Agentic work."
- **Strength:** Covers agent-centric use cases well.
- **Gap:** Very heavy.
- **Lesson:** There's room for a lighter alternative — which is llmwiki's niche.

### Session browsers (complementary, not competitors)

#### [raine/claude-history](https://github.com/raine/claude-history)
- **Shape:** TUI app. 3 markdown + 0 Python.
- **Strength:** "Best thing ever" user quote in the README. Clear UX.
- **Gap:** Search-only, no wiki building.
- **Lesson:** Users love the ability to search their session history. llmwiki's wiki is additive — it compiles search-ready content.

#### [sinzin91/search-sessions](https://github.com/sinzin91/search-sessions)
- **Shape:** CLI binary. 13 markdown + 0 Python (Go).
- **Strength:** Sub-300ms search across all sessions.
- **Gap:** Same — search only.
- **Lesson:** llmwiki could call out to search-sessions as an optional backend for its Cmd+K search.

### Not cloned (mentioned but out of scope)

- [tobi/qmd](https://github.com/tobi/qmd) — personal wiki format, broader than llmwiki
- [silverbulletmd/silverbullet](https://github.com/silverbulletmd/silverbullet) — extensible notes platform
- [swarmclawai/swarmvault](https://github.com/swarmclawai/swarmvault) — multi-agent vault
- [anzal1/quicky-wiki](https://github.com/anzal1/quicky-wiki) — small-scale wiki
- [Houseofmvps/codesight](https://github.com/Houseofmvps/codesight) — different domain
- [milla-jovovich/mempalace](https://github.com/milla-jovovich/mempalace) — memory palace
- [MetamusicX/llm-research-wiki](https://github.com/MetamusicX/llm-research-wiki) — research-only
