# Multi-Agent Setup

llmwiki reads sessions from multiple coding agents. Every shipped source is configured under `adapters.<name>` in `config.json`. Bare `llmwiki sync` runs all enabled coding-agent sources when their store is present; notes intake (Obsidian, ChatGPT export) needs `enabled: true`. Run `llmwiki configure-sources` after install to probe stores and write settings, or use `--adapter <name>` for a one-off limit.

## Which agents are supported

| Agent | Registry name | Session store | How to enable | Status |
|---|---|---|---|---|
| Claude Code | `claude_code` | `~/.claude/projects/` | Auto when store present (`adapters.claude_code`) | Production |
| Codex CLI | `codex_cli` | `~/.codex/sessions/` (and `~/.codex/projects/`) | Auto when store present | Production |
| Cursor Agent CLI | `cursor_cli` | `~/.cursor/chats/` | Auto when store present | Production |
| Cursor IDE | `cursor_ide` | `globalStorage/state.vscdb` (Composer) | `--adapter cursor_ide` (not on bare sync until `ingest_ready`) | Production |
| OpenClaw | `openclaw` | `~/.openclaw/agents/` or `<vault>/.openclaw-sessions-inbox` | Auto when store present; set `adapters.openclaw.roots` for vault inbox | Production |
| OpenCode | `opencode` | OpenCode / OpenClaw app-config sessions dirs | Auto when store present | Production |
| GitHub Copilot Chat | `copilot_chat` | VS Code workspaceStorage | Auto when store present | Production |
| GitHub Copilot CLI | `copilot_cli` | `~/.copilot/session-state/` | Auto when store present | Production |
| Gemini CLI | `gemini_cli` | `~/.gemini/` (and related paths) | Auto when store present | Scaffold — store detection only |
| ChatGPT export | `chatgpt` | `conversations.json` export | `enabled: true` + `export_dirs` (opt-in) | Production (export ingest) |
| Obsidian | `obsidian` | Configurable vault paths | `enabled: true` + `vault_paths` (opt-in notes intake) | Production |

Per-adapter detail: [Claude Code](adapters/claude-code.md) · [Codex CLI](adapters/codex-cli.md) · [Cursor Agent CLI](adapters/cursor-cli.md) · [Cursor IDE](adapters/cursor-ide.md) · [OpenClaw](adapters/openclaw.md) · [OpenCode](adapters/opencode.md) · [Copilot](adapters/copilot.md) · [Gemini CLI](adapters/gemini-cli.md) · [ChatGPT](adapters/chatgpt.md) · [Obsidian](adapters/obsidian.md).

### Cursor Agent CLI vs Cursor IDE

- **Cursor Agent CLI** (`cursor_cli`) — working session source for Agent CLI chats under `~/.cursor/chats/`.
- **Cursor IDE** (`cursor_ide`) — working Composer ingest from global `state.vscdb` (alias `cursor` still resolves). Both adapters use the same `cursor-<12-char-hash>` project-id form when a workspace hash is known.

## What “automated” (headless) means

`filters.exclude_headless` defaults to **true**. It applies at **ingest** (`sync` never converts those sessions) and at **synthesis** / `--estimate` (already-converted raw files marked headless are skipped and not counted as backlog). Set `"exclude_headless": false` in `config.json` to keep automated launches.

| Source | Counts as automated (skipped when filter is on) |
|---|---|
| Claude Code | `entrypoint` starts with `sdk-` (e.g. `sdk-cli`) **or** `promptSource` is `sdk` — headless `claude -p` / Agent SDK runs |
| Cursor Agent CLI | Store meta has `subagentInfo` **or** `approvalMode` is `auto-review`. Interactive top-level Agent chats stay eligible. Nested Task/subagent runs are classified under `exclude_headless` (not `include_subagents`) |
| Cursor IDE | `composerHeaders.isSubagent` — agents spawned from a parent Composer stay skipped; user-facing Composer chats stay eligible |
| Codex CLI, OpenCode, Copilot CLI, Copilot Chat | No verified automation markers in the store yet — sessions are treated as **not** headless |
| OpenClaw | **All** OpenClaw sessions are treated as not headless |
| Gemini CLI | Scaffold — N/A until launch detection exists — never classified headless today |
| ChatGPT export, Obsidian | **Not applicable** — export / notes intake, not agent launches |

Legacy raw files with no `is_headless` marker stay eligible until you re-sync (re-convert) them. Sync still reports skipped automated sessions as one aggregate headless count in the filter summary.

## How default sync chooses adapters

1. Loads every shipped adapter from the registry.
2. For each adapter, checks whether its store path exists (`present`) and whether ingest is ready. Cursor IDE is production via `--adapter cursor_ide`, but is **not** selected on bare sync while `ingest_ready` is false (avoids flooding from a large historical Composer DB until you set a lookback and opt in).
3. Includes every **coding-agent** source that is present, ingest-ready, and not explicitly disabled (`enabled: false` in `adapters.<name>`). Notes/export intake (Obsidian, ChatGPT) requires `enabled: true`.

```bash
# All enabled coding-agent sources with stores on disk
python3 -m llmwiki sync

# Limit to specific sources this run
python3 -m llmwiki sync --adapter cursor_cli openclaw
```

Run `llmwiki configure-sources` after install to probe paths (including `<vault>/.openclaw-sessions-inbox` when `vault.default_path` is set) and write `config.json`. The interview asks shared start date first (default today−30), then per source **Sessions · Earliest · In last 30 days** before Enable. Unset `filters.since` (skip the interview) still means unlimited. See [configuration-reference.md — Sync lookback](configuration-reference.md#sync-lookback).

## Checking detected agents

```bash
python3 -m llmwiki adapters
llmwiki adapters --wide
```

## Per-agent setup

### Claude Code

Sessions live at `~/.claude/projects/<project-dir-slug>/<session-uuid>.jsonl`. Sub-agent runs are under `subagents/agent-*.jsonl`. No configuration needed for a default sync.

### Codex CLI

Sessions under `~/.codex/sessions/` (date-bucketed) and optionally `~/.codex/projects/`. The adapter reads `session_meta.cwd` for the project slug and normalizes Codex JSONL into the shared format. Core adapter — production.

### Cursor Agent CLI

Runs on bare `sync` when `~/.cursor/chats/` exists. See [Cursor Agent CLI adapter](adapters/cursor-cli.md).

### Cursor IDE

```bash
python3 -m llmwiki sync --adapter cursor
```

Composer threads from global `state.vscdb`; spawned subagents skipped under default `exclude_headless`. Not on bare sync while `ingest_ready` is false. See [Cursor IDE adapter](adapters/cursor-ide.md).

### OpenClaw

Runs on bare `sync` when configured roots exist. Default native store: `~/.openclaw/agents/`. Vault mirror: `<vault>/.openclaw-sessions-inbox/<agent>/*.jsonl`. See [OpenClaw adapter](adapters/openclaw.md).

### OpenCode

Runs on bare `sync` when its store paths exist.

### GitHub Copilot Chat / CLI

Runs on bare `sync` when stores exist.

```bash
python3 -m llmwiki sync --adapter copilot_chat   # optional one-run limit
```

Copilot CLI: set `COPILOT_HOME` to override `~/.copilot`.

### Gemini CLI

Runs on bare `sync` when `~/.gemini/` exists. Automation markers are not detected yet.

### ChatGPT / Obsidian

Export and notes intake. Set `enabled: true` (and paths) in config; they are outside automated-launch detection.

## Per-adapter configuration

Override roots in `config.json`:

```json
{
  "adapters": {
    "codex_cli": {
      "roots": ["~/custom/codex/sessions"]
    },
    "cursor_cli": {
      "roots": ["~/.cursor/chats"]
    },
    "openclaw": {
      "roots": ["~/.openclaw/agents", "<vault>/.openclaw-sessions-inbox"]
    },
    "obsidian": {
      "vault_paths": ["~/Documents/My Vault"],
      "exclude_folders": [".obsidian", "Templates"],
      "min_content_chars": 50
    }
  }
}
```

## Tips

1. Use `--adapter` to limit sync to one or more sources for a single run.
2. Each agent gets its own project slug from its store layout — sessions do not collide across agents.
3. The wiki layer is agent-agnostic once files are in `raw/`.
4. Schedule with `llmwiki install-automation` (or cron / Task Scheduler) rather than a hand-rolled loop.
5. Combine with `.llmwikiignore` to skip noisy projects from any adapter.
