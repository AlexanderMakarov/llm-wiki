# API Guide

Using llmwiki as a Python library in your own scripts and pipelines.

## Public API

The `llmwiki` package exposes several functions that can be imported directly:

```python
from llmwiki.convert import convert_all
from llmwiki.build import build_site
from llmwiki.serve import serve_site
from llmwiki.graph import build_and_report
from llmwiki.exporters import export_all
from llmwiki.adapters import REGISTRY, discover_adapters
```

## Core functions

### `convert_all()` -- sync agent sessions to markdown

```python
from llmwiki.convert import convert_all

rc = convert_all(
    adapters=None,         # list[str] | None -- adapter names; None = all available
    since=None,            # str | None -- "YYYY-MM-DD" cutoff date
    project=None,          # str | None -- substring filter on project slug
    include_current=False, # bool -- include live sessions (< 60 min old)
    force=False,           # bool -- ignore state file, reconvert everything
    dry_run=False,         # bool -- preview without writing
)
# Returns: 0 on success, non-zero on error
```

This is the programmatic equivalent of `llmwiki sync`. It discovers agent session stores, converts `.jsonl` files to markdown, and writes them under `raw/sessions/`.

### `build_site()` -- compile HTML from markdown

```python
from llmwiki.build import build_site
from pathlib import Path

rc = build_site(
    out_dir=Path("site"),           # Path -- output directory
    synthesize=False,               # bool -- call claude CLI for overview
    claude_path="/usr/local/bin/claude",  # str -- path to claude binary
)
# Returns: 0 on success, non-zero on error
```

Reads `raw/` (and `wiki/` if populated) and renders a complete static HTML site. Equivalent to `llmwiki build`.

### `serve_site()` -- start local HTTP server

```python
from llmwiki.serve import serve_site
from pathlib import Path

rc = serve_site(
    directory=Path("site"),  # Path -- directory to serve
    port=8765,               # int -- port number
    host="127.0.0.1",       # str -- host to bind
    open_browser=False,      # bool -- open browser after starting
)
# Returns: 0 on success, non-zero on error
```

Starts a local HTTP server using Python's stdlib `http.server`. Binds to localhost by default.

### `build_and_report()` -- knowledge graph

```python
from llmwiki.graph import build_and_report

rc = build_and_report(
    write_json_flag=True,  # bool -- write graph/graph.json
    write_html_flag=True,  # bool -- write graph/graph.html
)
# Returns: 0 on success
```

Walks `[[wikilinks]]` in `wiki/` and produces a JSON graph and/or an interactive HTML visualization.

### `export_all()` -- AI-consumable exports

```python
from llmwiki.exporters import export_all
from llmwiki.build import discover_sources, group_by_project, RAW_SESSIONS
from pathlib import Path

sources = discover_sources(RAW_SESSIONS)
groups = group_by_project(sources)
out_dir = Path("site")

paths = export_all(out_dir, groups, sources)
# Returns: dict[str, Path] -- format name -> output file path
```

Generates all export formats: `llms.txt`, `llms-full.txt`, JSON-LD, sitemap, RSS, robots.txt, AI-README.

## Adapter registry

### Discovering adapters

```python
from llmwiki.adapters import REGISTRY, discover_adapters, get_available

# Import all built-in adapters
discover_adapters()

# All registered adapters (available or not)
for name, cls in REGISTRY.items():
    print(f"{name}: available={cls.is_available()}")

# Only available adapters
available = get_available()
```

### Using an adapter directly

```python
from llmwiki.adapters import discover_adapters, REGISTRY

discover_adapters()
adapter_cls = REGISTRY["claude_code"]
adapter = adapter_cls()

# List all session files
sessions = adapter.discover_sessions()
for path in sessions:
    slug = adapter.derive_project_slug(path)
    print(f"{slug}: {path}")
```

## Helper modules

### Source discovery

```python
from llmwiki.build import discover_sources, group_by_project, RAW_SESSIONS

# Find all .md files under raw/sessions/
sources = discover_sources(RAW_SESSIONS)

# Group by project slug
groups = group_by_project(sources)
for project, project_sources in groups.items():
    print(f"{project}: {len(project_sources)} sessions")
```

### Render visualizations

```python
from llmwiki.viz_heatmap import render_heatmap, collect_session_counts
from llmwiki.viz_tools import render_session_tool_chart
from llmwiki.viz_tokens import render_session_token_card

# Heatmap SVG
counts = collect_session_counts(raw_dir=Path("raw/sessions"))
svg = render_heatmap(counts)

# Tool chart SVG (from frontmatter tools_used dict)
svg = render_session_tool_chart({"Read": 45, "Edit": 30, "Bash": 25, "Grep": 15})

# Token card SVG (from frontmatter token counts)
svg = render_session_token_card({
    "input": 50000,
    "cache_creation": 10000,
    "cache_read": 35000,
    "output": 8000,
})
```

### Freshness checks

```python
from llmwiki.freshness import freshness_badge, load_freshness_config

config = load_freshness_config()
badge = freshness_badge("2026-04-01", config)
# Returns an HTML badge string indicating staleness
```

### Model discovery

```python
from llmwiki.models_page import discover_model_entities, discover_model_entities_with_meta

# Find model entity pages in wiki/entities/
models = discover_model_entities()

# With metadata extraction
models_with_meta = discover_model_entities_with_meta()
```

### Project topics

```python
from llmwiki.project_topics import get_project_topics, load_project_profile

topics = get_project_topics("my-project")
# Returns: list of topic strings

profile = load_project_profile("my-project")
# Returns: dict with project metadata
```

### Model schema

```python
from llmwiki.schema import parse_model_profile, ModelProfile

profile = parse_model_profile(frontmatter_dict)
if profile:
    print(f"Provider: {profile['provider']}")
    print(f"Context: {profile['context_window']}")
```

### Export to qmd

```python
from llmwiki.export_qmd import export_qmd

summary = export_qmd(
    out_dir=Path("export/qmd"),
    source_wiki=Path("wiki"),
    collection_name="my-wiki",
)
print(f"Copied {summary['files_copied']} files")
```

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
- `convert_all` is idempotent -- state is tracked in `.llmwiki-state.json`.
- `build_site` is deterministic -- the same inputs produce the same outputs.
- All functions use the repo root auto-detected from the package location. Override with `LLMWIKI_ROOT`.
