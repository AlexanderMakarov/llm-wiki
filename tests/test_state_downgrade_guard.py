"""Guard against silent full-reconvert on downgrade / corrupt state (#29).

A sync must never treat a present-but-unreadable state file (or a state
file written by a *newer* schema) as "empty" and reconvert the whole
corpus. It has to hard-stop with a clear message; the only escape hatch
is an explicit ``--force-resync``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki.state_store import (
    SCHEMA_VERSION,
    IncompatibleStateError,
    check_sync_state_compatible,
    default_state,
    state_incompatibility_reason,
    write_state,
)


# --- the pure predicate -------------------------------------------------

def test_missing_state_is_compatible():
    # No file at all == a fresh vault; a first full convert is legitimate.
    assert state_incompatibility_reason(None) is None


def test_current_schema_is_compatible():
    text = json.dumps(default_state())
    assert state_incompatibility_reason(text) is None


def test_corrupt_json_is_incompatible():
    reason = state_incompatibility_reason("{ this is not json")
    assert reason is not None
    assert reason  # non-empty human-readable message


def test_non_dict_json_is_incompatible():
    # A JSON array parses fine but is not a state object.
    assert state_incompatibility_reason("[]") is not None


def test_empty_file_is_compatible():
    # An empty / whitespace-only file has no data to lose (touched artifact,
    # interrupted first write) — don't block a genuine first sync on it.
    assert state_incompatibility_reason("") is None
    assert state_incompatibility_reason("   \n") is None


def test_newer_schema_version_is_incompatible():
    state = default_state()
    state["meta"]["schema_version"] = SCHEMA_VERSION + 1
    reason = state_incompatibility_reason(json.dumps(state))
    assert reason is not None


def test_float_newer_schema_version_is_incompatible():
    # A JSON number like 2.0 deserializes to float — must still block.
    reason = state_incompatibility_reason(
        json.dumps({"meta": {"schema_version": float(SCHEMA_VERSION + 1)}})
    )
    assert reason is not None


def test_non_numeric_schema_version_is_incompatible():
    # A present-but-non-numeric version means a foreign/unknown format:
    # fail closed rather than silently reconverting.
    reason = state_incompatibility_reason(
        json.dumps({"meta": {"schema_version": "brand-new"}})
    )
    assert reason is not None


def test_bool_schema_version_is_compatible():
    # bool is an int subclass but never a real version — don't spuriously block.
    assert state_incompatibility_reason(
        json.dumps({"meta": {"schema_version": True}})
    ) is None


def test_meta_not_a_dict_is_compatible():
    # A legacy/odd state whose meta isn't a dict has no version to trust;
    # treat as older/compatible (reconcilable), not a hard stop.
    assert state_incompatibility_reason(
        json.dumps({"meta": "oops", "sync": {"files": {}}})
    ) is None


# --- the guard used at the sync border ---------------------------------

def test_guard_passes_for_missing_file(tmp_path: Path):
    # Should not raise: nothing to protect.
    check_sync_state_compatible(tmp_path / "llmwiki-state.json")


def test_guard_passes_for_current_state(tmp_path: Path):
    state_file = tmp_path / "llmwiki-state.json"
    write_state(default_state(), state_file)
    check_sync_state_compatible(state_file)


def test_guard_raises_on_newer_schema(tmp_path: Path):
    state_file = tmp_path / "llmwiki-state.json"
    state = default_state()
    state["meta"]["schema_version"] = SCHEMA_VERSION + 1
    state_file.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(IncompatibleStateError):
        check_sync_state_compatible(state_file)


def test_guard_raises_on_corrupt_state(tmp_path: Path):
    state_file = tmp_path / "llmwiki-state.json"
    state_file.write_text("{ half-written", encoding="utf-8")
    with pytest.raises(IncompatibleStateError):
        check_sync_state_compatible(state_file)


def test_force_resync_bypasses_guard(tmp_path: Path):
    state_file = tmp_path / "llmwiki-state.json"
    state_file.write_text("{ half-written", encoding="utf-8")
    # Explicit override: user accepts the full reconvert.
    check_sync_state_compatible(state_file, force_resync=True)


def test_guard_raises_on_unreadable_file(tmp_path: Path, monkeypatch):
    # Present but unreadable (permission/IO error) must hard-stop, not
    # fall through to an empty state.
    state_file = tmp_path / "llmwiki-state.json"
    state_file.write_text("{}", encoding="utf-8")
    orig_read_text = Path.read_text

    def boom(self, *args, **kwargs):
        if self.name == "llmwiki-state.json":
            raise OSError("permission denied")
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", boom)
    with pytest.raises(IncompatibleStateError):
        check_sync_state_compatible(state_file)
