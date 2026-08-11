---
title: "Writing a New Adapter (part 2/2: Testing)"
slug: writing-a-new-adapter-02
project: writing-a-new-adapter
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/adapter-authoring.md"
content_sha256: bc99a2e401bcc61d5739a6ce3d53ee80b19d069b4d18416c8e1424d3a361816a
---

> Part 2 of 2 of **Writing a New Adapter** — Testing.

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
