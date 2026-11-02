"""Latest outcome per pipeline part, stored for the Home problems banner.

# @spec: 374-no-silent-automation-failure
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki import run_outcomes
from llmwiki.run_outcomes import Failure
from llmwiki.state_store import read_state, update_state
from llmwiki.synth.base import BaseSynthesizer, backend_unavailable_message
from llmwiki.synth.claude_cli import ClaudeCLISynthesizer
from llmwiki.synth.cursor_cli import CursorCLISynthesizer
from llmwiki.synth.ollama import OllamaConfig, OllamaSynthesizer


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "site").mkdir(parents=True)
    return root


def _site_snapshot(vault: Path) -> dict:
    text = (vault / "site" / "llmwiki-state.js").read_text(encoding="utf-8")
    return json.loads(text.split("=", 1)[1].rstrip().rstrip(";"))


def test_a_failure_reaches_the_site_sidecar_without_a_build(vault: Path):
    state_file = vault / "llmwiki-state.json"
    run_outcomes.record_failure(
        "synth", Failure(scope="entire", summary="did not run: x", detail="boom"),
        state_file=state_file, when="2026-10-31T05:02:00Z",
    )
    entry = _site_snapshot(vault)["outcomes"]["parts"]["synth"]
    assert entry["scope"] == "entire"
    assert entry["summary"] == "did not run: x"
    assert entry["detail"] == "boom"
    assert entry["at"] == "2026-10-31T05:02:00Z"


def test_a_clean_finish_removes_only_that_part(vault: Path):
    state_file = vault / "llmwiki-state.json"
    for part in ("sync", "build"):
        run_outcomes.record_failure(
            part, Failure(scope="entire", summary="failed"), state_file=state_file,
        )
    run_outcomes.record_clean("sync", state_file=state_file)
    assert set(_site_snapshot(vault)["outcomes"]["parts"]) == {"build"}


def test_a_clean_finish_with_nothing_recorded_does_not_write(vault: Path):
    state_file = vault / "llmwiki-state.json"
    update_state(lambda s: s, state_file)
    before = read_state(state_file)["meta"]["revision"]
    run_outcomes.record_clean("synth", state_file=state_file)
    assert read_state(state_file)["meta"]["revision"] == before


def test_long_detail_is_capped_before_it_is_stored(vault: Path):
    state_file = vault / "llmwiki-state.json"
    run_outcomes.record_failure(
        "build", Failure(scope="entire", summary="failed", detail="x" * 20_000),
        state_file=state_file,
    )
    detail = read_state(state_file)["outcomes"]["parts"]["build"]["detail"]
    assert len(detail) <= run_outcomes.DETAIL_MAX_CHARS + 2
    assert detail.endswith("…")


def test_scheduled_runs_point_at_the_job_log_manual_runs_do_not(vault: Path, monkeypatch):
    state_file = vault / "llmwiki-state.json"
    run_outcomes.record_failure("build", Failure(scope="entire", summary="failed"), state_file=state_file)
    assert read_state(state_file)["outcomes"]["parts"]["build"]["log_path"] == ""
    monkeypatch.setenv(run_outcomes.SCHEDULED_ENV, "1")
    run_outcomes.record_failure("build", Failure(scope="entire", summary="failed"), state_file=state_file)
    log_path = read_state(state_file)["outcomes"]["parts"]["build"]["log_path"]
    assert log_path == str(vault / ".llmwiki" / "last-automation.log")


def test_state_writes_keep_outcomes_and_drop_malformed_entries(vault: Path):
    state_file = vault / "llmwiki-state.json"

    def _mut(state: dict) -> dict:
        state["outcomes"] = {
            "parts": {
                "synth": {"scope": "partial", "summary": "1 of 2 sources failed"},
                "sync": {"scope": "sometimes", "summary": "?"},
                "build": "failed",
            },
            "scheduled": {"interval_s": 86400},
            "junk": [1],
        }
        return state

    update_state(_mut, state_file)
    outcomes = read_state(state_file)["outcomes"]
    assert outcomes == {
        "parts": {"synth": {"scope": "partial", "summary": "1 of 2 sources failed"}},
        "scheduled": {"interval_s": 86400},
    }


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        ({"synthesized": 6, "errors": [], "deferred": 0}, None),
        (
            {"synthesized": 6, "errors": ["doc-a: 'float' object has no attribute 'strip'"], "deferred": 0},
            ("partial", "1 of 7 sources failed", ("doc-a",)),
        ),
        (
            {"synthesized": 5, "errors": [], "deferred": 7, "usage_limit": {"reset": "10:00"}},
            ("partial", "stopped at the AI provider's usage limit after 5 of 12 sources", ()),
        ),
        (
            {"synthesized": 2, "errors": [], "deferred": 3, "interrupted": True},
            ("partial", "interrupted after 2 of 5 sources", ()),
        ),
    ],
    ids=["clean", "one-source-failed", "usage-limit", "interrupted"],
)
def test_synth_summary_is_classified_by_how_much_landed(summary, expected):
    failure = run_outcomes.synth_failure(summary)
    if expected is None:
        assert failure is None
        return
    scope, text, items = expected
    assert (failure.scope, failure.summary, failure.items) == (scope, text, items)


def test_usage_limit_detail_says_when_it_resets():
    failure = run_outcomes.synth_failure(
        {"synthesized": 0, "errors": [], "deferred": 3, "usage_limit": {"reset": "10:00"}}
    )
    assert "resets 10:00" in failure.detail


def test_unavailable_backend_is_an_entire_failure_naming_the_reason():
    backend = ClaudeCLISynthesizer(claude_path="/gone/versions/2.1.309")
    failure = run_outcomes.synth_unavailable(backend)
    assert failure.scope == "entire"
    assert failure.summary == "did not run: backend claude-cli is not available"
    assert failure.detail == (
        "backend claude-cli is not available: /gone/versions/2.1.309 does not exist — "
        "point synthesis.claude.path at the claude launcher (e.g. ~/.local/bin/claude) or remove it"
    )


def test_claude_not_on_path_names_the_fix(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    assert ClaudeCLISynthesizer().unavailable_reason() == (
        "claude was not found on PATH — install Claude Code or set synthesis.claude.path"
    )


def test_cursor_agent_not_on_path_names_the_fix(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    assert CursorCLISynthesizer().unavailable_reason().startswith(
        "neither agent nor cursor-agent was found on PATH"
    )


def test_ollama_names_the_server_it_could_not_reach():
    backend = OllamaSynthesizer(OllamaConfig(base_url="http://127.0.0.1:9"))
    assert backend.unavailable_reason() == (
        "the Ollama server at http://127.0.0.1:9 did not answer — "
        "start it (ollama serve) or change synthesis.backend"
    )


def test_unavailable_message_keeps_the_prefix_doctor_matches():
    class _Gone(BaseSynthesizer):
        name = "gone"

        def is_available(self) -> bool:
            return False

        def synthesize_source_page(self, *args, **kwargs):  # pragma: no cover - never called
            raise AssertionError

    assert backend_unavailable_message(_Gone()).startswith("backend gone is not available: ")


def test_state_writes_keep_sections_a_newer_llmwiki_added(vault: Path):
    """An older writer must not erase a newer release's section (#374 incident:
    a per-minute ``queue run`` on older code wiped ``outcomes``)."""
    state_file = vault / "llmwiki-state.json"
    state_file.write_text(json.dumps({
        "meta": {"schema_version": 1},
        "future_section": {"key": "value"},
        "_meta": {"last_sync": "x"},
        "raw/sessions/a.md": 1712345678.0,
    }), encoding="utf-8")
    update_state(lambda s: s, state_file)
    on_disk = json.loads(state_file.read_text(encoding="utf-8"))
    assert on_disk["future_section"] == {"key": "value"}
    assert "_meta" not in on_disk
    assert "raw/sessions/a.md" not in on_disk
