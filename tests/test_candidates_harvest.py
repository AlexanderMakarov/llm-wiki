"""Tests for entity/concept candidate harvesting (#90).

Harvesting reads already-synthesized ``wiki/sources/`` pages and turns their
``[[wikilinks]]`` into candidate stubs. It must never re-read ``raw/``.
"""

from __future__ import annotations

from pathlib import Path

from llmwiki.candidates_harvest import (
    classify_names,
    harvest_targets,
    summarize_backlog,
    write_stubs,
)

# ─── Fixtures ──────────────────────────────────────────────────────────


def _mk_source(wiki: Path, slug: str, links: list[str]) -> Path:
    """Write a minimal source page whose Connections list the given links."""
    path = wiki / "sources" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"- [[{name}]] — why it connects" for name in links)
    path.write_text(
        f"---\ntitle: {slug}\ntype: source\n---\n\n## Connections\n{body}\n",
        encoding="utf-8",
    )
    return path


# ─── Threshold semantics ───────────────────────────────────────────────


def test_counts_distinct_source_pages_not_repeat_mentions(tmp_path: Path) -> None:
    """One page shouting a name five times is one signal, not five.

    This is the whole reason ``--min-refs`` is page-counted: instance
    counting lets a single emphatic document manufacture a hub.
    """
    wiki = tmp_path / "wiki"
    _mk_source(wiki, "loud", ["Repeated"] * 5)
    _mk_source(wiki, "a", ["Spread"])
    _mk_source(wiki, "b", ["Spread"])
    _mk_source(wiki, "c", ["Spread"])

    names = {t.name for t in harvest_targets(wiki, min_refs=3)}

    assert names == {"Spread"}


def test_target_below_threshold_is_dropped(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _mk_source(wiki, "a", ["Rare"])
    _mk_source(wiki, "b", ["Rare"])

    assert harvest_targets(wiki, min_refs=3) == []


def test_default_threshold_is_three(tmp_path: Path) -> None:
    """The default must agree with the lint rule that reports the gap."""
    wiki = tmp_path / "wiki"
    for slug in ("a", "b", "c"):
        _mk_source(wiki, slug, ["Trio"])
    _mk_source(wiki, "d", ["Duo"])
    _mk_source(wiki, "e", ["Duo"])

    assert [t.name for t in harvest_targets(wiki)] == ["Trio"]


# ─── Resolution against the existing wiki ──────────────────────────────


def test_targets_resolving_to_existing_pages_are_dropped(tmp_path: Path) -> None:
    """A link that already resolves is not a gap — whatever its inbound count.

    Matching is normalized the same way ``link_integrity`` normalizes, so the
    producer and the checker that reports on it cannot drift apart.
    """
    wiki = tmp_path / "wiki"
    for slug in ("a", "b", "c"):
        _mk_source(wiki, slug, ["LLM-Wiki", "Missing"])
    (wiki / "entities").mkdir(parents=True, exist_ok=True)
    (wiki / "entities" / "llm wiki.md").write_text("# llm wiki\n", encoding="utf-8")

    names = {t.name for t in harvest_targets(wiki)}

    assert names == {"Missing"}


# ─── Link syntax ───────────────────────────────────────────────────────


def test_section_anchors_are_stripped(tmp_path: Path) -> None:
    """``[[Name#Section]]`` names the same page as ``[[Name]]``."""
    wiki = tmp_path / "wiki"
    _mk_source(wiki, "a", ["Target#Key Facts"])
    _mk_source(wiki, "b", ["Target"])
    _mk_source(wiki, "c", ["Target#Sessions"])

    assert [t.name for t in harvest_targets(wiki)] == ["Target"]


def test_only_source_pages_vote(tmp_path: Path) -> None:
    """Links from elsewhere in the wiki are not evidence of a source gap.

    Guards the ``--candidates-only`` contract: harvesting reads the
    synthesized source layer, not whatever else lives under ``wiki/``.
    """
    wiki = tmp_path / "wiki"
    _mk_source(wiki, "a", ["Fringe"])
    (wiki / "projects").mkdir(parents=True, exist_ok=True)
    for slug in ("p1", "p2", "p3"):
        (wiki / "projects" / f"{slug}.md").write_text(
            "- [[Fringe]]\n", encoding="utf-8"
        )

    assert harvest_targets(wiki) == []


# ─── Evidence ──────────────────────────────────────────────────────────


def test_target_carries_the_pages_that_justified_it(tmp_path: Path) -> None:
    """A reviewer must be able to judge a stub without re-grepping."""
    wiki = tmp_path / "wiki"
    for slug in ("c", "a", "b"):
        _mk_source(wiki, slug, ["Evidenced"])

    [target] = harvest_targets(wiki)

    assert target.refs == 3
    assert target.sources == (
        "sources/a.md",
        "sources/b.md",
        "sources/c.md",
    )


# ─── Writing stubs ─────────────────────────────────────────────────────


def _harvest_one(tmp_path: Path, name: str = "Subject") -> tuple[Path, list]:
    wiki = tmp_path / "wiki"
    for slug in ("a", "b", "c"):
        _mk_source(wiki, slug, [name])
    return wiki, harvest_targets(wiki)


def test_stub_lands_under_candidates_with_status_candidate(tmp_path: Path) -> None:
    """Stubs are quarantined — never written straight into the trusted tree."""
    wiki, targets = _harvest_one(tmp_path)

    [path] = write_stubs(wiki, targets)

    assert path == wiki / "candidates" / "entities" / "Subject.md"
    text = path.read_text(encoding="utf-8")
    assert "status: candidate" in text
    assert "type: entity" in text
    assert not (wiki / "entities" / "Subject.md").exists()


def test_stub_records_the_evidence_that_justified_it(tmp_path: Path) -> None:
    wiki, targets = _harvest_one(tmp_path)

    [path] = write_stubs(wiki, targets)

    text = path.read_text(encoding="utf-8")
    for slug in ("a", "b", "c"):
        assert f"[[{slug}]]" in text


def test_classifier_routes_concepts_to_their_own_folder(tmp_path: Path) -> None:
    wiki, targets = _harvest_one(tmp_path, "Compounding")

    [path] = write_stubs(wiki, targets, classify=lambda names: {"Compounding": "concept"})

    assert path == wiki / "candidates" / "concepts" / "Compounding.md"
    assert "type: concept" in path.read_text(encoding="utf-8")


def test_unclassifiable_target_is_kept_not_dropped(tmp_path: Path) -> None:
    """Losing a target because a classifier shrugged is worse than misfiling it."""
    wiki, targets = _harvest_one(tmp_path)

    [path] = write_stubs(wiki, targets, classify=lambda names: {})

    assert path.exists()
    assert "entity_type: unknown" in path.read_text(encoding="utf-8")


def test_rerun_merges_new_evidence_without_duplicating(tmp_path: Path) -> None:
    """Idempotence is what makes it safe to wire into automation later."""
    wiki, targets = _harvest_one(tmp_path)
    write_stubs(wiki, targets)

    _mk_source(wiki, "d", ["Subject"])
    [path] = write_stubs(wiki, harvest_targets(wiki))

    text = path.read_text(encoding="utf-8")
    assert len(list((wiki / "candidates" / "entities").glob("*.md"))) == 1
    assert text.count("[[a]]") == 1
    assert "[[d]]" in text


def test_rerun_preserves_reviewer_prose(tmp_path: Path) -> None:
    """"No silent overwrites" applies to the review queue too.

    A reviewer who fleshes out a stub before promoting it must not lose that
    work to the next harvest.
    """
    wiki, targets = _harvest_one(tmp_path)
    [path] = write_stubs(wiki, targets)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "## Key Facts\n", "## Key Facts\n\n- Reviewer added this by hand.\n"
        ),
        encoding="utf-8",
    )

    _mk_source(wiki, "d", ["Subject"])
    write_stubs(wiki, harvest_targets(wiki))

    text = path.read_text(encoding="utf-8")
    assert "- Reviewer added this by hand." in text
    assert "[[d]]" in text


# ─── Classification ────────────────────────────────────────────────────


class _RecordingBackend:
    """Minimal stand-in for a synthesis backend."""

    def __init__(self, reply: str = "", *, available: bool = True) -> None:
        self.reply = reply
        self._available = available
        self.calls: list[str] = []

    def is_available(self) -> bool:
        return self._available

    def synthesize_source_page(self, raw_body, meta, prompt_template) -> str:
        self.calls.append(raw_body)
        return self.reply


def test_classification_uses_one_call_for_every_name() -> None:
    """Cost must scale with the candidate count, not the corpus size."""
    backend = _RecordingBackend("Tailscale: entity\nCompounding: concept\n")

    kinds = classify_names(["Tailscale", "Compounding"], backend)

    assert len(backend.calls) == 1
    assert kinds == {"Tailscale": "entity", "Compounding": "concept"}


def test_classification_is_skipped_when_backend_is_unavailable() -> None:
    """Harvesting must never be blocked by an unreachable backend."""
    backend = _RecordingBackend("Tailscale: entity\n", available=False)

    assert classify_names(["Tailscale"], backend) == {}
    assert backend.calls == []


def test_classification_survives_unparseable_output() -> None:
    """A confused backend costs us precision, never a crash."""
    backend = _RecordingBackend("I'm not sure what you're asking for.")

    assert classify_names(["Tailscale"], backend) == {}
    # First pass + one retry of the omitted name.
    assert len(backend.calls) == 2


def test_classification_retries_omitted_names() -> None:
    """A truncated first reply must get one follow-up for the missing tail (#90)."""

    class _PartialThenComplete(_RecordingBackend):
        def synthesize_source_page(self, raw_body, meta, prompt_template) -> str:
            self.calls.append(raw_body)
            if len(self.calls) == 1:
                return "Tailscale: entity\n"
            return "Compounding: concept\n"

    backend = _PartialThenComplete("")
    kinds = classify_names(["Tailscale", "Compounding"], backend)

    assert kinds == {"Tailscale": "entity", "Compounding": "concept"}
    assert len(backend.calls) == 2
    assert backend.calls[1] == "Compounding"


def test_classification_retry_still_leaves_gaps() -> None:
    """Retry is one shot — persistent gaps stay absent for fail-closed harvest."""
    backend = _RecordingBackend("Tailscale: entity\n")

    kinds = classify_names(["Tailscale", "Missing"], backend)

    assert kinds == {"Tailscale": "entity"}
    assert "Missing" not in kinds
    assert len(backend.calls) == 2
    assert backend.calls[1] == "Missing"


def test_classification_ignores_names_it_was_not_asked_about() -> None:
    """Guards against a backend inventing targets that were never harvested."""
    backend = _RecordingBackend("Tailscale: entity\nHallucinated: concept\n")

    assert classify_names(["Tailscale"], backend) == {"Tailscale": "entity"}


def test_no_backend_means_no_classification() -> None:
    assert classify_names(["Tailscale"], None) == {}


# ─── Re-runs respect the reviewer's filing ─────────────────────────────


def test_rerun_keeps_a_candidate_the_reviewer_refiled(tmp_path: Path) -> None:
    """If a reviewer moves a stub to concepts/, harvest must not drag it back.

    Re-classifying every run would fight the human the queue exists to serve.
    """
    wiki, targets = _harvest_one(tmp_path, "Refiled")
    [original] = write_stubs(wiki, targets)
    moved = wiki / "candidates" / "concepts" / "Refiled.md"
    moved.parent.mkdir(parents=True, exist_ok=True)
    moved.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
    original.unlink()

    write_stubs(wiki, harvest_targets(wiki))

    assert moved.is_file()
    assert not (wiki / "candidates" / "entities" / "Refiled.md").exists()


# ─── Estimate: the second backlog ──────────────────────────────────────


def test_backlog_summary_reports_adjacent_thresholds(tmp_path: Path) -> None:
    """--estimate must let an operator pick --min-refs before committing.

    A single total at one threshold hides whether the choice was sensible.
    """
    wiki = tmp_path / "wiki"
    for slug in ("a", "b", "c", "d", "e"):
        _mk_source(wiki, slug, ["Wide"])
    for slug in ("a", "b", "c"):
        _mk_source(wiki, f"{slug}2", ["Mid"])
    _mk_source(wiki, "solo", ["Narrow"])

    summary = summarize_backlog(wiki, min_refs=3)

    assert summary["min_refs"] == 3
    assert summary["candidates"] == 2          # Wide + Mid
    assert summary["distribution"][5] == 1     # Wide only
    assert summary["distribution"][1] == 3     # all three
    assert summary["broken_targets"] == 3


def test_backlog_summary_on_a_vault_with_no_sources(tmp_path: Path) -> None:
    """An empty or unsynthesized vault reports zero, not a crash."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()

    summary = summarize_backlog(wiki)

    assert summary["candidates"] == 0
    assert summary["broken_targets"] == 0


def test_classification_chunks_large_batches() -> None:
    """One prompt for 600 names risks a truncated reply and silent loss.

    Chunking bounds each call while keeping cost proportional to the
    candidate count.
    """
    names = [f"Name{i}" for i in range(250)]
    backend = _RecordingBackend("")

    classify_names(names, backend, batch_size=100, retry_missing=False)

    assert len(backend.calls) == 3
    assert sum(len(c.splitlines()) for c in backend.calls) == 250


def test_classification_reports_what_it_could_not_classify() -> None:
    """Silent degradation is the failure mode this must not have."""
    backend = _RecordingBackend("Known: entity\n")

    kinds = classify_names(["Known", "Unknown"], backend, retry_missing=False)

    assert kinds == {"Known": "entity"}


def test_rerun_does_not_reclassify_already_filed_candidates(tmp_path: Path) -> None:
    """Re-runs must not pay to re-decide a question already answered.

    A stub's folder is fixed once it exists (reviewer's call), so asking the
    backend about it again buys nothing and costs a call.
    """
    wiki, targets = _harvest_one(tmp_path, "Settled")
    asked: list[list[str]] = []

    def _classify(names):
        asked.append(list(names))
        return {}

    write_stubs(wiki, targets, classify=_classify)
    write_stubs(wiki, harvest_targets(wiki), classify=_classify)

    assert asked[0] == ["Settled"]
    assert asked[1] == []
