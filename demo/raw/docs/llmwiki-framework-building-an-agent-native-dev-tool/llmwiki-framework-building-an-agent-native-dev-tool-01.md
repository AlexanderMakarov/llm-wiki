---
title: "llmwiki Framework — Building an Agent-Native Dev Tool (part 1/3)"
slug: llmwiki-framework-building-an-agent-native-dev-tool-01
project: llmwiki-framework-building-an-agent-native-dev-tool
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/framework.md"
content_sha256: eaa0b1b799c976996e7f4c0abe139ab99b35aae734b1fa67f0b35a8648668fa7
---

> Part 1 of 3 of **llmwiki Framework — Building an Agent-Native Dev Tool**.

# llmwiki Framework — Building an Agent-Native Dev Tool

> **Adapted from** the maintainer's "Open Source Project Framework v4.0" (local reference — kept outside the public repo).
>
> **Extensions** specific to llmwiki and any tool in this class (dev tools that ingest from AI coding agents):
>
> 1. **Agent-Aware pipeline** (Phase 1.75)
> 2. **Adapter Contribution flow** (Phase 5.25)
> 3. **Self-Demo pattern** (Phase 6.5)
> 4. **Living-Knowledge loop** (Phase 7.5)
> 5. **Schema-Versioning rules** (cross-cutting)
> 6. **Privacy-First rules** (cross-cutting)
> 7. **Performance Budget** (cross-cutting)
> 8. **Dogfooding Meta-Loop** (cross-cutting)

This document is both the **spec for how llmwiki is built** and the **contribution guide for anyone extending it**. It is the source of truth for what "done" means at each phase.

---

## The Pipeline (extended)

```
0 CAPTURE  →  1 VALIDATE  →  1.25 RESEARCH  →  1.5 STEERING  →  1.75 AGENT SURVEY
  →  2 BRAND  →  3 STRUCTURE  →  4 CONTENT  →  5 CONTRIBUTION  →  5.25 ADAPTER FLOW
  →  5.5 PRE-LAUNCH QA  →  6 LAUNCH  →  6.5 SELF-DEMO  →  7 GROW
  →  7.5 LIVING KNOWLEDGE  →  8 MAINTAIN
```

**Five** new phases slot into the parent pipeline. **Kiro-style spec-driven** overlay applies to every phase (see `.kiro/steering/` for always-loaded rules).

The new phases are:

| Phase | New? | Why it exists | Deliverable |
|---|---|---|---|
| 1.75 Agent Survey | NEW | Agent-native tools need to know the `.jsonl` / session store schema for every agent they claim to support | Per-agent compatibility matrix + test fixtures |
| 5.25 Adapter Flow | NEW | Extensible agent tools need a contract for community-contributed adapters | `docs/adapter-contract.md` + PR template |
| 6.5 Self-Demo | NEW | Dev tools that produce browsable HTML have a killer demo surface — the tool's own dev history | Public GitHub Pages site built from the repo's own sessions |
| 7.5 Living Knowledge | NEW | The wiki built during development IS a growth engine — publish it and it sells the tool for you | Public wiki updating on every release |

---

## Phase 0 — Capture

Same as parent framework. See `idea-brief.md` at the repo root for llmwiki's capture.

**Gate to Phase 1**: idea-brief.md exists and names the target users + the one non-obvious mechanism that makes this 10x.

---

## Phase 1 — Validate

Same scoring (/25). llmwiki scored **22/25** on 2026-04-08 (see `_progress.md`).

| Dimension | Score | Note |
|---|---|---|
| Gap | 5/5 | No existing tool bridges `.jsonl` → Karpathy wiki |
| Quality gap | 5/5 | Existing implementations require Node + Postgres + MCP; we require only stdlib + one pip install |
| Audience | 4/5 | Every Claude Code user is a potential user; niche but growing fast |
| Effort | 4/5 | v0.1 ships in a day; v1.0 in a week |
| Personal fit | 4/5 | Author already has 278+ session transcripts; uses the tool daily |

**Kill threshold**: < 13/25 → kill. 13–19 → research further. 20+ → build.

---

## Phase 1.5 — Project Steering

**llmwiki steering decisions** (locked on 2026-04-08):

| Decision | Choice | Rationale |
|---|---|---|
| Runtime dep floor | Python 3.12+ stdlib + `markdown` | Matches oldest common macOS system Python |
| Optional deps | `graphifyy` (advanced graph layout) | Detected, not required. PDF ingestion was removed in the simplification sweep. |
| No-network by default | True | Privacy + offline-first |
| Binding default | `127.0.0.1` only | Privacy-first — user must opt-in to LAN |
| Redaction default | ON | Username, API keys, tokens, emails — all redacted |
| Config file | JSON, single file | TOML excluded because `tomllib` is 3.11+ only |
| Distribution | Git-native (clone + `./setup.sh`) | v0.1. pip-installable from git in v0.2 |
| Branch name | `master` | Matches author's other projects |
| License | MIT | Permissive, widely understood |
| Telemetry | None, ever | Trust the user's machine |
| GPL/AGPL deps | Forbidden | Keep the tool MIT-compatible end-to-end |

---

## Phase 1.75 — Agent Survey (NEW)

Before Phase 2 Brand, any tool targeting AI coding agents must complete this survey:

### Agent compatibility matrix

| Agent | Session store | File pattern | Record types seen | Tested version | Adapter status |
|---|---|---|---|---|---|
| Claude Code | `~/.claude/projects/<proj>/` | `<uuid>.jsonl` + `<uuid>/subagents/agent-*.jsonl` | `user`, `assistant`, `tool_use`, `tool_result`, `queue-operation`, `file-history-snapshot`, `progress` | 2.1.87 | ✅ Production |
| Codex CLI | `~/.codex/sessions/` (TBC) | TBC | TBC | TBC | 🚧 Stub |
| Gemini CLI | TBC | TBC | TBC | TBC | ⏳ Planned |
| OpenCode | `~/.opencode/` (TBC) | TBC | TBC | TBC | ⏳ Planned |

### Test fixture requirements

Every claimed agent must ship:

1. **At least one fixture `.jsonl`** under `tests/fixtures/<agent>/` (synthetic or heavily redacted).
2. **A snapshot test** that converts the fixture and asserts the output matches `tests/snapshots/<agent>/*.md`.
3. **A schema version constant** pinned in the adapter: `SUPPORTED_SCHEMA_VERSIONS = ["..."]`.

Without all three, the adapter ships as a **stub** (imports cleanly, logs "not yet tested", does not convert).

### Graceful degradation rule

When an adapter encounters a record `type` it doesn't know:
- **Skip it silently** — don't crash the build
- **Log at DEBUG level**, not WARN or ERROR
- **Never drop user-visible content** — user prompts and assistant text are always rendered even if the wrapping record is unknown

### Gate to Phase 2

1.75 closes when:
- [x] Matrix row exists for every agent the README claims to support
- [x] Test fixtures exist for every "Production" adapter
- [x] Stub adapters are clearly marked in the README and CHANGELOG

---

## Phase 2 — Brand

Same as parent. llmwiki brand artifacts:

- **Name**: `llmwiki` (lowercase, one word)
- **Tagline**: "LLM-powered knowledge base from your Claude Code and Codex CLI sessions"
- **README header**: License + Python + Claude Code badge + Codex badge
- **LICENSE**: MIT

---
