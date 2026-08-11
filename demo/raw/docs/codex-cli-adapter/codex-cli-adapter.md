---
title: "Codex CLI adapter"
slug: codex-cli-adapter
project: codex-cli-adapter
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/adapters/codex-cli.md"
content_sha256: 95df671edec83f1679316d672d5c7736d8bd1bebb377e852aeaf4d794210d1a3
---

# Codex CLI adapter

**Status:** 🚧 **v0.1 stub — not yet production-ready**
**Module:** `llmwiki.adapters.codex_cli`
**Source:** [`llmwiki/adapters/codex_cli.py`](../../llmwiki/adapters/codex_cli.py)
**Tracking issue:** [LMW-13 · Codex CLI adapter (stub)](https://github.com/Pratiyush/llm-wiki/issues) (to be filled in when the v0.2 work starts)

## What "stub" means

The Codex CLI adapter in v0.1 does these things:

1. Imports cleanly — no errors on `python3 -m llmwiki adapters`
2. Registers under the name `codex_cli` in the adapter registry
3. Declares its expected session store path (`~/.codex/sessions/`)
4. Reports `available: yes` if the path exists

It does NOT yet:

- Parse records correctly for all known types
- Have a tested snapshot fixture
- Handle Codex-specific quirks (if any)

**If you run `llmwiki sync` with Codex installed, the stub will attempt to use the shared converter with the default record-type filters.** Your mileage may vary. The output is best-effort.

## How to help finalise this adapter

llmwiki's Phase 5.25 Adapter Flow applies. To push this adapter to production:

1. **Clone the repo** and install Codex CLI on your machine.
2. **Generate a few real sessions**, then copy 2-3 of them into `tests/fixtures/codex_cli/` after heavy redaction. Keep each fixture under 50 KB.
3. **Run the converter** against your fixtures and inspect the output:
   ```bash
   python3 -m llmwiki sync --adapter codex_cli --dry-run
   ```
4. **Compare with the Claude Code output format** for similar sessions. Note any fields that are missing or named differently.
5. **Update `llmwiki/adapters/codex_cli.py`** to handle those differences. Common customisations:
   - `session_store_path` — confirm the exact directory layout
   - `derive_project_slug()` — if Codex uses a different encoding
   - `is_subagent()` — if Codex has sub-agent sessions
6. **Add snapshot tests** under `tests/snapshots/codex_cli/<slug>.md` and a test file `tests/test_codex_adapter.py`.
7. **Write `docs/adapters/codex-cli.md`** (this file) with the finalised record format.
8. **Bump version** in `llmwiki/adapters/codex_cli.py`:
   ```python
   SUPPORTED_SCHEMA_VERSIONS = ["0.1"]  # actual Codex CLI version tested
   ```
9. **Open a PR** with all of the above. CHANGELOG gets a `Codex CLI adapter graduated from stub to production` entry.

## Expected session store path

Based on Codex CLI conventions as of April 2026 (subject to change):

```
~/.codex/sessions/
    <session-id>.jsonl        # main session files
~/.codex/projects/
    <project>/
        <session-id>.jsonl    # alternate layout
```

The adapter checks both paths.

## Expected record format

Unknown until we test against a real Codex install. We expect it to be similar to Claude Code's `.jsonl` format:

```jsonc
{"type": "user", "content": "...", "timestamp": "..."}
{"type": "assistant", "content": [{"type": "text", "text": "..."}, {"type": "tool_use", ...}], "usage": {...}}
{"type": "tool_result", "tool_use_id": "...", "content": "..."}
```

If the format diverges significantly, the adapter will need its own record classifier.

## Privacy

Redaction runs the same way for Codex sessions as for Claude Code — username, API keys, tokens, and emails are redacted at the converter layer. Any Codex-specific path patterns (e.g. `~/.codex/cache/`) can be added to `extra_patterns` in `config.json`.

## Tracking

- [Epic: v0.2.0 — Extensions](https://github.com/Pratiyush/llm-wiki/issues/2) — this adapter's graduation
- Pull requests welcome. See [CONTRIBUTING.md](../../CONTRIBUTING.md) §"Adding a new adapter" for the full contract.
