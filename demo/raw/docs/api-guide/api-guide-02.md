---
title: "API Guide (part 2/2: Example: custom pipeline script)"
slug: api-guide-02
project: api-guide
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/api-guide.md"
content_sha256: fae505c4b98c8250e0baf29aa08edd046ace338695d5c5dcf0921b461114788a
---

> Part 2 of 2 of **API Guide** — Example: custom pipeline script.

## Example: custom pipeline script

A script that syncs sessions, builds the site, and exports all formats:

```python
#!/usr/bin/env python3
"""Custom llmwiki pipeline."""

from pathlib import Path
from llmwiki.convert import convert_all
from llmwiki.build import build_site, discover_sources, group_by_project, RAW_SESSIONS
from llmwiki.exporters import export_all

# Step 1: sync new sessions
print("Syncing sessions...")
convert_all(since="2026-01-01")

# Step 2: build the site
print("Building site...")
out_dir = Path("site")
build_site(out_dir=out_dir)

# Step 3: export AI-consumable formats
print("Exporting...")
sources = discover_sources(RAW_SESSIONS)
if sources:
    groups = group_by_project(sources)
    paths = export_all(out_dir, groups, sources)
    for name, path in sorted(paths.items()):
        print(f"  {name}: {path}")

print("Done.")
```

## Example: adapter introspection

A script that reports on all detected agents and their session counts:

```python
#!/usr/bin/env python3
"""Report on detected coding agents."""

from llmwiki.adapters import discover_adapters, REGISTRY

discover_adapters()

for name, cls in sorted(REGISTRY.items()):
    available = cls.is_available()
    if available:
        adapter = cls()
        sessions = adapter.discover_sessions()
        print(f"{name}: {len(sessions)} sessions")
    else:
        print(f"{name}: not installed")
```

## Notes

- All public functions are importable from their module paths.
- No function requires network access (except `image_pipeline.process_markdown_images` with `--download-images`).
- `convert_all` is idempotent -- state is tracked in `llmwiki-state.json` (active path from `configure_state_file` / `resolve_state_file`).
- `build_site` is deterministic -- the same inputs produce the same outputs.
- Content root comes from `vault.default_path` in `config.json` (CLI) or an explicit `state_file=` / vault path. The removed `LLMWIKI_ROOT` env var is no longer read.
