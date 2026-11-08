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

**Do not build default paths at import time.** Evaluating `Path.home()` when the module loads freezes the developer's real home directory — the test suite points `HOME` at an isolated directory per test (`settings_sandbox`, #367), so defaults must be resolved **when used** (a `default_roots()` / `default_session_store_path()` classmethod, or equivalent) so that sandbox applies.

```python
from pathlib import Path

# Good: resolve at call time (single dot-dir store)
@classmethod
def default_session_store_path(cls) -> Path:
    return Path.home() / ".myagent" / "sessions"

@property
def session_store_path(self) -> Path:  # type: ignore[override]
    return self.default_session_store_path()

# Good: multiple platform-specific defaults as a classmethod
@classmethod
def default_roots(cls) -> list[Path]:
    return [
        Path.home() / ".myagent",                         # macOS / Linux
        Path.home() / ".config" / "myagent",              # Linux (XDG)
        Path.home() / "AppData" / "Roaming" / "myagent",  # Windows
    ]

# Good: environment variable override evaluated in the same helper
import os

@classmethod
def default_roots(cls) -> list[Path]:
    roots = [
        Path.home() / ".myagent" / "sessions",
        Path.home() / ".config" / "myagent" / "sessions",
    ]
    custom = os.environ.get("MYAGENT_HOME")
    if custom:
        roots.append(Path(custom).expanduser() / "sessions")
    return roots
```

Never hardcode `/Users/` or `C:\Users\`. Always use `Path.home()` inside those call-time helpers, not in a module-level constant.

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

    @classmethod
    def default_roots(cls) -> list[Path]:
        return [
            Path.home() / ".myagent" / "sessions",
            Path.home() / ".config" / "myagent" / "sessions",
        ]

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        ad_cfg = (config or {}).get("adapters", {}).get("myagent", {})
        paths = ad_cfg.get("roots") or []
        self.roots: list[Path] = (
            [Path(p).expanduser() for p in paths] if paths else list(self.default_roots())
        )

    @property
    def session_store_path(self):  # type: ignore[override]
        return self.roots

    # Prefer inheriting BaseAdapter.is_available() — it instantiates and reads
    # self.session_store_path. Override only for env-var edge cases (see copilot_cli).

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

## Testing

Every adapter needs three kinds of tests:

### 1. Fixture test

Create a fixture file at `tests/fixtures/<agent>/sample.jsonl` with representative session data. Test that `discover_sessions()` finds it and `derive_project_slug()` returns the expected slug.

### 2. Snapshot test

Test that `normalize_records()` produces the expected output for known input. Store the expected output as a JSON fixture and compare against it.

### 3. Graceful degradation test

Test that the adapter handles:
- Missing session store (returns empty list, not an error)
- Corrupt JSONL lines (skips them, does not crash)
- Unknown record types (skips them)
- Empty files (returns empty list)

Example test structure:

```python
from pathlib import Path
from llmwiki.adapters.myagent import MyAgentAdapter


def test_is_available_when_missing(tmp_path):
    """Adapter reports unavailable when the store doesn't exist."""
    adapter = MyAgentAdapter()
    # With a non-existent path, should be no sessions
    assert adapter.discover_sessions() == [] or not adapter.is_available()


def test_discover_sessions(tmp_path):
    """Finds .jsonl files under the session store."""
    store = tmp_path / "sessions"
    store.mkdir()
    (store / "project-a").mkdir()
    (store / "project-a" / "session.jsonl").write_text('{"type":"init"}\n')

    adapter = MyAgentAdapter({"adapters": {"myagent": {"roots": [str(store)]}}})
    sessions = adapter.discover_sessions()
    assert len(sessions) == 1
    assert sessions[0].name == "session.jsonl"


def test_derive_project_slug(tmp_path):
    store = tmp_path / "sessions"
    (store / "my-project").mkdir(parents=True)
    f = store / "my-project" / "session.jsonl"
    f.touch()

    adapter = MyAgentAdapter({"adapters": {"myagent": {"roots": [str(store)]}}})
    assert adapter.derive_project_slug(f) == "my-project"
```

## Checklist before PR

- [ ] Adapter module created at `llmwiki/adapters/<name>.py`
- [ ] `@register("<name>")` decorator applied
- [ ] Import added to `discover_adapters()` in `llmwiki/adapters/__init__.py`
- [ ] `session_store_path` covers macOS, Linux, and Windows
- [ ] `is_available()` returns `False` gracefully when the agent is not installed
- [ ] `normalize_records()` implemented if the schema differs from Claude Code
- [ ] Test file at `tests/test_adapter_<name>.py` with fixture, snapshot, and degradation tests
- [ ] Fixture file at `tests/fixtures/<name>/sample.jsonl`
- [ ] `llmwiki adapters` shows the new adapter with correct description
- [ ] Documentation updated in `docs/multi-agent-setup.md`
