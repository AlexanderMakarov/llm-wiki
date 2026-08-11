---
title: "Phase 1.25 — Research Report (part 3/3: The 10x gap (feature matrix))"
slug: phase-1-25-research-report-03
project: phase-1-25-research-report
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/research.md"
content_sha256: 38ce338d0adda637c856de5cd5eeab0485842848f83af1b0e5b0ae87c2afff0b
---

> Part 3 of 3 of **Phase 1.25 — Research Report** — The 10x gap (feature matrix).

## The 10x gap (feature matrix)

| Feature | Most existing | llmwiki |
|---|---|---|
| Ingests `.jsonl` session transcripts | ❌ (generic markdown only) | ✅ |
| Claude Code adapter | Some | ✅ |
| Codex CLI adapter | None | ✅ stub (v0.2) |
| Multi-agent adapter pattern | None | ✅ |
| Pure stdlib + `markdown` (no DB, no MCP, no Node) | ~50% | ✅ |
| Beautiful static HTML viewer | ❌ | ✅ god-level UI |
| Global search (Cmd+K) | ❌ | ✅ client-side index |
| Syntax highlighting | Rarely | ✅ highlight.js (CDN) |
| Redaction by default | ❌ | ✅ username + API keys + tokens + emails |
| Live-session detection | ❌ | ✅ skips `<60min` old |
| Idempotent incremental sync | Some | ✅ mtime state file |
| Windows `.bat` scripts | Rarely | ✅ |
| Obsidian connector | Some (only input) | ✅ input **and** output |
| No cloud, no telemetry, no auth | Some | ✅ hard rule |
| Build time `<15s` for 300 sessions | Varies | ✅ 9s measured |

## Borrowed ideas (with attribution)

- **Directory layout** (`raw/`, `wiki/`, `index.md`, `log.md`, `overview.md`) — Karpathy's gist + SamurAIGPT/llm-wiki-agent
- **Slash commands** (`/wiki-ingest`, `/wiki-query`, `/wiki-lint`, `/wiki-graph`) — SamurAIGPT/llm-wiki-agent
- **Stale-page detection** — Ss1024sS/LLM-wiki
- **Local-LLM privacy angle** — kytmanov/obsidian-llm-wiki-local
- **Writer/viewer split** — louiswang524/llm-knowledge-base
- **Multi-tool portable memory framing** — remember-md/remember
- **Hosted-demo angle** (to be used for Phase 6.5 Self-Demo, not the tool itself) — lucasastorian/llmwiki
- **Single-skill marketing** — Astro-Han/karpathy-llm-wiki

## Decisions informed by this research

1. **Keep llmwiki stdlib-first.** `lucasastorian/llmwiki` shows the "full-stack" approach exists; llmwiki is the local alternative.
2. **Ship an Obsidian adapter in v0.1.** Four of 15 reference implementations use Obsidian — clearly important to users. Make it an optional input adapter, not the only path.
3. **Ship the HTML viewer as the hero feature.** None of the reference implementations have a beautiful static HTML output. This is llmwiki's most visible 10x.
4. **Keep the slash commands compatible** with SamurAIGPT/llm-wiki-agent and kfchou/wiki-skills. Users can switch between implementations.
5. **Use Karpathy's three-layer structure exactly** (`raw/` immutable, `wiki/` LLM-maintained, schema in CLAUDE.md/AGENTS.md). No deviations.
6. **Build-time redaction is non-negotiable** — none of the reference implementations do this, and session transcripts leak PII by default.

## References

- [Andrej Karpathy — LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [Karpathy's X thread](https://x.com/karpathy/status/2039805659525644595)
- [Tolkien Gateway](https://tolkiengateway.net/wiki/Main_Page) — example of a user-maintained wiki Karpathy cites for structure
- All 15 cloned repos listed above (under `.temp/`, gitignored)
