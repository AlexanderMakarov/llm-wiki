# Multi-Agent Setup

llmwiki reads sessions from multiple coding agents. A bare `llmwiki sync` runs **core** adapters only (`claude_code`, `codex_cli`) when their stores exist. **Contrib** adapters (Cursor Agent CLI, OpenClaw, Copilot, …) stay opt-in until [#182](https://github.com/AlexanderMakarov/llm-wiki/issues/182) — pass `--adapter <name>` or set `adapters.<name>.enabled: true` in config.

## Which agents are supported

| Agent | Registry name | Session store | How to enable | Status |
|---|---|---|---|---|
| Claude Code | `claude_code` | `~/.claude/projects/` | Core — default `sync` | Production |
| Codex CLI | `codex_cli` | `~/.codex/sessions/` (and `~/.codex/projects/`) | Core — default `sync` | Production |
| Cursor Agent CLI | `cursor_cli` | `~/.cursor/chats/` | Contrib — `--adapter cursor_cli` | Production |
| Cursor IDE | `cursor` | Cursor `workspaceStorage` | Contrib — `--adapter cursor` | Limited — IDE chat ingest is incomplete; see [#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2) |
| OpenClaw | `openclaw` | `~/.openclaw/agents/` | Contrib — `--adapter openclaw` | Production |
| OpenCode | `opencode` | OpenCode / OpenClaw app-config sessions dirs | Contrib — `--adapter opencode` | Production |
| GitHub Copilot Chat | `copilot_chat` | VS Code workspaceStorage | Contrib — `--adapter copilot_chat` | Production |
| GitHub Copilot CLI | `copilot_cli` | `~/.copilot/session-state/` | Contrib — `--adapter copilot_cli` | Production |
| Gemini CLI | `gemini_cli` | `~/.gemini/` (and related paths) | Contrib — `--adapter gemini_cli` | Scaffold — store detection only; no verified launch markers yet |
| ChatGPT export | `chatgpt` | `conversations.json` export | Contrib — opt-in `enabled: true` + path | Production (export ingest) |
| Obsidian | `obsidian` | Configurable vault paths | Contrib — opt-in `enabled: true` | Production — **notes intake**, not an agent chat source |

Per-adapter detail: [Claude Code](adapters/claude-code.md) · [Codex CLI](adapters/codex-cli.md) · [Cursor Agent CLI](adapters/cursor-cli.md) · [Cursor IDE](adapters/cursor.md) · [OpenClaw](adapters/openclaw.md) · [OpenCode](adapters/opencode.md) · [Copilot](adapters/copilot.md) · [Gemini CLI](adapters/gemini-cli.md) · [ChatGPT](adapters/chatgpt.md) · [Obsidian](adapters/obsidian.md).

### Cursor Agent CLI vs Cursor IDE

- **Cursor Agent CLI** (`cursor_cli`) — working session source for non-interactive / Agent CLI chats under `~/.cursor/chats/`. This is what `filters.exclude_headless` can classify today.
- **Cursor IDE** (`cursor`) — IDE workspace chat ingest is not finished ([#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2)). Do not expect IDE chats to land in the wiki from this adapter yet.

## What “automated” (headless) means

`filters.exclude_headless` defaults to **true**. It applies at **ingest** (`sync` never converts those sessions) and at **synthesis** / `--estimate` (already-converted raw files marked headless are skipped and not counted as backlog). Set `"exclude_headless": false` in `config.json` to keep automated launches.

| Source | Counts as automated (skipped when filter is on) |
|---|---|
| Claude Code | `entrypoint` starts with `sdk-` (e.g. `sdk-cli`) **or** `promptSource` is `sdk` — headless `claude -p` / Agent SDK runs |
| Cursor Agent CLI | Store meta has `subagentInfo` **or** `approvalMode` is `auto-review`. Interactive top-level Agent chats stay eligible. Nested Task/subagent runs are classified under `exclude_headless` (not `include_subagents`) |
| Codex CLI, OpenCode, Copilot CLI, Copilot Chat | No verified automation markers in the store yet — sessions are treated as **not** headless |
| OpenClaw | **All** OpenClaw sessions are treated as not headless |
| Gemini CLI, Cursor IDE | N/A until launch detection exists — never classified headless today |
| ChatGPT export, Obsidian | **Not applicable** — export / notes intake, not agent launches |

Legacy raw files with no `is_headless` marker stay eligible until you re-sync (re-convert) them. Sync still reports skipped automated sessions as one aggregate headless count in the filter summary.

## How default sync chooses adapters

1. Imports **core** adapters (`claude_code`, `codex_cli`).
2. Calls `is_available()` — whether the session store path exists.
3. Runs each available core adapter. Contrib adapters load only when named with `--adapter` (or explicitly enabled in config where that applies).

```bash
# Core only (Claude + Codex when present)
python3 -m llmwiki sync

# Also pull Cursor Agent CLI + OpenClaw
python3 -m llmwiki sync --adapter claude_code codex_cli cursor_cli openclaw
```

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

```bash
python3 -m llmwiki sync --adapter cursor_cli
```

See [Cursor Agent CLI adapter](adapters/cursor-cli.md).

### Cursor IDE

```bash
python3 -m llmwiki sync --adapter cursor
```

Limited until [#2](https://github.com/AlexanderMakarov/llm-wiki/issues/2) lands full IDE ingest. See [Cursor IDE adapter](adapters/cursor.md).

### OpenClaw

```bash
python3 -m llmwiki sync --adapter openclaw
```

Native store under `~/.openclaw/agents/`. All sessions are treated as not headless. See [OpenClaw adapter](adapters/openclaw.md).

### OpenCode

```bash
python3 -m llmwiki sync --adapter opencode
```

### GitHub Copilot Chat / CLI

```bash
python3 -m llmwiki sync --adapter copilot_chat
python3 -m llmwiki sync --adapter copilot_cli
```

Copilot CLI: set `COPILOT_HOME` to override `~/.copilot`.

### Gemini CLI

```bash
python3 -m llmwiki sync --adapter gemini_cli
```

Scaffold — store paths are checked; automation markers are not detected yet.

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

1. Use `--adapter` to test one contrib source at a time.
2. Each agent gets its own project slug from its store layout — sessions do not collide across agents.
3. The wiki layer is agent-agnostic once files are in `raw/`.
4. Schedule with `llmwiki install-automation` (or cron / Task Scheduler) rather than a hand-rolled loop.
5. Combine with `.llmwikiignore` to skip noisy projects from any adapter.
