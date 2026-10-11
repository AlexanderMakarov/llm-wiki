"""Whole-feature acceptance tests for #264 / AWOS 325-known-names-prep.

# @layer: integration
# @spec: 325-known-names-prep
# @regression

Unit and integration slices live in ``tests/test_topics.py`` (config resolution,
cap ordering, fingerprint/skip/delta merge, timeout kwarg wiring, cache v2) and
``tests/test_181_synth_clean_stop.py`` (progress/skip/usage reporting lines,
usage-limit during prep). This file adds **feature-level** checks those files
do not own — especially FR5 docs — and a few end-to-end ``prepare_known_names``
scenarios called out in ``functional-spec.md`` FR1–FR4.

AC coverage matrix (``context/spec/325-known-names-prep/functional-spec.md``):

    FR1.1 exact cap, highest reach first     -> test_topics.py::
                                             test_prepare_known_names_sends_exactly_candidate_cap
    FR1.2 below-cut saved entry + kind       -> test_below_cut_cached_topic_survives_capped_prepare
    FR1.3 cap change honoured on re-run      -> test_cap_change_on_rerun_honours_new_limit
    FR2.1 zero-call steady state + kind      -> test_topics.py::
                                             test_prepare_known_names_skips_llm_when_fingerprint_and_coverage_match;
                                             test_181_synth_clean_stop.py::
                                             test_known_names_prep_skip_reports_zero_sent_and_sizes
    FR2.2 partial delta merge                -> test_topics.py::
                                             test_prepare_known_names_one_new_candidate_delta_merges_prior_fields
    FR2.3 first run seeds full capped set    -> test_topics.py::
                                             test_prepare_known_names_calls_llm_once_and_caches
    FR3.1 dedicated timeout bounds prep call -> test_topics.py::
                                             test_prepare_known_names_passes_resolved_timeout
    FR3.2 config timeout without page change -> test_topics.py::
                                             test_known_names_config_honours_explicit_values
    FR3.3 failure → heuristic + clear warn   -> test_prepare_failure_warns_heuristic_fallback_with_stats
    FR4.1 sent/sizes/duration on call        -> test_181_synth_clean_stop.py::
                                             test_known_names_prep_prints_a_progress_line_before_the_call
    FR4.2 tokens/cost when backend reports   -> test_181_synth_clean_stop.py::
                                             test_known_names_prep_includes_usage_when_backend_reports_it
    FR4.3 skip visible (zero sent)           -> test_181_synth_clean_stop.py::
                                             test_known_names_prep_skip_reports_zero_sent_and_sizes
    FR4 delta mode visible in summary        -> test_delta_run_reports_mode_and_partial_sent_count
    FR5.1 config keys documented             -> test_configuration_reference_documents_known_names_keys
    FR5.2 four “how to choose” points         -> test_configuration_reference_how_to_choose_four_points
    FR5.3 CHANGELOG user-visible summary     -> test_changelog_mentions_known_names_prep

API parity (Dummy accepts ``timeout=`` without calling a provider):

    test_dummy_synthesizer_accepts_timeout_kwarg
"""

from __future__ import annotations

from pathlib import Path

from llmwiki.synth.base import DummySynthesizer
from llmwiki.synth.pipeline import PROMPT_TEMPLATE_PATH, _inject_vocabulary
from llmwiki.topics_consolidate import cache_path, load_cache, prepare_known_names
from tests import test_topics as topics_tests
from tests.changelog_notes import shipping_section_text

REPO_ROOT = Path(__file__).resolve().parents[1]


def _reply_for(names: list[str]) -> str:
    topics = [
        f'{{"canonical": "{n}", "kind": "entity",'
        f' "description": "{n} topic.", "aliases": []}}'
        for n in names
    ]
    return '{"topics": [' + ", ".join(topics) + '], "dropped": []}'


def _names_in_prompt(prompt: str) -> list[str]:
    return [
        line.split('name="', 1)[1].split('"', 1)[0]
        for line in prompt.splitlines()
        if "<candidate " in line
    ]


class _LlmSpy:
    """Minimal LLM backend: records calls and returns canned consolidation JSON."""

    is_llm = True
    timeout = 120

    def __init__(self, *, reply_names: list[str] | None = None) -> None:
        self.calls = 0
        self.prompts: list[str] = []
        self.kwargs: list[dict] = []
        self._reply_names = reply_names

    def synthesize_source_page(self, raw_body, meta, prompt_template, **kwargs):
        self.calls += 1
        self.prompts.append(prompt_template)
        self.kwargs.append(kwargs)
        names = self._reply_names
        if names is None:
            names = _names_in_prompt(prompt_template)
        return _reply_for(names)


# ─── FR1: cap change + below-cut preservation ───────────────────────────


# @regression
def test_cap_change_on_rerun_honours_new_limit(tmp_path: Path) -> None:
    """FR1.3: a higher ``candidate_cap`` on the next run sends more candidates."""
    # @spec: 325-known-names-prep
    wiki = topics_tests._make_wiki(
        tmp_path,
        {
            "s1": ["A", "B", "C", "D"],
            "s2": ["A", "B", "C", "D"],
            "s3": ["A", "B"],
            "s4": ["A"],
        },
    )
    spy = _LlmSpy()
    prepare_known_names(
        wiki,
        spy,
        cfg={"synthesis": {"known_names": {"candidate_cap": 2}}},
    )
    assert spy.calls == 1
    assert _names_in_prompt(spy.prompts[0]) == ["A", "B"]

    spy2 = _LlmSpy()
    prepare_known_names(
        wiki,
        spy2,
        cfg={"synthesis": {"known_names": {"candidate_cap": 4}}},
    )
    assert spy2.calls == 1
    # Delta call: only newly capped-in names (C, D) — not A/B again.
    assert _names_in_prompt(spy2.prompts[0]) == ["C", "D"]


# @regression
def test_below_cut_cached_topic_survives_capped_prepare_and_injects_kind(
    tmp_path: Path,
) -> None:
    """FR1.2: topics below the cap keep saved cache rows and inject ``kind``."""
    # @spec: 325-known-names-prep
    wiki = topics_tests._make_wiki(
        tmp_path,
        {
            "s1": ["Top", "Mid", "Tail"],
            "s2": ["Top", "Mid", "Tail"],
            "s3": ["Top", "Mid"],
            "s4": ["Top"],
        },
    )
    cfg_full = {"synthesis": {"known_names": {"candidate_cap": 3}}}
    spy = _LlmSpy(reply_names=["Top", "Mid", "Tail"])
    prepare_known_names(wiki, spy, cfg=cfg_full)
    assert spy.calls == 1
    assert set(_names_in_prompt(spy.prompts[0])) == {"Top", "Mid", "Tail"}

    cfg_tight = {"synthesis": {"known_names": {"candidate_cap": 2}}}
    spy2 = _LlmSpy()
    prepare_known_names(wiki, spy2, cfg=cfg_tight)
    assert spy2.calls == 0  # fingerprint refresh skip — Tail stays on disk
    assert "Tail" in cache_path(wiki).read_text(encoding="utf-8")

    loaded = load_cache(wiki)
    assert loaded is not None
    assert loaded["descriptions"]["Tail"] == "Tail topic."
    assert loaded["kinds"]["Tail"] == "entity"

    out = _inject_vocabulary("{vocabulary}", wiki)
    assert 'name="Tail" kind="entity"' in out
    assert 'desc="Tail topic."' in out


# ─── FR3 / FR4: failure fallback + delta reporting ───────────────────────


# @regression
def test_prepare_failure_warns_heuristic_fallback_with_stats(
    tmp_path: Path, capsys
) -> None:
    """FR3.3: non-usage-limit failure prints heuristic fallback + step stats."""
    # @spec: 325-known-names-prep
    wiki = topics_tests._make_wiki(
        tmp_path,
        {"s1": ["OpenClaw"], "s2": ["OpenClaw"]},
    )

    class _Boom:
        is_llm = True
        timeout = 120

        def synthesize_source_page(self, *_a, **_k):
            raise RuntimeError("provider timeout simulated")

    prepare_known_names(
        wiki,
        _Boom(),
        cfg={"synthesis": {"known_names": {"candidate_cap": 150}}},
    )
    err = capsys.readouterr().err
    assert "prepare_known_names failed" in err
    assert "heuristic vocabulary" in err
    assert "considered=" in err
    assert "sent=" in err


# @regression
def test_delta_run_reports_mode_and_partial_sent_count(
    tmp_path: Path, capsys
) -> None:
    """FR4: delta prep reports ``mode=delta``, ``considered`` vs ``sent``."""
    # @spec: 325-known-names-prep
    wiki = topics_tests._make_wiki(
        tmp_path,
        {"s1": ["Alpha", "Beta"], "s2": ["Alpha", "Beta"]},
    )
    spy = _LlmSpy()
    cfg = {"synthesis": {"known_names": {"candidate_cap": 150}}}
    prepare_known_names(wiki, spy, cfg=cfg)
    capsys.readouterr()

    (wiki / "sources" / "proj" / "s3.md").write_text(
        topics_tests._session(["Gamma"], stem="s3"),
        encoding="utf-8",
    )
    (wiki / "sources" / "proj" / "s4.md").write_text(
        topics_tests._session(["Gamma"], stem="s4"),
        encoding="utf-8",
    )

    prepare_known_names(wiki, spy, cfg=cfg)
    out = capsys.readouterr().out
    assert "Preparing known names (delta):" in out
    assert "mode=delta" in out
    assert "considered=3" in out
    assert "sent=1" in out
    assert "Known names ready (" in out


# ─── Dummy timeout kwarg (FR3 API) ───────────────────────────────────────


# @regression
def test_dummy_synthesizer_accepts_timeout_kwarg() -> None:
    """Dummy backend accepts ``timeout=`` for API parity (#264)."""
    # @spec: 325-known-names-prep
    dummy = DummySynthesizer()
    body = dummy.synthesize_source_page(
        "hello",
        {"slug": "s", "project": "p", "date": "2026-01-01"},
        PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8"),
        timeout=999.0,
    )
    assert "## Summary" in body


# ─── FR5: docs + CHANGELOG ───────────────────────────────────────────────


def test_configuration_reference_documents_known_names_keys() -> None:
    """FR5.1: cap (default 150), timeout, and incremental reuse are documented."""
    # @spec: 325-known-names-prep
    text = (REPO_ROOT / "docs" / "configuration-reference.md").read_text(
        encoding="utf-8"
    )
    cap_row = next(
        (
            ln
            for ln in text.splitlines()
            if ln.startswith("| `synthesis.known_names` | `candidate_cap`")
        ),
        None,
    )
    timeout_row = next(
        (
            ln
            for ln in text.splitlines()
            if ln.startswith("| `synthesis.known_names` | `timeout`")
        ),
        None,
    )
    assert cap_row is not None, "missing synthesis.known_names.candidate_cap row"
    assert "| 150 |" in cap_row
    assert timeout_row is not None, "missing synthesis.known_names.timeout row"
    assert "600" in timeout_row
    assert "Choosing the known-names candidate cap" in text
    assert "incremental reuse" in text.lower() or "fingerprint" in text.lower()


def test_configuration_reference_how_to_choose_four_points() -> None:
    """FR5.2: the four cap-guidance bullets from the functional spec."""
    # @spec: 325-known-names-prep
    text = (REPO_ROOT / "docs" / "configuration-reference.md").read_text(
        encoding="utf-8"
    )
    section_start = text.index("### Choosing the known-names candidate cap")
    section = text[section_start : section_start + 3500]
    assert "**What the number bounds**" in section
    assert "does **not** depend on session or article body length" in section
    assert "**Cost and time**" in section
    assert "pays **zero**" in section or "zero" in section.lower()
    assert "**Quality effect**" in section
    assert "heuristic" in section.lower()
    assert "**When vaults exceed ~150**" in section
    assert "quality problem" in section.lower() or "noisy" in section.lower()


def test_cli_reference_links_known_names_cap_guidance() -> None:
    """FR5: CLI synth section points at configuration cap guidance (#264)."""
    # @spec: 325-known-names-prep
    text = (REPO_ROOT / "docs" / "reference" / "cli.md").read_text(encoding="utf-8")
    assert "synthesis.known_names.candidate_cap" in text
    assert "synthesis.known_names.timeout" in text
    assert "choosing-the-known-names-candidate-cap" in text


def test_changelog_mentions_known_names_prep() -> None:
    """FR5.3: shipping notes summarise cap, reuse, timeout, and reporting."""
    # @spec: 325-known-names-prep
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    notes = shipping_section_text(text)
    assert "#264" in notes
    entry = next((ln for ln in notes.splitlines() if "#264" in ln), "")
    lowered = entry.lower()
    assert "known-names" in lowered or "known names" in lowered
    assert "150" in notes or "candidate_cap" in notes
    assert "timeout" in notes.lower()
    assert "fingerprint" in notes.lower() or "reuse" in notes.lower() or "skip" in notes.lower()
