---
title: "Writing a New Adapter (part 1/2)"
slug: writing-a-new-adapter-01
project: writing-a-new-adapter
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/adapter-authoring.md"
content_sha256: bc99a2e401bcc61d5739a6ce3d53ee80b19d069b4d18416c8e1424d3a361816a
---

> Part 1 of 2 of **Writing a New Adapter**.

# Writing a New Adapter

This guide walks you through adding support for a new coding agent to llmwiki.

## The BaseAdapter contract

Every adapter extends `llmwiki.adapters.base.BaseAdapter` and must provide:

### Required

| Attribute/Method | Purpose |
|---|---|
| `session_store_path` | `Path` or `list[Path]` where this agent writes session transcripts |
| `SUPPORTED_SCHEMA_VERSIONS` | List of schema version strings this adapter understands |
| `is_available()` (classmethod) | Returns `True` if the session store exists on this machine |

### Optional overrides

| Method | Default behavior | Override when... |
|---|---|---|
| `discover_sessions()` | Recursive glob for `*.jsonl` under `session_store_path` | Your agent uses a different extension or layout |
| `derive_project_slug(path)` | Parent directory name under the store | Your agent encodes project info differently |
| `normalize_records(records)` | No-op pass-through | Your agent's JSONL schema differs from Claude Code's |
| `is_subagent(path)` | Checks for "subagent" in path | Your agent has a different sub-agent layout |
| `description()` | First line of the class docstring | You want a custom description for `llmwiki adapters` |

## Cross-platform path requirements

Adapters must work on macOS, Linux, and Windows. Use these patterns:

```python
from pathlib import Path

# Good: resolves ~ on all platforms
Path.home() / ".myagent" / "sessions"

# Good: check multiple platform-specific paths
DEFAULT_ROOTS = [
    Path.home() / ".myagent",                                    # macOS / Linux
    Path.home() / ".config" / "myagent",                         # Linux (XDG)
    Path.home() / "AppData" / "Roaming" / "myagent",             # Windows
]

# Good: environment variable override
import os
custom = os.environ.get("MYAGENT_HOME")
if custom:
    roots.append(Path(custom).expanduser() / "sessions")
```

Never hardcode `/Users/` or `C:\Users\`. Always use `Path.home()`.

## Registration via @register

Adapters register themselves using the `@register` decorator:

```python
from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter

@register("myagent")
class MyAgentAdapter(BaseAdapter):
    """MyAgent — reads ~/.myagent/sessions/*.jsonl"""
    ...
```

Then add the import to `llmwiki/adapters/__init__.py` in `discover_adapters()`:

```python
def discover_adapters() -> None:
    from llmwiki.adapters import claude_code   # noqa: F401
    from llmwiki.adapters import codex_cli     # noqa: F401
    # ... existing adapters ...
    from llmwiki.adapters import myagent       # noqa: F401
```

## Example: minimal adapter skeleton

```python
"""MyAgent adapter.

Reads session transcripts from MyAgent's local session store.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter


@register("myagent")
class MyAgentAdapter(BaseAdapter):
    """MyAgent — reads ~/.myagent/sessions/**/*.jsonl"""

    SUPPORTED_SCHEMA_VERSIONS = ["v1"]

    DEFAULT_ROOTS = [
        Path.home() / ".myagent" / "sessions",
        Path.home() / ".config" / "myagent" / "sessions",
    ]

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        ad_cfg = (config or {}).get("adapters", {}).get("myagent", {})
        paths = ad_cfg.get("roots") or []
        self.roots: list[Path] = (
            [Path(p).expanduser() for p in paths] if paths else self.DEFAULT_ROOTS
        )

    @property
    def session_store_path(self):  # type: ignore[override]
        return self.roots

    @classmethod
    def is_available(cls) -> bool:
        for p in cls.DEFAULT_ROOTS:
            if Path(p).expanduser().exists():
                return True
        return False

    def discover_sessions(self) -> list[Path]:
        out: list[Path] = []
        for root in self.roots:
            root = Path(root).expanduser()
            if root.exists():
                out.extend(sorted(root.rglob("*.jsonl")))
        # Dedupe
        seen: set[Path] = set()
        return [p for p in out if not (p in seen or seen.add(p))]

    def derive_project_slug(self, path: Path) -> str:
        for root in self.roots:
            root = Path(root).expanduser()
            try:
                rel = path.relative_to(root)
                if rel.parts:
                    return rel.parts[0]
            except ValueError:
                continue
        return path.parent.name

    def normalize_records(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Convert MyAgent's native records into the shared Claude-style format.

        The shared renderer expects:
        - {"type": "user", "message": {"role": "user", "content": "..."}}
        - {"type": "assistant", "message": {"role": "assistant", "content": [...]}}
        """
        out: list[dict[str, Any]] = []
        for r in records:
            # Map your agent's record types here
            rtype = r.get("type", "")
            if rtype == "user_message":
                out.append({
                    "type": "user",
                    "message": {"role": "user", "content": r.get("text", "")},
                    "timestamp": r.get("timestamp", ""),
                })
            elif rtype == "assistant_message":
                out.append({
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": r.get("text", "")}],
                    },
                    "timestamp": r.get("timestamp", ""),
                })
            # Skip unknown types gracefully
        return out
```
