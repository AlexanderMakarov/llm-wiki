"""Migration to unified state v1.4.0 (#23).

``migrate-state`` must not enqueue task types the queue runner cannot
dispatch. Legacy ``.llmwiki-pending-prompts/<uuid>.md`` files are resolved
against the sentinel pages still sitting in ``wiki/sources/``; the backlog
is drained by exactly one ``synthesize`` task. Vaults migrated with the
buggy version carry dead ``synth_request`` items — re-running the migration
purges them.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from llmwiki.state_store import default_state, read_state, write_state

REPO = Path(__file__).resolve().parents[1]


def _load_migrator():
    script = REPO / "scripts" / "migrate_state_v1_4_0.py"
    spec = importlib.util.spec_from_file_location("migrate_state_v1_4_0", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RAW_SESSION = """---
title: "Session: alpha — 2026-04-09"
type: source
tags: [claude-code]
date: 2026-04-09
slug: alpha
project: proj
---

# Session: alpha
"""

SENTINEL_PAGE = """---
title: "Session: alpha — 2026-04-09"
type: source
tags: [claude-code]
date: 2026-04-09
source_file: raw/sessions/proj/2026-04-09-alpha.md
project: proj
---

<!-- llmwiki-pending: aaaa-1111 -->

*Pending agent synthesis.*
"""

REAL_PAGE = """---
title: "Session: alpha — 2026-04-09"
type: source
tags: [claude-code]
date: 2026-04-09
source_file: raw/sessions/proj/2026-04-09-alpha.md
project: proj
---

## Summary

A real synthesis.

## Connections

- [[ProjectAlpha]]
"""


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    (tmp_path / "raw" / "sessions" / "proj").mkdir(parents=True)
    (tmp_path / "raw" / "sessions" / "proj" / "2026-04-09-alpha.md").write_text(
        RAW_SESSION, encoding="utf-8"
    )
    (tmp_path / "wiki" / "sources" / "proj").mkdir(parents=True)
    return tmp_path


def _state_file(vault: Path) -> Path:
    return vault / "llmwiki-state.json"


def _page(vault: Path) -> Path:
    return vault / "wiki" / "sources" / "proj" / "2026-04-09-alpha.md"


def _prompt(vault: Path, uuid: str) -> Path:
    d = vault / ".llmwiki-pending-prompts"
    d.mkdir(exist_ok=True)
    p = d / f"{uuid}.md"
    p.write_text("synthesize me\n", encoding="utf-8")
    return p


# ─── prompt resolution ─────────────────────────────────────────────────


def test_unfilled_prompt_is_reported_and_filled_one_is_not(vault: Path):
    _page(vault).write_text(SENTINEL_PAGE, encoding="utf-8")  # uuid aaaa-1111
    _prompt(vault, "aaaa-1111")
    _prompt(vault, "bbbb-2222")  # no sentinel page left → already fulfilled

    report = _load_migrator().run_migration(_state_file(vault))

    assert report["pending_prompts_total"] == 2
    assert report["pending_prompts_unfilled"] == 1
    items = read_state(_state_file(vault))["queue"]["items"]
    assert not [r for r in items if r.get("task_type") == "synth_request"]


def test_migration_enqueues_exactly_one_synthesize_when_backlog_exists(vault: Path):
    _page(vault).write_text(SENTINEL_PAGE, encoding="utf-8")
    _prompt(vault, "aaaa-1111")
    _prompt(vault, "cccc-3333")

    report = _load_migrator().run_migration(_state_file(vault))

    state = read_state(_state_file(vault))
    assert state["synth"]["pending_total"] == 1
    synth_tasks = [r for r in state["queue"]["items"] if r.get("task_type") == "synthesize"]
    assert len(synth_tasks) == 1
    assert synth_tasks[0]["status"] == "pending"
    assert report["queued_synthesize"] == 1


def test_rerunning_migration_does_not_stack_synthesize_tasks(vault: Path):
    _page(vault).write_text(SENTINEL_PAGE, encoding="utf-8")
    _prompt(vault, "aaaa-1111")
    mod = _load_migrator()

    mod.run_migration(_state_file(vault))
    report = mod.run_migration(_state_file(vault))

    items = read_state(_state_file(vault))["queue"]["items"]
    assert len([r for r in items if r.get("task_type") == "synthesize"]) == 1
    assert report["queued_synthesize"] == 0


def test_migration_enqueues_nothing_when_backlog_empty(vault: Path):
    _page(vault).write_text(REAL_PAGE, encoding="utf-8")
    _prompt(vault, "aaaa-1111")

    report = _load_migrator().run_migration(_state_file(vault))

    state = read_state(_state_file(vault))
    assert state["synth"]["pending_total"] == 0
    assert state["queue"]["items"] == []
    assert report["queued_synthesize"] == 0
    assert report["pending_prompts_unfilled"] == 0


# ─── purge of dead synth_request items ─────────────────────────────────


def test_migration_purges_existing_synth_request_items(vault: Path):
    _page(vault).write_text(REAL_PAGE, encoding="utf-8")
    state = default_state()
    state["queue"]["items"] = [
        {"id": "dead-1", "task_type": "synth_request", "status": "error"},
        {"id": "dead-2", "task_type": "synth_request", "status": "pending"},
        {"id": "keep", "task_type": "build", "status": "done"},
    ]
    write_state(state, _state_file(vault))

    report = _load_migrator().run_migration(_state_file(vault))

    items = read_state(_state_file(vault))["queue"]["items"]
    assert [r["id"] for r in items] == ["keep"]
    assert report["synth_request_items_purged"] == 2


# ─── removed backend warning ───────────────────────────────────────────


def _write_config(vault: Path, backend: str) -> None:
    (vault / "config.json").write_text(
        json.dumps({"synthesis": {"backend": backend}}), encoding="utf-8"
    )


@pytest.mark.parametrize("backend", ["agent", "agent-delegate", "agent_delegate", "Agent-Delegate"])
def test_removed_backend_is_warned(vault: Path, backend: str):
    _write_config(vault, backend)
    report = _load_migrator().run_migration(_state_file(vault))
    warnings = report["warnings"]
    assert len(warnings) == 1
    assert backend in warnings[0]
    assert "claude" in warnings[0] and "ollama" in warnings[0] and "dummy" in warnings[0]


@pytest.mark.parametrize("backend", ["claude", "ollama", "dummy"])
def test_supported_backend_is_not_warned(vault: Path, backend: str):
    _write_config(vault, backend)
    report = _load_migrator().run_migration(_state_file(vault))
    assert report["warnings"] == []
