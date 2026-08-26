---
title: "Setup Guide — Your First LLM Wiki in 15 Minutes (part 2/2: Part 4: Customization)"
slug: setup-guide-your-first-llm-wiki-in-15-minutes-02
project: setup-guide-your-first-llm-wiki-in-15-minutes
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/tutorials/setup-guide.md"
content_sha256: 2a5077f9cc058e6c40812eb5eff1cc0a76dc3e6af51f6903f7813a5aa7d29f3d
---

> Part 2 of 2 of **Setup Guide — Your First LLM Wiki in 15 Minutes** — Part 4: Customization.

## Part 4: Customization

### 4.1 Add a project topic

Create `wiki/projects/my-project.md`:

```markdown
---
title: "my-project"
type: project
project: my-project
topics: [python, api, fastapi]
description: "My FastAPI CRUD service"
homepage: "https://github.com/me/my-project"
---
```

Rebuild and reload — the project card now shows topic chips.

### 4.2 Add a model entity

llmwiki ships structured model schemas. Create `wiki/entities/MyModel.md`:

```markdown
---
title: "MyModel"
type: entity
entity_kind: ai-model
provider: MyProvider
model: {"context_window": 200000, "license": "proprietary", "released": "2026-04-01"}
pricing: {"input_per_1m": 3.00, "output_per_1m": 15.00, "currency": "USD", "effective": "2026-04-01"}
modalities: [text, vision]
benchmarks: {"gpqa_diamond": 0.82, "swe_bench": 0.65}
---

# MyModel

## Connections
- [[Anthropic]]
```

Rebuild — a `/models/` page appears listing every model entity.

### 4.3 Use Obsidian

```bash
llmwiki link-obsidian --vault ~/Documents/"Obsidian Vault"
```

This symlinks the whole project into your vault. Now:
- Graph view shows every `[[wikilink]]`
- Backlinks panel shows citing pages
- Dataview queries in `wiki/dashboard.md` render live

See [`../obsidian-integration.md`](../obsidian-integration.md) for plugin configs.

### 4.4 Structured search (Cmd+K command palette)

Press `Cmd+K` (macOS) or `Ctrl+K` (Linux/Windows). Try:

| Query | What it does |
|-------|--------------|
| `flutter` | Full-text match |
| `type:session` | Only session pages |
| `type:topic` | Only topic pages (aliases match via body) |
| `project:my-project` | Filter by project |
| `model:claude-sonnet-4` | Filter by model |
| `date:2026-04` | Date prefix match |
| `confidence:>0.8` | High-confidence pages (v1.0) |
| `lifecycle:verified` | By lifecycle state (v1.0) |

### 4.5 Export for other tools

```bash
llmwiki sync --vault ~/Documents/"Obsidian Vault"   # vault sync (replaces removed export-obsidian)
llmwiki build                                         # HTML site + AI exports (llms.txt, llms-full.txt, graph.jsonld, sitemap.xml, rss.xml, robots.txt, ai-readme.md)
```

> The `export-obsidian`, `export-qmd`, and `export-marp` subcommands were removed in v1.2.0. See `docs/UPGRADING.md` for migration paths.

---

## Part 5: Multi-agent setup

llmwiki works with Claude Code, Codex CLI, Copilot Chat, Copilot CLI, Cursor,
Gemini CLI, Obsidian, and PDFs — all in one wiki. Each session gets an agent
badge on the site so you know which AI produced which transcript.

### 5.1 Enable multiple agents

The setup script detects what's installed. To force-enable:

```bash
llmwiki adapters
```

Shows default availability + configured state. Enable opt-in adapters in
`examples/sessions_config.json`:

```json
{
  "meeting": { "enabled": true, "source_dirs": ["~/Meetings"] },
  "jira": { "enabled": true, "server": "https://me.atlassian.net", "email": "me@x.com", "api_token": "..." },
  "web_clipper": { "enabled": true, "watch_dir": "raw/web" }
}
```

> The `pdf` adapter that used to live here was removed in the simplification sweep.

### 5.2 Share slash commands across agents

```bash
mkdir -p ~/.claude/commands
cp .claude/commands/wiki-*.md ~/.claude/commands/
```

Copies the `.claude/commands/wiki-*.md` files into your global Claude
Code commands dir. For Codex CLI / Cursor / other agents, copy them
into the appropriate skill directory for that tool — the file format
is portable.

### 5.3 Cross-platform paths

| OS | Claude Code | Codex CLI | Cursor |
|----|-------------|-----------|--------|
| macOS | `~/.claude/projects/` | `~/.codex/sessions/` | `~/Library/Application Support/Cursor/User/workspaceStorage/` |
| Linux | `~/.claude/projects/` | `~/.codex/sessions/` | `~/.config/Cursor/User/workspaceStorage/` |
| Windows | `%USERPROFILE%\.claude\projects\` | `%USERPROFILE%\.codex\sessions\` | `%APPDATA%\Cursor\User\workspaceStorage\` |

llmwiki auto-detects all of these — you usually don't need to configure paths
manually.

---

## Next steps

- **[Obsidian integration guide](../obsidian-integration.md)** — plugins + config
- **[Architecture](../architecture.md)** — 3-layer Karpathy + 8-layer build
- **[Configuration](../configuration.md)** — every tuning knob
- **[Privacy](../privacy.md)** — redaction rules + `.llmwikiignore`

If you hit a snag, check [GitHub Issues](https://github.com/Pratiyush/llm-wiki/issues) or file a new one.
