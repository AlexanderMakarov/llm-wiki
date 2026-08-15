---
title: "Claude Code"
type: entity
status: reviewed
tags: []
sources: [2026-08-10-00-quickstart-walkthrough, 2026-08-10-03-use-with-claude-code, 2026-08-10-07-example-workflows, 2026-08-10-claude-code-adapter, 2026-08-10-cli-reference-02, 2026-08-10-feature-matrix-every-feature-across-the-15-prior-implementations-01, 2026-08-10-getting-started-02, 2026-04-12-adapter-registry-refactor, 2026-07-18-mcp-server-tools, 2026-08-10-llmwiki-framework-building-an-agent-native-dev-tool-03, 2026-08-10-llmwiki-roadmap-phase-layer-item-prioritised-04, 2026-08-10-mode-b-agent, 2026-08-10-multi-agent-setup]
last_updated: 2026-08-12
---

# Claude Code

## Key Facts

- Creates `.jsonl` format session files that `llm-wiki` ingests as its primary data source. [[2026-08-10-feature-matrix-every-feature-across-the-15-prior-implementations-01]]
- An IDE with native support for automatic caller attribution via `CLAUDE_PROJECT_DIR` environment variable injection (v2.1.139+). [[2026-08-10-cli-reference-02]]
- Serves as a core adapter in `llm-wiki` that auto-detects sessions on every sync without requiring explicit configuration. [[2026-04-12-adapter-registry-refactor]]
- Provides the `SessionStart` hook mechanism for optional auto-sync of sessions upon IDE startup. [[2026-08-10-getting-started-02]]
- Functions as an MCP client capable of consuming MCP-based services. [[2026-07-18-mcp-server-tools]]

## Connections

Named by 13 source page(s), which is the evidence that
justified this candidate:

- [[2026-08-10-00-quickstart-walkthrough]]
- [[2026-08-10-03-use-with-claude-code]]
- [[2026-08-10-07-example-workflows]]
- [[2026-08-10-claude-code-adapter]]
- [[2026-08-10-cli-reference-02]]
- [[2026-08-10-feature-matrix-every-feature-across-the-15-prior-implementations-01]]
- [[2026-08-10-getting-started-02]]
- [[2026-04-12-adapter-registry-refactor]]
- [[2026-07-18-mcp-server-tools]]
- [[2026-08-10-llmwiki-framework-building-an-agent-native-dev-tool-03]]
- [[2026-08-10-llmwiki-roadmap-phase-layer-item-prioritised-04]]
- [[2026-08-10-mode-b-agent]]
- [[2026-08-10-multi-agent-setup]]
