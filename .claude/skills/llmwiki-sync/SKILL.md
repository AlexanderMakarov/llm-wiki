---
name: llmwiki-sync
description: Sync Claude Code session transcripts into the user's llmwiki and ingest them into the wiki. Use when the user says "sync the wiki", "update llmwiki", "ingest recent sessions", "refresh the knowledge base", or asks a knowledge question that would benefit from up-to-date sessions. Also use when the user explicitly asks to refresh or rebuild the LLM wiki from their agent history.
---

# llmwiki-sync

## What this skill does

The user maintains a Karpathy-style LLM Wiki — a local, file-based knowledge base compiled from their Claude Code (and Codex CLI) session transcripts.

This skill runs the full sync pipeline:

```
~/.claude/projects/*/*.jsonl         (raw session transcripts)
        │
        ▼   python3 -m llmwiki sync
llmwiki/raw/sessions/<proj>/*.md     (Karpathy layer 1 — immutable markdown)
        │
        ▼   /wiki-ingest              (Claude in the loop)
llmwiki/wiki/sources, entities,      (Karpathy layer 2 — LLM-maintained wiki)
              concepts, syntheses
        │
        ▼   python3 -m llmwiki build
llmwiki/site/                         (Karpathy layer 3 — static HTML)
```

## When to use

Invoke this skill when the user:

- Says "sync the wiki", "update llmwiki", "ingest recent sessions", "refresh the knowledge base"
- Asks a knowledge question that would benefit from the latest sessions ("what have I been working on this week?") — run sync first, then `/wiki-query`
- Starts a new project and wants context from past work
- Says "what's new" or "catch me up" in a context where session history matters

Do NOT invoke when:

- The user is asking a question unrelated to their own work
- The tool is not installed (check for `llmwiki/` directory first)

## Workflow

1. **Locate the llmwiki install.** Check the current working directory and common locations:
   - `./` (if cwd contains `llmwiki/` package)
   - `~/Desktop/2026/production-draft/llmwiki/`
   - `~/llmwiki/`
   - `$LLMWIKI_ROOT` environment variable

   If you can't find it, tell the user and stop.

2. **Run the converter** (idempotent — safe to re-run):
   ```bash
   cd <llmwiki-dir>
   python3 -m llmwiki sync
   ```
   Capture the summary line: `N converted, M unchanged, K live, J filtered, X errors`.

3. **If N == 0**, report that the wiki is up to date and stop.

4. **If N > 0**, ingest the new files into the wiki using the Ingest Workflow from the repo's `CLAUDE.md`. Process one project at a time. If more than 20 new files, ask the user whether to process all or a subset first.

5. **Append to `wiki/log.md`**:
   ```
   ## [YYYY-MM-DD] sync | <N> sessions across <M> projects
   ```

6. **Report** what was converted, which wiki pages were created or updated, and any contradictions flagged.

## Options

The converter supports flags the user may want:

```bash
python3 -m llmwiki sync --project <substring>       # only one project
python3 -m llmwiki sync --since 2026-04-01          # only recent
python3 -m llmwiki sync --include-current           # include <60min live
python3 -m llmwiki sync --force                     # ignore state, reconvert all
python3 -m llmwiki sync --dry-run                   # preview without writing
```

## Hook installation (optional, for auto-sync)

If the user wants the converter to run automatically on every Claude Code session start, offer to add this to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "(python3 /absolute/path/to/llmwiki/tools/sessions_to_markdown.py > /tmp/llmwiki-sync.log 2>&1 &) ; exit 0"
          }
        ]
      }
    ]
  }
}
```

The `( ... &) ; exit 0` pattern ensures the hook runs in the background and never blocks session start.

## Troubleshooting

- **Permission errors on `raw/`**: the converter writes to `llmwiki/raw/sessions/`. Make sure the repo is writable.
- **Nothing converted, only "live"**: the default 60-minute live filter is skipping recent sessions. Pass `--include-current` to override, or wait an hour.
- **Converter says "module 'tomllib' not found"**: stale source. Update to the current version (`tools/sessions_to_markdown.py` uses `json`, not `tomllib`).
- **Privacy**: the converter redacts username, API keys, tokens, and emails by default. If you see unredacted PII, check `examples/sessions_config.json` → `redaction.real_username`.
