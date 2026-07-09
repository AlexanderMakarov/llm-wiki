# Troubleshooting

Common errors and how to fix them.

## "No sessions found"

**Cause:** The agent you expect is either not installed or stores sessions in a non-default location.

**Fix:**

1. Run `python3 -m llmwiki adapters` to see which agents are detected.
2. If the agent shows `available: no`, verify the session store path exists:
   - Claude Code: `~/.claude/projects/`
   - Codex CLI: `~/.codex/sessions/`
   - Copilot Chat: VS Code `workspaceStorage/*/chatSessions/`
   - Copilot CLI: `~/.copilot/session-state/`
   - Cursor: Cursor IDE `workspaceStorage/`
   - Gemini CLI: `~/.gemini/`
3. If the agent stores sessions in a custom location, override it in `config.json`:

```json
{
  "adapters": {
    "claude_code": {
      "roots": ["/custom/path/to/projects"]
    }
  }
}
```

4. If you have sessions but they are very recent (< 60 minutes old), the converter skips them as "live sessions." Use `--include-current` to override:

```bash
python3 -m llmwiki sync --include-current
```

## "UnicodeDecodeError" during sync

**Cause:** Corrupt or binary content in a `.jsonl` file.

**Fix:** This was fixed in v0.5 -- the converter now uses `errors="replace"` when reading files. Upgrade to the latest version:

```bash
git pull origin master
pip install -e .
```

If you still see this error, the file may be severely corrupted. Identify it with `--dry-run` and exclude it via `.llmwikiignore`.

## Build fails with import error

**Cause:** The `llmwiki` package is not installed in your Python environment.

**Fix:**

```bash
pip install -e .
# or, if you don't want an editable install:
pip install markdown
```

The `setup.sh` script does this automatically. If you skipped setup, install manually.

## Site is blank after build

**Cause:** No session data exists under `raw/sessions/`.

**Fix:**

1. Run `llmwiki sync` first to convert agent sessions into markdown.
2. Then run `llmwiki build`.
3. Check that `raw/sessions/` contains `.md` files:

```bash
find raw/sessions -name "*.md" | head -5
```

If empty, see "No sessions found" above.

## Code blocks not highlighted

**Cause:** highlight.js loads from a CDN (`cdnjs.cloudflare.com`). If the CDN is blocked by a firewall, VPN, or you are fully offline, code blocks render as plain unformatted text.

**Fix:** This is by design -- the site degrades gracefully. Code is still readable, just not colorized. If you need highlighting offline, you could vendor the highlight.js files into `site/` manually, but this is not currently automated.

## "Permission denied" on serve

**Cause:** Port 8765 is already in use by another process.

**Fix:**

```bash
# Use a different port
python3 -m llmwiki serve --port 9000

# Or find and kill the process using 8765
lsof -i :8765
kill <PID>
```

## Heatmap shows no data

**Cause:** The 365-day activity heatmap requires sessions with valid date information in their YAML frontmatter.

**Fix:**

1. Verify your sessions have `started:` or `date:` fields in their frontmatter:

```bash
head -10 raw/sessions/*/2026-*.md
```

2. If dates are missing, the converter may have failed to extract timestamps. Re-sync with `--force`:

```bash
python3 -m llmwiki sync --force
```

3. Rebuild the site after re-syncing:

```bash
python3 -m llmwiki build
```

## Search returns nothing

**Cause:** The search index (`site/search-index.json`) is stale or was not generated.

**Fix:** Rebuild the site. The build step regenerates the search index from all current content.

```bash
python3 -m llmwiki build
```

If the search index file exists but search still fails, open the browser console (F12) and check for JavaScript errors.

## Token/tool charts not rendering

**Cause:** The visualization components require session frontmatter with `total_tokens`, `tools_used`, or similar metadata fields.

**Fix:** These fields are populated during `llmwiki sync`. If you have older sessions that predate the metadata extraction, re-sync with `--force`:

```bash
python3 -m llmwiki sync --force
python3 -m llmwiki build
```

## `.llmwikiignore` patterns not working

**Cause:** The ignore file uses gitignore-style glob patterns, not regexes.

**Fix:** Verify pattern syntax:

```
# Correct: glob patterns
confidential-client/*
*2025-11-*

# Wrong: regex patterns (these will not match)
^confidential.*$
```

The ignore file must be at the repo root as `.llmwikiignore`.

## Sync is slow

**Cause:** Re-converting all sessions on every run.

**Fix:** The converter tracks state in `llmwiki-state.json` (at the vault root when `vault.default_path` / `--vault` is set). If this file is missing or corrupted, it reconverts everything. Normal behavior is to skip unchanged files (fast no-op). If you used `--force`, the next run without `--force` will be fast again.

For large session stores (1000+ sessions), the initial sync can take a few minutes. Subsequent syncs only process new or modified files.

## Build output is too large

**Cause:** Very large session stores produce many HTML pages.

**Fix:**

1. Use `.llmwikiignore` to exclude projects or date ranges you don't need.
2. Check the perf budget with `llmwiki manifest --fail-on-violations`.
3. The truncation settings in `config.json` control how much of each session is rendered:

```json
{
  "truncation": {
    "tool_result_chars": 500,
    "bash_stdout_lines": 5,
    "user_prompt_chars": 4000,
    "assistant_text_chars": 8000
  }
}
```

Reduce these values to shrink output.
