"""Whole-feature acceptance tests for #113: Honest estimate Candidates + post-synth summary.

# @layer: integration
# @spec: 001-honest-estimate-candidates
# @regression

Maps every acceptance criterion in functional-spec.md to at least one test.
Slice tests already cover several ACs; this file fills the gaps — specifically
the cases that require a vault with *pending* (unsynthesized) raw sessions.

AC coverage matrix (see bottom of module docstring):

    AC 2.1.1  → test_ac_211_pending_sources_estimate_uses_prerun_label   [integration]
    AC 2.1.2  → test_ac_212_pending_sources_estimate_prints_note          [integration]
    AC 2.1.3  → documented as covered by test_synthesize_estimate.py
    AC 2.2.1  → documented as covered by test_synth_run_summary.py
    AC 2.2.2  → test_ac_222_end_summary_does_not_duplicate_candidates    [unit]
    AC 2.2.3  → documented as covered by test_synth_run_summary.py
    AC 2.2.4  → documented as covered by test_synth_run_summary.py
    AC 2.3.1  → documented as covered by test_synth_run_summary.py

Notes on RED:
    ACs 2.1.3, 2.2.1, 2.2.3, 2.2.4, 2.3.1 satisfied by prior slice tests — those
    tests were written before implementation was complete and failed (RED) at that
    time per the slice development process.

    ACs 2.1.1, 2.1.2 (this file) are new integration tests on the pending-sources
    scenario. The estimate vault in slice tests used an empty corpus, which did not
    exercise the "at least one source still to synthesize" branch called out by the spec.

    AC 2.2.2 (this file) is a new unit test verifying the two helper functions use
    semantically distinct labels, making it structurally impossible for pre-run and
    post-run Candidates to be confused by callers.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from llmwiki.synth.reporting import print_candidates_pre_run, print_synth_run_summary

REPO_ROOT = Path(__file__).resolve().parents[1]


# ─── helpers ─────────────────────────────────────────────────────────────────


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    return subprocess.run(
        [sys.executable, "-m", "llmwiki", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=str(REPO_ROOT),
    )


@pytest.fixture
def pending_vault(tmp_path: Path) -> Path:
    """Vault with unsynthesized raw session files — the 'at least one pending source' scenario.

    No llmwiki-state.json is written, so every session file is 'new since last run'.
    """
    vault = tmp_path / "pending-vault"
    sessions = vault / "raw" / "sessions"
    sessions.mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki" / "sources").mkdir(parents=True)

    # Two minimal session files that _discover_raw_sessions will pick up.
    for slug in ("2026-01-01T10-00-project-alpha", "2026-01-02T11-00-project-beta"):
        (sessions / f"{slug}.md").write_text(
            f"---\ntitle: {slug}\nslug: {slug}\nproject: project\n---\n\nSession body.\n",
            encoding="utf-8",
        )
    return vault


# ─── AC 2.1.1 — pending sources → Candidates labelled as pre-run state ───────


def test_ac_211_pending_sources_estimate_uses_prerun_label(
    pending_vault: Path,
) -> None:
    """AC 2.1.1: vault with pending sessions → estimate uses 'Candidates (pre-run state):'.

    The spec requires this label (not bare 'Candidates:') specifically when
    sources are still waiting to be synthesized.  The slice tests for this
    label used an empty vault (AC 2.1.3); this test exercises the branch where
    new sessions exist in raw/sessions/ but are not yet in the state file.
    """
    # @regression
    cp = _run_cli("synthesize", "--estimate", "--vault", str(pending_vault))
    assert cp.returncode == 0, cp.stderr

    # Must carry the honest pre-run label.
    assert "Candidates (pre-run state):" in cp.stdout, (
        "Expected 'Candidates (pre-run state):' when pending sources exist.\n"
        f"stdout:\n{cp.stdout}"
    )
    # Must NOT read as a prediction / forecast of this run.
    assert re.search(r"(?m)^Candidates:\s", cp.stdout) is None, (
        "Old bare 'Candidates:' label must not appear.\n"
        f"stdout:\n{cp.stdout}"
    )
    # Confirm the vault really did have pending sources (estimate shows new > 0).
    assert "New since last run:" in cp.stdout
    new_match = re.search(r"New since last run:\s+(\d+)", cp.stdout)
    assert new_match is not None
    assert int(new_match.group(1)) > 0, (
        "Fixture should have pending sources but new=0 — fixture is broken."
    )


# ─── AC 2.1.2 — pending sources → clarifying note is present ────────────────


def test_ac_212_pending_sources_estimate_prints_note(
    pending_vault: Path,
) -> None:
    """AC 2.1.2: estimate with pending sources must print the pending-sources note.

    The note tells readers that the figure does not include whatever the
    upcoming synthesize will harvest from the new sessions.
    """
    # @regression
    cp = _run_cli("synthesize", "--estimate", "--vault", str(pending_vault))
    assert cp.returncode == 0, cp.stderr

    assert "note: pending sources are not yet reflected in this figure" in cp.stdout, (
        "Expected pending-sources note when vault has unsynthesised sessions.\n"
        f"stdout:\n{cp.stdout}"
    )


# ─── AC 2.2.2 — end summary does not retell Candidates (harvest owns it) ─────


def test_ac_222_end_summary_does_not_duplicate_candidates(
    capsys: pytest.CaptureFixture,
) -> None:
    """AC 2.2.2 (amended): Candidates appear once after a real synth — on harvest.

    Estimate still uses ``Candidates (pre-run state):``. The end-of-run
    summary must not print a second Candidates line (smoke: duplicate was
    noisy next to ``run_harvest``'s report).
    """
    # @regression
    backlog_with_candidate: dict = {
        "candidates": 3,
        "min_refs": 1,
        "broken_links": 4,
        "broken_targets": 2,
        "covered_links": 3,
        "distribution": {1: 3},
    }

    print_candidates_pre_run(backlog_with_candidate)
    pre_out = capsys.readouterr().out

    print_synth_run_summary(synthesized=5, duration_s=42.0)
    post_out = capsys.readouterr().out

    assert "Candidates (pre-run state):" in pre_out
    assert "3" in pre_out
    assert "Synthesized: 5" in post_out
    assert "Duration: 42.0s" in post_out
    assert "Candidates" not in post_out
    assert "backlog now" not in post_out.lower()


# ─── AC coverage summary (cross-reference) ───────────────────────────────────
#
# AC 2.1.1  → test_ac_211_pending_sources_estimate_uses_prerun_label   (this file)
# AC 2.1.2  → test_ac_212_pending_sources_estimate_prints_note          (this file)
# AC 2.1.3  → tests/test_synthesize_estimate.py::test_cli_estimate_labels_candidates_as_pre_run_state
# AC 2.2.1  → tests/test_synth_run_summary.py::test_synth_prints_post_harvest_run_summary
# AC 2.2.2  → test_ac_222_end_summary_does_not_duplicate_candidates    (this file)
# AC 2.2.3  → tests/test_synth_run_summary.py::test_synth_run_summary_omits_fabricated_token_and_cost
# AC 2.2.4  → tests/test_synth_run_summary.py::test_estimate_skips_end_of_run_summary
#             tests/test_synthesize_estimate.py::test_cli_estimate_does_not_print_post_run_summary
# AC 2.3.1  → harvest Candidates line (test_synth_prints_post_harvest_run_summary)
