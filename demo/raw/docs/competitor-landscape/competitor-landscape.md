---
title: "Competitor Landscape"
slug: competitor-landscape
project: competitor-landscape
type: source
tags: [wiki-add, raw-doc]
date: 2026-10-21
source: "docs/competitor-landscape.md"
content_sha256: cadb83747d4a95bc362791b6d1d5e7ef9c0e9f51abffeea5880a5b599bd24878
---

# Competitor Landscape

How llmwiki compares with other tools that keep memory across agentic coding tools.

## The problem

Every AI coding agent (Claude Code, Codex CLI, Cursor, Copilot, Gemini CLI and others) writes a full session transcript to disk. After a few months you have hundreds of sessions containing decisions, code patterns, and debugging insights — and the next agent cannot see them.

The table compares tools that persist that kind of memory and let agents use it again. The static site is how a person observes llmwiki's vault. It is not the memory.

## Function grid

Columns are tools that keep memory for agents. Cells describe the mechanism, not a slogan. Other-column sources: [agentmemory recall](https://github.com/rohitg00/agentmemory/blob/main/docs/recall.md), [Mem0 — how it works](https://docs.mem0.ai/core-concepts/how-it-works), [TencentDB Agent Memory install guide](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/feat/server_team/INSTALL.md) (9 named clients).

| Function | llmwiki | agentmemory | mem0 | TencentDB Agent Memory |
|---|---|---|---|---|
| **Output for agents** | MCP. The agent calls a tool. Nothing is written into the prompt. | MCP and HTTP. Hooks also write a recall into the next session. | The application calls `search` and pastes the result into the prompt. Platform MCP exposes the same calls as tools. | Hooks write a recall into the prompt. Tools can search memories, search conversations, and open one stored node. |
| **Context impact** | 6 MCP tool descriptions. A page is added only when the agent reads it. | 54 MCP tool descriptions when the server is up (7 when it is not), plus a filtered recall. Default budget is 2000 tokens. Not the whole store. | A filtered slice the application pastes in. Their own guide uses the top few hits, on the order of 150–250 tokens. Platform MCP instead puts 11 tool descriptions in context. Not the whole store. | A few hundred tokens: persona, scenes, or the task canvas. One node is added when the agent opens it. Not the whole store. |
| **Output for humans** | Static HTML site. Open the files. | Local viewer. Only while the server is running. | Dashboard of stored facts. Open-source setup and hosted platform. | Markdown files on disk (persona, scenarios, task canvas). Open the directory. |
| **Agent coverage** | 11: Claude Code, Codex CLI, ChatGPT, Copilot Chat, Copilot CLI, Cursor IDE, Cursor CLI, Gemini CLI, Obsidian, OpenCode, OpenClaw. | 25: Claude Code, Codex CLI, GitHub Copilot CLI, Cursor, OpenCode, Devin, OpenClaw, Hermes, pi, OpenHuman, Gemini CLI, Antigravity, Claude Desktop, Warp, Zed, Cline, Continue, Droid, Kiro, Qwen Code, DeepSeek Harness, Roo Code, Kilo Code, Goose, Aider. | Any. Something calls `add` and `search`. | 9: Claude Code, CodeBuddy, WorkBuddy, Codex, DeepSeek Harness, OpenCode, Hermes, OpenClaw, Pi. |
| **KB sources** | [agent sessions, files, folders, URLs, PDFs] | [live tool activity, records saved on purpose, Claude Code JSONL] | [messages passed to `add`] | [agent conversations, tool outputs] |
| **KB layers** | [sources, entities, concepts, projects, syntheses] | [working, episodic, semantic, procedural] | [facts, entities, graph]. Graph is the hosted platform only. | [conversation, atomic facts, scenarios, persona] |
| **Query features** | Literal substring. Filters: type, confidence, lifecycle, tags. One page can be opened. | BM25, optional vectors, graph fusion. Filters: layer, project, agent. One hit can be opened by id. | Vector, keyword, entity overlap, time. Filters: user, agent, run. Graph rank is the hosted platform only. One memory can be opened by id. | BM25 and vector. Filters: which layer you start from. One node can be opened by id. |
| **Automation cadence** | OS scheduler (once a day or once an hour), a `watch` process, or agent hooks. Hooks are brittle and not the default. All three pull transcripts in. None of them push a summary out. | Hooks on each turn, while the server is running. The next session starts with a recall. | The application calls `add` after a turn and `search` before the next model call. | End of turn sends the conversation. A worker extracts the next layers. Recall is injected before the next prompt. |
| **Resources usage** | Nothing stays running. MCP starts with the agent session and exits with it. The site is static files. CLI commands are one shot. `watch` only polls for new input. | Memory server, engine, and viewer stay up. Stop them and recall stops. | A SQL database and a vector store stay up, or the hosted platform runs them. | A gateway stays up (SQLite and a vector index locally, or the hosted service). The agent plugin stores nothing by itself. |
| **Tokens cost** | No LLM for search, sync, or reading raw pages. An LLM is used for `synth`, which derives entities and concepts from raw data that stays searchable, and when inner skills run. | No LLM in the default keyless mode. Search is BM25. An LLM runs only if a provider is set and compression or graph extraction is turned on. | An LLM runs on `add` to extract facts, unless `infer=False`. `search` calls an embedding model, not a chat model. | An LLM runs to extract atomic facts, scenarios, and a persona. An API key is required. The injected canvas is not another model call. |
| **Observability** | Static site: pipeline freshness, token totals, health, the candidate queue, and MCP call counts. From the last build and the local usage log. | Viewer and an HTTP health check, while the server is up. | Dashboard of the facts that were stored. | Files you can open: persona, scenarios, canvas, and the raw conversation they point at. Gateway health is an HTTP check. |

Projects: [agentmemory](https://github.com/rohitg00/agentmemory), [mem0](https://docs.mem0.ai/core-concepts/how-it-works), [TencentDB Agent Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory).

## Same shape, different job

These look like llmwiki. They build a Karpathy-style wiki a person reads. They do not take coding-agent session stores.

[llmwiki (lucasastorian)](https://github.com/lucasastorian/llmwiki) is a different project with the same name. It turns documents, web clips, and highlights into a wiki you browse in a Next.js app (on your machine, or at llmwiki.app).

The [Karpathy LLM Wiki plugin for Obsidian](https://community.obsidian.md/plugins/karpathywiki) builds wiki pages from notes already in an Obsidian vault and lets you query them inside Obsidian.

## llmwiki's positioning

llmwiki occupies a specific niche:

1. **Shared agent memory.** One vault holds what your coding agents already did. Other agents read it back through MCP. Memory is not trapped in a single chat.

2. **Local-first.** No cloud, no API keys, no accounts. Your data stays on your machine (or your own GitHub Pages).

3. **Multi-agent.** Eleven agents (Claude Code, Codex CLI, ChatGPT, Copilot Chat, Copilot CLI, Cursor IDE, Cursor CLI, Gemini CLI, Obsidian, OpenCode, OpenClaw) across core and contrib adapters, with a clean adapter interface for adding more. See the agent table in the [README](../README.md#agents). PDFs are added with `llmwiki add`, not synced as an agent.

4. **Karpathy-standard.** Based on [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — sources, entities, concepts, projects, syntheses, all interlinked with wikilinks.

5. **Minimal runtime.** No numpy, no torch, no node, no database. Python 3.12+ with `markdown` as the single runtime dependency.

6. **Observable.** `build` writes a static site so a person can see pipeline state, token and cache metrics, health, and which pages have settled. Agents use MCP against the vault. They do not need the site.

## When llmwiki is NOT the right tool

- You want recall pushed into the next coding session and you do not want a vault (use agentmemory)
- You are building an application and need a memory API (use mem0)
- A team should share one memory server through a proxy (use TencentDB Agent Memory)
- You want a wiki of documents and web highlights, not agent sessions (use llmwiki (lucasastorian))
- Your notes already live in Obsidian and you want to query them there (use the Karpathy LLM Wiki plugin)
- You have only a few sessions: writing notes by hand is enough
- You want collaborative editing on a shared wiki (use Notion, Obsidian Publish, or Confluence)
