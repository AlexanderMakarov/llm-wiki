"""Queue dispatch table is the single source of truth for task types (#23).

Producers (CLI, migration script) may only emit task types the consumer
(``_run_one``) can actually handle. ``enqueue_task`` validates against
``TASK_HANDLERS`` so drift fails fast at enqueue time instead of turning
into permanently-unprocessable ``status: error`` items on the first
``llmwiki queue run``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llmwiki import queue_ops
from llmwiki.queue_ops import TASK_HANDLERS, enqueue_task, _run_one
from llmwiki.state_store import read_state


REPO = Path(__file__).resolve().parents[1]

# Tracking-only rows the ``llmwiki add`` command writes directly into the
# queue for observability. They never carry ``status: pending``, so the
# runner never picks them up and they need no handler.
TRACKING_ONLY_TASK_TYPES = {"add_doc_sync"}


def test_dispatch_table_covers_expected_types():
    assert set(TASK_HANDLERS) == {"add_doc", "session_sync", "synthesize", "build"}


def test_enqueue_rejects_unknown_task_type(tmp_path: Path):
    state = tmp_path / "llmwiki-state.json"
    with pytest.raises(ValueError) as exc:
        enqueue_task("synth_request", {}, state)
    msg = str(exc.value)
    assert "synth_request" in msg
    for known in TASK_HANDLERS:
        assert known in msg
    assert not state.exists()


def test_enqueue_accepts_known_task_types(tmp_path: Path):
    state = tmp_path / "llmwiki-state.json"
    for name in TASK_HANDLERS:
        enqueue_task(name, {}, state)
    items = read_state(state)["queue"]["items"]
    assert {row["task_type"] for row in items} == set(TASK_HANDLERS)


def test_run_one_rejects_unknown_task_type(tmp_path: Path):
    with pytest.raises(RuntimeError, match="unknown task_type"):
        _run_one({"task_type": "synth_request", "payload": {}}, tmp_path)


# ─── producer/consumer contract ────────────────────────────────────────


def _emitted_task_types() -> set[str]:
    """Every task_type literal any producer in the tree can write."""
    found: set[str] = set()
    roots = [REPO / "llmwiki", REPO / "scripts"]
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            found.update(re.findall(r'"task_type":\s*"([a-z_]+)"', text))
            found.update(re.findall(r'enqueue_task\(\s*"([a-z_]+)"', text))
            # CLI --task-type choices list
            for block in re.findall(r'"--task-type".*?choices=\[([^\]]+)\]', text):
                found.update(re.findall(r'"([a-z_]+)"', block))
    return found


def test_every_producible_task_type_has_a_handler():
    emitted = _emitted_task_types() - TRACKING_ONLY_TASK_TYPES
    unhandled = emitted - set(TASK_HANDLERS)
    assert not unhandled, f"producers emit task types with no handler: {sorted(unhandled)}"


def test_migration_does_not_emit_synth_request():
    text = (REPO / "scripts" / "migrate_state_v1_4_0.py").read_text(encoding="utf-8")
    assert '"task_type": "synth_request"' not in text


# ─── synthesize handler payload (#23) ──────────────────────────────────


def test_synthesize_handler_passes_payload(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    class _Backend:
        name = "fake"

        def is_available(self) -> bool:
            return True

    def _fake_synth(**kwargs):
        calls.update(kwargs)
        return {"synthesized": 2, "errors": []}

    monkeypatch.setattr(queue_ops, "resolve_backend", lambda cfg: _Backend())
    monkeypatch.setattr(queue_ops, "synthesize_new_sessions", _fake_synth)

    result = _run_one(
        {
            "task_type": "synthesize",
            "payload": {"paths": ["raw/sessions/a.md"], "force": True},
        },
        tmp_path,
    )
    assert "2" in result
    assert calls["only_paths"] == {"raw/sessions/a.md"}
    assert calls["force"] is True


def test_synthesize_handler_without_payload_drains_backlog(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    class _Backend:
        name = "fake"

        def is_available(self) -> bool:
            return True

    def _fake_synth(**kwargs):
        calls.update(kwargs)
        return {"synthesized": 0, "errors": []}

    monkeypatch.setattr(queue_ops, "resolve_backend", lambda cfg: _Backend())
    monkeypatch.setattr(queue_ops, "synthesize_new_sessions", _fake_synth)

    _run_one({"task_type": "synthesize", "payload": {}}, tmp_path)
    assert calls["only_paths"] is None
    assert calls["force"] is False
