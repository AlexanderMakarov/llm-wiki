"""Tests for wiki/candidates/ approval workflow (v1.1.0, #51)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from llmwiki import candidates as candidates_mod
from llmwiki.candidates import (
    ARCHIVE_DIR_NAME,
    CANDIDATES_DIR_NAME,
    DEFAULT_STALE_DAYS,
    MIRRORED_SUBDIRS,
    KeyFactsBackendError,
    _age_days,
    _find_candidate,
    _parse_frontmatter,
    _rewrite_status,
    apply_review_summary_to_pipeline,
    archive_dir,
    candidate_filename,
    candidate_review_summary,
    candidates_dir,
    discard,
    discarded_names,
    fill_key_facts_from_evidence,
    find_live_page,
    flip_and_promote,
    is_candidate,
    list_candidates,
    merge,
    promote,
    record_redirect_alias,
    rewrite_key_facts,
    stale_candidates,
    strip_harvest_merge_sections,
)
from llmwiki.candidates_harvest import harvest_targets, write_stubs
from llmwiki.cli import build_parser
from llmwiki.lint import (
    REGISTRY,
    rules,  # noqa: F401
)
from llmwiki.synth.base import BaseSynthesizer, DummySynthesizer
from llmwiki.wikilinks import (
    build_page_alias_map,
    parse_page_aliases,
    resolve_wikilink_target,
)

# ─── Fixtures ──────────────────────────────────────────────────────────


def _mk_wiki(tmp_path: Path) -> Path:
    """Create a wiki/ tree with candidates/ + entities/ + concepts/."""
    wiki = tmp_path / "wiki"
    for sub in MIRRORED_SUBDIRS:
        (wiki / sub).mkdir(parents=True, exist_ok=True)
        (wiki / "candidates" / sub).mkdir(parents=True, exist_ok=True)
    return wiki


class _FakeSynthesizer(BaseSynthesizer):
    """LLM stand-in that records its prompt and returns a canned completion."""

    def __init__(self, response: str = "- [[alpha]]: a real fact.\n"):
        self.response = response
        self.calls: list[dict] = []

    def synthesize_source_page(self, raw_body, meta, prompt_template):
        self.calls.append(
            {"body": raw_body, "meta": meta, "template": prompt_template}
        )
        return self.response

    def is_available(self) -> bool:
        return True


def _write_candidate(
    wiki: Path,
    kind: str,
    slug: str,
    *,
    body: str = "",
    date: str = "2026-04-17",
    title: str | None = None,
) -> Path:
    path = wiki / "candidates" / kind / f"{slug}.md"
    title = title or slug
    # Python 3.9 disallows backslashes inside f-string expressions, so build
    # the default body first and interpolate via a plain name.
    default_body = f"# {title}\n\nCandidate body."
    body_text = body or default_body
    path.write_text(
        f'---\ntitle: "{title}"\ntype: {kind[:-1]}\nstatus: candidate\n'
        f'last_updated: {date}\n---\n\n{body_text}\n',
        encoding="utf-8",
    )
    return path


# ─── Constants ────────────────────────────────────────────────────────


def test_constants_defined():
    assert CANDIDATES_DIR_NAME == "candidates"
    assert ARCHIVE_DIR_NAME == "archive"
    assert DEFAULT_STALE_DAYS == 30
    assert "entities" in MIRRORED_SUBDIRS
    assert "concepts" in MIRRORED_SUBDIRS


def test_candidate_review_summary(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Alpha", date="2020-01-01")
    _write_candidate(wiki, "concepts", "Beta", date="2026-04-17")
    (wiki / "entities").mkdir(parents=True, exist_ok=True)
    (wiki / "concepts").mkdir(parents=True, exist_ok=True)
    (wiki / "entities" / "TrustedEnt.md").write_text(
        "---\ntitle: TrustedEnt\nstatus: reviewed\n---\n\n# TrustedEnt\n",
        encoding="utf-8",
    )
    (wiki / "concepts" / "_context.md").write_text(
        "---\ntitle: Concepts\ntype: context\n---\n\nFolder context.\n",
        encoding="utf-8",
    )
    (wiki / "concepts" / "TrustedConcept.md").write_text(
        "---\ntitle: TrustedConcept\nstatus: reviewed\n---\n\n# TrustedConcept\n",
        encoding="utf-8",
    )
    summary = candidate_review_summary(wiki, now=datetime(2026, 4, 20, tzinfo=UTC))
    assert summary["to_review"] == 2
    assert summary["to_review_by_kind"] == {"entities": 1, "concepts": 1}
    assert summary["to_review_stale"] == 1
    assert summary["stale_days"] == DEFAULT_STALE_DAYS
    assert summary["trusted_entities"] == 1
    assert summary["trusted_concepts"] == 1  # _context.md excluded
    pipeline = apply_review_summary_to_pipeline(
        {"stages": ["raw", "synthesized"], "rows": []},
        wiki,
        now=datetime(2026, 4, 20, tzinfo=UTC),
    )
    assert "to_review" in pipeline["stages"]
    assert pipeline["to_review"] == 2
    assert pipeline["trusted_entities"] == 1
    assert pipeline["trusted_concepts"] == 1


# ─── is_candidate / dir helpers ──────────────────────────────────────


def test_is_candidate_true_for_candidates_path():
    assert is_candidate(Path("/x/wiki/candidates/entities/Foo.md")) is True


def test_is_candidate_false_for_normal_path():
    assert is_candidate(Path("/x/wiki/entities/Foo.md")) is False


def test_candidates_dir_returns_right_path(tmp_path: Path):
    wiki = tmp_path / "wiki"
    assert candidates_dir(wiki) == wiki / "candidates"


def test_archive_dir_returns_right_path(tmp_path: Path):
    wiki = tmp_path / "wiki"
    assert archive_dir(wiki) == wiki / "archive" / "candidates"


# ─── list_candidates ─────────────────────────────────────────────────


def test_list_empty_wiki(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    assert list_candidates(wiki) == []


def test_list_missing_candidates_dir(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    # No candidates/ subdir
    assert list_candidates(wiki) == []


def test_list_returns_pending_entities(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "NewEntity")
    _write_candidate(wiki, "concepts", "NewConcept")
    items = list_candidates(wiki)
    assert len(items) == 2
    kinds = {c["kind"] for c in items}
    assert kinds == {"entities", "concepts"}


def test_list_skips_context_md(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Real")
    (wiki / "candidates" / "entities" / "_context.md").write_text(
        "---\ntitle: Context\n---\n", encoding="utf-8"
    )
    items = list_candidates(wiki)
    assert len(items) == 1
    assert items[0]["slug"] == "Real"


def test_list_includes_body_preview(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "X", body="# X\n\nDetails about X entity.")
    items = list_candidates(wiki)
    assert "Details about X entity" in items[0]["body_preview"]


def test_list_computes_age_days(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Old", date="2026-04-01")
    now = datetime(2026, 4, 17, tzinfo=UTC)
    items = list_candidates(wiki, now=now)
    assert items[0]["age_days"] == 16


# ─── promote ────────────────────────────────────────────────────────


def test_promote_moves_candidate_to_entities(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    candidate = _write_candidate(wiki, "entities", "ApprovedFoo")

    promoted = promote("ApprovedFoo", wiki)
    assert promoted == wiki / "entities" / "ApprovedFoo.md"
    assert promoted.is_file()
    assert not candidate.exists()


def test_promote_rewrites_status_to_reviewed(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Foo")
    path = promote("Foo", wiki)
    content = path.read_text(encoding="utf-8")
    assert "status: reviewed" in content
    assert "status: candidate" not in content


def test_promote_infers_kind_from_candidate_location(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "concepts", "Idea")
    path = promote("Idea", wiki)
    assert path.parent.name == "concepts"


def test_promote_respects_explicit_kind(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Foo")
    path = promote("Foo", wiki, kind="entities")
    assert path.parent.name == "entities"


def test_promote_raises_when_candidate_missing(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    with pytest.raises(FileNotFoundError):
        promote("Ghost", wiki)


def test_cli_promote_unknown_slug_is_an_error(tmp_path: Path, capsys):
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    args = build_parser().parse_args([
        "candidates", "promote", "--slug", "Ghost", "--wiki-dir", str(wiki),
    ])
    assert args.func(args) == 2
    assert capsys.readouterr().err.startswith("error: candidate not found")


def test_cli_promote_ambiguous_slug_is_an_error(tmp_path: Path, capsys):
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Junk")
    _write_candidate(wiki, "entities", "junk")
    args = build_parser().parse_args([
        "candidates", "promote", "--slug", "JUNK", "--wiki-dir", str(wiki),
    ])
    assert args.func(args) == 2
    assert "is ambiguous" in capsys.readouterr().err


def _write_subject_with_evidence(wiki: Path) -> Path:
    """A harvest stub whose two sources each name it twice (mention digest)."""
    (wiki / "sources").mkdir(parents=True, exist_ok=True)
    (wiki / "sources" / "alpha.md").write_text(
        "---\ntitle: Alpha session\ntype: source\n---\n\n"
        "## Summary\n[[Other]] work landed alongside [[Subject]]\n\n"
        "## Connections\n- [[Subject]] — built the auth layer\n",
        encoding="utf-8",
    )
    (wiki / "sources" / "beta.md").write_text(
        "---\ntitle: Beta session\ntype: source\n---\n\n"
        "## Summary\nDiscussed [[Subject]] for rollout planning.\n",
        encoding="utf-8",
    )
    path = wiki / "candidates" / "entities" / "Subject.md"
    path.write_text(
        '---\ntitle: "Subject"\ntype: entity\nstatus: candidate\n'
        "sources: [alpha, beta]\nlast_updated: 2026-08-01\n---\n\n"
        "# Subject\n\n## Key Facts\n\n## Connections\n\n"
        "Named by 2 source page(s):\n\n- [[alpha]]\n- [[beta]]\n",
        encoding="utf-8",
    )
    return path


def _write_subject_with_topic_facts(wiki: Path) -> Path:
    """Candidate whose sources carry parseable ``fact:`` topic bullets (#147)."""
    (wiki / "sources").mkdir(parents=True, exist_ok=True)
    (wiki / "sources" / "alpha.md").write_text(
        "---\ntitle: Alpha session\ntype: source\n---\n\n"
        "## Connections\n"
        "- [[Subject]] (entity) — auth layer\n"
        "  - fact: Serves as the auth layer for the platform.\n",
        encoding="utf-8",
    )
    (wiki / "sources" / "beta.md").write_text(
        "---\ntitle: Beta session\ntype: source\n---\n\n"
        "## Connections\n"
        "- [[Subject]] (entity) — rollout\n"
        "  - fact: Was scheduled for staged rollout.\n",
        encoding="utf-8",
    )
    path = wiki / "candidates" / "entities" / "Subject.md"
    path.write_text(
        '---\ntitle: "Subject"\ntype: entity\nstatus: candidate\n'
        "sources: [alpha, beta]\nlast_updated: 2026-08-01\n---\n\n"
        "# Subject\n\n## Key Facts\n\n## Connections\n\n"
        "Named by 2 source page(s):\n\n- [[alpha]]\n- [[beta]]\n",
        encoding="utf-8",
    )
    return path


def test_promote_fills_key_facts_from_source_topics(tmp_path: Path):
    """#147: promote copies ``fact:`` lines from cited sources, no LLM."""
    wiki = _mk_wiki(tmp_path)
    _write_subject_with_topic_facts(wiki)

    text = promote("Subject", wiki).read_text(encoding="utf-8")
    assert "status: reviewed" in text
    assert "- Serves as the auth layer for the platform. [[alpha]]" in text
    assert "- Was scheduled for staged rollout. [[beta]]" in text


def test_promote_succeeds_without_llm_backend(tmp_path: Path):
    """#147: no backend is fine — empty Key Facts stay empty if sources lack facts."""
    wiki = _mk_wiki(tmp_path)
    candidate = _write_subject_with_evidence(wiki)

    promoted = promote("Subject", wiki)
    assert promoted.is_file()
    assert not candidate.exists()
    text = promoted.read_text(encoding="utf-8")
    assert "status: reviewed" in text
    kf = text.split("## Key Facts", 1)[1].split("## Connections", 1)[0]
    assert not any(
        line.strip().startswith("-") for line in kf.splitlines() if line.strip()
    )


def test_promote_succeeds_with_dummy_backend(tmp_path: Path):
    """Dummy is ignored on promote; fill stays offline from source topics."""
    wiki = _mk_wiki(tmp_path)
    _write_subject_with_topic_facts(wiki)

    text = promote("Subject", wiki, synthesizer=DummySynthesizer()).read_text(
        encoding="utf-8"
    )
    assert "- Serves as the auth layer for the platform. [[alpha]]" in text


def test_promote_does_not_call_synthesize_or_mention_helpers(tmp_path: Path, monkeypatch):
    """Promote must not use the LLM rewrite path or mention-clip helpers."""
    wiki = _mk_wiki(tmp_path)
    _write_subject_with_topic_facts(wiki)
    fake = _FakeSynthesizer("- Invented by the model. [[alpha]]\n")
    calls = {"mention": 0, "digest": 0}

    def _spy_mention(*_a, **_k):
        calls["mention"] += 1
        raise AssertionError("promote must not call _mention_lines")

    def _spy_digest(*_a, **_k):
        calls["digest"] += 1
        raise AssertionError("promote must not build an LLM evidence digest")

    monkeypatch.setattr(candidates_mod, "_mention_lines", _spy_mention)
    monkeypatch.setattr(candidates_mod, "_evidence_digest", _spy_digest)

    text = promote("Subject", wiki, synthesizer=fake).read_text(encoding="utf-8")
    assert "Invented by the model" not in text
    assert "- Serves as the auth layer for the platform. [[alpha]]" in text
    assert fake.calls == []
    assert calls["mention"] == 0
    assert calls["digest"] == 0


def test_promote_needs_no_backend_when_sources_are_silent(tmp_path: Path):
    """No evidence to write from is not a backend problem."""
    wiki = _mk_wiki(tmp_path)
    (wiki / "sources").mkdir(parents=True, exist_ok=True)
    (wiki / "sources" / "quiet.md").write_text(
        "---\ntitle: Quiet\ntype: source\n---\n\n## Summary\nNothing relevant.\n",
        encoding="utf-8",
    )
    (wiki / "candidates" / "entities" / "Unmentioned.md").write_text(
        '---\ntitle: "Unmentioned"\ntype: entity\nstatus: candidate\n'
        "sources: [quiet]\n---\n\n# Unmentioned\n\n## Key Facts\n\n"
        "## Connections\n\n- [[quiet]]\n",
        encoding="utf-8",
    )

    text = promote("Unmentioned", wiki).read_text(encoding="utf-8")
    assert "status: reviewed" in text


def test_promote_preserves_nonempty_key_facts(tmp_path: Path):
    """#103/#147: reviewer-authored Key Facts must survive promote."""
    wiki = _mk_wiki(tmp_path)
    (wiki / "sources").mkdir(parents=True, exist_ok=True)
    (wiki / "sources" / "alpha.md").write_text(
        "---\ntitle: Alpha\ntype: source\n---\n\n"
        "## Connections\n"
        "- [[Foo]] (entity) — should not overwrite\n"
        "  - fact: Source topic fact that must not replace reviewer prose.\n",
        encoding="utf-8",
    )
    path = wiki / "candidates" / "entities" / "Foo.md"
    path.write_text(
        '---\ntitle: "Foo"\ntype: entity\nstatus: candidate\n'
        "sources: [alpha]\n---\n\n"
        "# Foo\n\n## Key Facts\n\n- Reviewer wrote this.\n\n"
        "## Connections\n\n- [[alpha]]\n",
        encoding="utf-8",
    )

    text = promote("Foo", wiki).read_text(encoding="utf-8")
    assert "- Reviewer wrote this." in text
    assert "Source topic fact" not in text


def test_fill_key_facts_from_topics_without_synthesizer(tmp_path: Path):
    """Offline fill uses topic facts; bare name-only Connections stay empty."""
    wiki = _mk_wiki(tmp_path)
    (wiki / "sources").mkdir(parents=True, exist_ok=True)
    (wiki / "sources" / "solo.md").write_text(
        "---\ntitle: Solo notes\ntype: source\n---\n\n"
        "## Connections\n- [[Bare]]\n",
        encoding="utf-8",
    )
    text = (
        '---\ntitle: "Bare"\ntype: entity\nstatus: candidate\n'
        "sources: [solo]\n---\n\n# Bare\n\n## Key Facts\n\n"
        "## Connections\n\n- [[solo]]\n"
    )
    out = fill_key_facts_from_evidence(text, wiki, name="Bare")
    assert out == text


def test_fill_key_facts_llm_path_skips_bare_mentions(tmp_path: Path):
    """A source that only lists the name carries no fact for the LLM digest."""
    wiki = _mk_wiki(tmp_path)
    (wiki / "sources").mkdir(parents=True, exist_ok=True)
    (wiki / "sources" / "solo.md").write_text(
        "---\ntitle: Solo notes\ntype: source\n---\n\n"
        "## Connections\n- [[Bare]]\n",
        encoding="utf-8",
    )
    text = (
        '---\ntitle: "Bare"\ntype: entity\nstatus: candidate\n'
        "sources: [solo]\n---\n\n# Bare\n\n## Key Facts\n\n"
        "## Connections\n\n- [[solo]]\n"
    )
    fake = _FakeSynthesizer("- Invented. [[solo]]\n")
    out = fill_key_facts_from_evidence(text, wiki, name="Bare", synthesizer=fake)
    assert "Invented" not in out
    assert fake.calls == []


def test_key_facts_evidence_includes_every_mention_line(tmp_path: Path):
    """Rewrite/LLM fill: the descriptive mention is often not the first."""
    wiki = _mk_wiki(tmp_path)
    _write_subject_with_evidence(wiki)
    # Promote offline first so the trusted page exists for rewrite.
    promote("Subject", wiki)
    fake = _FakeSynthesizer("- A fact. [[alpha]]\n")

    rewrite_key_facts("Subject", wiki, synthesizer=fake)
    evidence = fake.calls[0]["body"]
    assert "work landed alongside" in evidence
    assert "built the auth layer" in evidence
    assert "rollout planning" in evidence


def test_rewrite_key_facts_requires_llm_backend(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_subject_with_evidence(wiki)
    promote("Subject", wiki)

    with pytest.raises(KeyFactsBackendError):
        rewrite_key_facts("Subject", wiki)


def test_rewrite_key_facts_rejects_dummy_backend(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_subject_with_evidence(wiki)
    promote("Subject", wiki)

    with pytest.raises(KeyFactsBackendError):
        rewrite_key_facts("Subject", wiki, synthesizer=DummySynthesizer())


def test_rewrite_key_facts_raises_when_backend_returns_no_bullets(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_subject_with_evidence(wiki)
    promote("Subject", wiki)

    with pytest.raises(KeyFactsBackendError):
        rewrite_key_facts(
            "Subject", wiki, synthesizer=_FakeSynthesizer("I cannot help.\n")
        )


def test_rewrite_key_facts_drop_preamble_and_cap_at_five(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_subject_with_evidence(wiki)
    promote("Subject", wiki)
    fake = _FakeSynthesizer(
        "Here are the facts:\n\n" +
        "".join(f"- Fact {i}. [[alpha]]\n" for i in range(8)) +
        "\nHope that helps!\n"
    )

    text = rewrite_key_facts("Subject", wiki, synthesizer=fake).read_text(
        encoding="utf-8"
    )
    assert "Here are the facts" not in text
    assert "Hope that helps" not in text
    assert text.count("- Fact ") == 5


def test_strip_harvest_merge_sections_drops_stub_paste():
    text = (
        '---\ntitle: "Tailscale"\ntype: entity\n---\n\n'
        "# Tailscale\n\n## Key Facts\n\n- Real fact. [[a]]\n\n"
        "## Connections\n\n- [[a]]\n\n"
        "## Candidate merge — 2026-08-01\n\n"
        "Merged from `candidates/entities/Tailnet.md`:\n\n"
        "# Tailnet\n\n## Key Facts\n\n## Connections\n\n"
        "Named by 4 source page(s), which is the evidence that\n"
        "justified this candidate:\n\n- [[b]]\n"
    )
    out = strip_harvest_merge_sections(text)
    assert "## Candidate merge" not in out
    assert "- Real fact. [[a]]" in out
    assert "Tailnet" not in out


def test_strip_harvest_merge_keeps_reviewer_prose():
    text = (
        '---\ntitle: "Main"\ntype: entity\n---\n\n# Main\n\n'
        "## Candidate merge — 2026-08-01\n\n"
        "Merged from `candidates/entities/Dup.md`:\n\n"
        "Reviewer added context about the duplicate.\n"
    )
    out = strip_harvest_merge_sections(text)
    assert "## Candidate merge" in out
    assert "Reviewer added context" in out


def test_rewrite_key_facts_replaces_regex_bullets(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    (wiki / "sources").mkdir(parents=True, exist_ok=True)
    (wiki / "sources" / "alpha.md").write_text(
        "---\ntitle: Alpha\ntype: source\n---\n\n"
        "## Connections\n- [[Foo]] — the auth gateway\n",
        encoding="utf-8",
    )
    page = wiki / "entities" / "Foo.md"
    page.write_text(
        '---\ntitle: "Foo"\ntype: entity\nstatus: reviewed\n'
        "sources: [alpha]\n---\n\n# Foo\n\n"
        "## Key Facts\n\n- [[alpha]]: [[Other]] sat near the link\n\n"
        "## Connections\n\n- [[alpha]]\n\n"
        "## Candidate merge — 2026-08-01\n\n"
        "Merged from `candidates/entities/FooAlias.md`:\n\n"
        "# FooAlias\n\n## Key Facts\n\n## Connections\n\n"
        "Named by 1 source page(s), which is the evidence that\n"
        "justified this candidate:\n\n- [[alpha]]\n",
        encoding="utf-8",
    )
    fake = _FakeSynthesizer(
        "- Serves as the auth gateway for the stack. [[alpha]]\n"
    )

    out = rewrite_key_facts("Foo", wiki, synthesizer=fake).read_text(encoding="utf-8")
    assert "sat near the link" not in out
    assert "Serves as the auth gateway" in out
    assert "## Candidate merge" not in out
    assert fake.calls, "rewrite must call the backend"


# ─── merge ──────────────────────────────────────────────────────────


def test_merge_appends_body_to_target(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    target = wiki / "entities" / "Main.md"
    target.write_text(
        '---\ntitle: "Main"\ntype: entity\n---\n\n# Main\n\nOriginal content.\n',
        encoding="utf-8",
    )
    _write_candidate(wiki, "entities", "Duplicate", body="# Duplicate\n\nExtra info.")

    result = merge("Duplicate", wiki, into_slug="Main")
    assert result == target
    text = target.read_text(encoding="utf-8")
    assert "Original content" in text
    assert "## Candidate merge" in text
    assert "Extra info" in text


def _write_merge_pair(tmp_path: Path) -> tuple[Path, Path]:
    """A trusted page plus a harvest-stub duplicate of it."""
    wiki = _mk_wiki(tmp_path)
    target = wiki / "entities" / "Tailscale.md"
    target.write_text(
        '---\ntitle: "Tailscale"\ntype: entity\nsources: [s1, s2]\n---\n\n'
        "# Tailscale\n\n## Key Facts\n\n- Provides the network layer. [[s1]]\n\n"
        "## Connections\n\n- [[s1]]\n- [[s2]]\n",
        encoding="utf-8",
    )
    (wiki / "candidates" / "entities" / "Tailnet.md").write_text(
        '---\ntitle: "Tailnet"\ntype: entity\nstatus: candidate\n'
        "sources: [s2, s3]\n---\n\n# Tailnet\n\n## Key Facts\n\n## Connections\n\n"
        "Named by 2 source page(s), which is the evidence that\n"
        "justified this candidate:\n\n- [[s2]]\n- [[s3]]\n",
        encoding="utf-8",
    )
    return wiki, target


def test_merge_unions_evidence_into_target(tmp_path: Path):
    """#103: a stub's value is its evidence, so the evidence must survive."""
    wiki, target = _write_merge_pair(tmp_path)
    merge("Tailnet", wiki, into_slug="Tailscale")
    text = target.read_text(encoding="utf-8")

    assert "sources: [s1, s2, s3]" in text
    connections = text.split("## Connections", 1)[1]
    assert "- [[s3]]" in connections
    assert connections.count("- [[s2]]") == 1, "no duplicate evidence links"


def test_merge_drops_harvest_boilerplate(tmp_path: Path):
    """The stub's scaffolding must not land in a trusted page."""
    wiki, target = _write_merge_pair(tmp_path)
    merge("Tailnet", wiki, into_slug="Tailscale")
    text = target.read_text(encoding="utf-8")

    assert "# Tailnet" not in text
    assert "Named by 2 source page(s)" not in text
    assert "## Candidate merge" not in text
    assert text.count("## Key Facts") == 1


def test_merge_records_the_alias(tmp_path: Path):
    wiki, target = _write_merge_pair(tmp_path)
    merge("Tailnet", wiki, into_slug="Tailscale")
    text = target.read_text(encoding="utf-8")

    assert "## Aliases" in text
    assert "- Tailnet — merged " in text


def test_merge_refreshes_named_by_count_on_pending_target(tmp_path: Path) -> None:  # @regression
    """#139: harvest boilerplate count tracks unioned evidence after same-table merge."""
    # @layer: integration  # @spec: 139-candidates-merge-aliases
    wiki = _mk_wiki(tmp_path)
    (wiki / "sources").mkdir(parents=True, exist_ok=True)
    for slug in ("s1", "s2", "s3"):
        (wiki / "sources" / f"{slug}.md").write_text(
            f'---\ntitle: "{slug}"\ntype: source\n---\n\nBody.\n',
            encoding="utf-8",
        )
    (wiki / "candidates" / "entities" / "Canonical.md").write_text(
        '---\ntitle: "Canonical"\ntype: entity\nstatus: candidate\n'
        "sources: [s1, s2]\n---\n\n# Canonical\n\n## Key Facts\n\n## Connections\n\n"
        "Named by 2 source page(s):\n\n- [[s1]]\n- [[s2]]\n",
        encoding="utf-8",
    )
    (wiki / "candidates" / "entities" / "Dup.md").write_text(
        '---\ntitle: "Dup"\ntype: entity\nstatus: candidate\n'
        "sources: [s2, s3]\n---\n\n# Dup\n\n## Key Facts\n\n## Connections\n\n"
        "Named by 2 source page(s), which is the evidence that\n"
        "justified this candidate:\n\n- [[s2]]\n- [[s3]]\n",
        encoding="utf-8",
    )

    merge("Dup", wiki, into_slug="Canonical")
    text = (wiki / "candidates" / "entities" / "Canonical.md").read_text(
        encoding="utf-8"
    )

    assert "Named by 3 source page(s)" in text
    assert "Named by 2 source page(s)" not in text
    assert "- [[s3]]" in text.split("Named by 3", 1)[1]


def test_merge_refreshes_named_by_on_trusted_target_with_boilerplate(
    tmp_path: Path,
) -> None:  # @regression
    """#139: trusted pages that still carry harvest boilerplate get a fresh count."""
    # @layer: integration  # @spec: 139-candidates-merge-aliases
    wiki, target = _write_merge_pair(tmp_path)
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            "## Connections",
            "Named by 2 source page(s), which is the evidence that\n"
            "justified this candidate:\n\n- [[s1]]\n- [[s2]]\n\n## Connections",
            1,
        ),
        encoding="utf-8",
    )

    merge("Tailnet", wiki, into_slug="Tailscale")
    text = target.read_text(encoding="utf-8")

    assert "Named by 3 source page(s)" in text
    assert "Named by 2 source page(s)" not in text
    assert "- [[s3]]" in text


def test_merge_preserves_target_key_facts(tmp_path: Path):
    wiki, target = _write_merge_pair(tmp_path)
    merge("Tailnet", wiki, into_slug="Tailscale")
    assert "- Provides the network layer. [[s1]]" in target.read_text(encoding="utf-8")


def test_merge_archives_candidate_after(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    (wiki / "entities" / "Main.md").write_text(
        '---\ntitle: Main\ntype: entity\n---\nbody\n', encoding="utf-8"
    )
    candidate = _write_candidate(wiki, "entities", "Dup")
    merge("Dup", wiki, into_slug="Main")
    assert not candidate.exists()


def test_merge_raises_when_target_missing(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Dup")
    with pytest.raises(FileNotFoundError):
        merge("Dup", wiki, into_slug="Nonexistent")


def test_cli_merge_unknown_slug_is_an_error(tmp_path: Path, capsys):
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Main")
    args = build_parser().parse_args([
        "candidates", "merge", "--slug", "Ghost", "--into", "Main",
        "--wiki-dir", str(wiki),
    ])
    assert args.func(args) == 2
    assert capsys.readouterr().err.startswith("error: candidate not found")


def test_cli_merge_ambiguous_slug_is_an_error(tmp_path: Path, capsys):
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Junk")
    _write_candidate(wiki, "entities", "junk")
    _write_candidate(wiki, "entities", "Main")
    args = build_parser().parse_args([
        "candidates", "merge", "--slug", "JUNK", "--into", "Main",
        "--wiki-dir", str(wiki),
    ])
    assert args.func(args) == 2
    assert "is ambiguous" in capsys.readouterr().err


# ─── discard ────────────────────────────────────────────────────────


def test_discard_moves_to_archive(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    candidate = _write_candidate(wiki, "entities", "Bogus")
    archived = discard("Bogus", wiki, reason="hallucinated").path

    assert not candidate.exists()
    assert archived.is_file()
    # Archive structure: wiki/archive/candidates/<timestamp>/Bogus.md
    assert "archive" in archived.parts
    assert "candidates" in archived.parts
    assert archived.name == "Bogus.md"


def test_discard_writes_reason_file(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Fake")
    archived = discard("Fake", wiki, reason="not a real thing").path

    reason_file = archived.with_suffix(".reason.txt")
    assert reason_file.is_file()
    text = reason_file.read_text(encoding="utf-8")
    assert "not a real thing" in text
    assert "Discarded at:" in text


def test_discard_raises_when_candidate_missing(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    with pytest.raises(FileNotFoundError):
        discard("Ghost", wiki, reason="x")


# ─── _find_candidate case-fold resolution (#282) ───────────────────────


def test_find_candidate_exact_match_wins_over_fold(tmp_path: Path):
    """# @layer: unit  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    exact = _write_candidate(wiki, "entities", "Junk")
    _write_candidate(wiki, "entities", "JUNK")
    assert _find_candidate("Junk", wiki, None) == exact


def test_find_candidate_resolves_case_insensitively(tmp_path: Path):
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    stubs = _harvest(wiki, {"a": "Uses [[JUNK]] a lot.", "b": "More on [[JUNK]]."})
    stub = next(p for p in stubs if p.stem == "JUNK")
    assert _find_candidate("Junk", wiki, None) == stub
    result = discard("Junk", wiki, reason="noise")
    assert result.path.name == "JUNK.md"


def test_find_candidate_resolves_sanitized_slash_name(tmp_path: Path):
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    stubs = _harvest(
        wiki, {"a": "See [[A/B thing]].", "b": "Also [[A/B thing]] again."}
    )
    stub = next(p for p in stubs if p.stem == "A-B thing")
    assert _find_candidate("A/B thing", wiki, None) == stub


def test_find_candidate_ambiguous_fold_raises_with_both_names(tmp_path: Path):
    """# @layer: unit  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Junk")
    _write_candidate(wiki, "entities", "junk")
    with pytest.raises(ValueError) as excinfo:
        _find_candidate("JUNK", wiki, None)
    message = str(excinfo.value)
    assert "Junk.md" in message
    assert "junk.md" in message


def test_find_candidate_fold_respects_kind_filter(tmp_path: Path):
    """Fold resolution stays inside the requested kind, same as exact match."""
    wiki = _mk_wiki(tmp_path)
    entity = _write_candidate(wiki, "entities", "Junk")
    _write_candidate(wiki, "concepts", "JUNK")
    assert _find_candidate("junk", wiki, "entities") == entity


def test_find_candidate_unknown_slug_still_errors(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    with pytest.raises(FileNotFoundError, match="candidate not found: 'Ghost'"):
        _find_candidate("Ghost", wiki, None)


# ─── discard rewrites links (#282) ───────────────────────────────────


def _harvest(wiki: Path, sources: dict[str, str]) -> list[Path]:
    """Write source pages, then harvest + write stubs through the real code."""
    for slug, body in sources.items():
        path = wiki / "sources" / f"{slug}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f'---\ntitle: "{slug}"\ntype: source\n---\n\n{body}\n', encoding="utf-8"
        )
    return write_stubs(wiki, harvest_targets(wiki, min_refs=2))


def _live_text(wiki: Path) -> str:
    return "\n".join(
        p.read_text(encoding="utf-8")
        for p in wiki.rglob("*.md")
        if "archive" not in p.relative_to(wiki).parts
    )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Plain Name", "Plain Name.md"),
        ("A/B thing", "A-B thing.md"),
        ("back\\slash", "back-slash.md"),
        ("C: D", "C- D.md"),
        ("..hidden", "hidden.md"),
        ("nul\x00byte", "nul-byte.md"),
        # Windows refuses a trailing dot or space, and every device name.
        ("Foo.", "Foo.md"),
        ("Foo . ", "Foo.md"),
        ("CON", "CON-.md"),
        ("com1", "com1-.md"),
        ("Console", "Console.md"),
    ],
)
def test_candidate_filename_is_flat_and_path_safe(name: str, expected: str):
    """# @layer: unit  # @spec: 282-discarded-topic-links"""
    assert candidate_filename(name) == expected
    # Idempotent: the stem read back off disk locates the same file.
    assert candidate_filename(expected.removesuffix(".md")) == expected


def test_review_actions_refuse_a_slug_that_escapes_the_wiki(tmp_path: Path):
    """Every reviewer slug is sanitized and contained. # @layer: unit  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("untouchable\n", encoding="utf-8")
    (wiki / "candidates" / "entities" / "Junk.md").write_text(
        '---\ntitle: "Junk"\ntype: entity\nstatus: candidate\n---\n\n# Junk\n',
        encoding="utf-8",
    )
    escaping = "../../outside"

    calls = {
        "promote": lambda: promote(escaping, wiki),
        "flip-promote": lambda: flip_and_promote(escaping, wiki),
        "discard": lambda: discard(escaping, wiki, reason="noise"),
        "merge-slug": lambda: merge(escaping, wiki, into_slug="Junk"),
        "merge-into": lambda: merge("Junk", wiki, into_slug=escaping),
        "rewrite-key-facts": lambda: rewrite_key_facts(
            escaping, wiki, synthesizer=_FakeSynthesizer()
        ),
        "redirect": lambda: find_live_page(wiki, escaping),
    }
    for name, call in calls.items():
        with pytest.raises((FileNotFoundError, ValueError)):
            call()
        assert outside.read_text(encoding="utf-8") == "untouchable\n", name


def test_slug_resolution_refuses_a_page_symlinked_out_of_the_wiki(tmp_path: Path):
    """Containment backstop for every caller. # @layer: unit  # @spec: 282-discarded-topic-links"""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "Escaped.md").write_text(
        '---\ntitle: "Escaped"\ntype: entity\n---\n\n# Escaped\n\n## Key Facts\n',
        encoding="utf-8",
    )
    (wiki / "entities").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="escapes"):
        rewrite_key_facts("Escaped", wiki, synthesizer=_FakeSynthesizer())


def test_rewrite_key_facts_slug_folds_case_and_punctuation(tmp_path: Path):
    """The `--slug` fold covers trusted pages too. # @layer: unit  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    _write_subject_with_evidence(wiki)
    promote("Subject", wiki)

    path = rewrite_key_facts(
        "sub-ject", wiki, synthesizer=_FakeSynthesizer("- A fact. [[alpha]]\n"),
    )
    assert path == wiki / "entities" / "Subject.md"


def test_rewrite_key_facts_refuses_an_ambiguous_slug(tmp_path: Path):
    """# @layer: unit  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    for sub, stem in (("entities", "My-Entity"), ("concepts", "My Entity")):
        (wiki / sub / f"{stem}.md").write_text(
            f'---\ntitle: "{stem}"\ntype: {sub[:-1]}\n---\n\n# {stem}\n\n## Key Facts\n',
            encoding="utf-8",
        )

    with pytest.raises(ValueError, match="trusted page 'MyEntity' is ambiguous"):
        rewrite_key_facts("MyEntity", wiki, synthesizer=_FakeSynthesizer())


def test_slug_resolution_never_lands_on_a_folder_context_stub(tmp_path: Path):
    """`_context.md` describes a folder, it is not a page. # @layer: unit  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    (wiki / "entities" / "_context.md").write_text(
        "Entities live here.\n", encoding="utf-8",
    )
    (wiki / "candidates" / "entities" / "_context.md").write_text(
        "Pending stubs live here.\n", encoding="utf-8",
    )

    for slug in ("context", "_context"):
        with pytest.raises(FileNotFoundError):
            rewrite_key_facts(slug, wiki, synthesizer=_FakeSynthesizer())
        with pytest.raises(FileNotFoundError):
            _find_candidate(slug, wiki, None)


def test_discard_leaves_no_link_outside_archive(tmp_path: Path):
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    _harvest(wiki, {
        "a": "Uses [[Junk]] and [[Keep]].",
        "b": "Mentions [[junk|the junk]] and [[Keep]].",
        "c": "See [[Junk#Usage]].",
    })
    (wiki / "entities" / "Keep.md").write_text(
        '---\ntitle: "Keep"\ntype: entity\n---\n\n# Keep\n\n## Connections\n- [[Junk]]\n',
        encoding="utf-8",
    )

    result = discard("Junk", wiki, reason="noise")

    live = _live_text(wiki)
    assert "[[Junk" not in live and "[[junk" not in live
    assert "Mentions the junk and [[Keep]]." in live
    assert "See Junk." in live
    assert result.links_rewritten == 4
    assert result.redirect is None
    assert sorted(result.pages_changed) == [
        "entities/Keep.md", "sources/a.md", "sources/b.md", "sources/c.md",
    ]
    reason = result.path.with_suffix(".reason.txt").read_text(encoding="utf-8")
    assert "Original path: candidates/entities/Junk.md" in reason
    assert "Redirected to" not in reason


def test_discard_keeps_links_a_live_page_still_answers(tmp_path: Path):
    """A same-named trusted page means the links are not dangling."""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "concepts", "Bash")
    (wiki / "entities" / "bash.md").write_text("# bash\n", encoding="utf-8")
    (wiki / "sources" / "s.md").write_text("Run [[Bash]].\n", encoding="utf-8")

    result = discard("Bash", wiki, reason="duplicate")

    assert result.links_rewritten == 0
    assert (wiki / "sources" / "s.md").read_text(encoding="utf-8") == "Run [[Bash]].\n"


def test_discard_redirect_points_links_at_page_and_records_alias(tmp_path: Path):
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    _harvest(wiki, {"a": "Uses [[Old Name]].", "b": "Uses [[old name|it]]."})
    target = wiki / "concepts" / "Proper.md"
    target.write_text('---\ntitle: "Proper"\ntype: concept\n---\n\n# Proper\n', encoding="utf-8")

    result = discard("Old Name", wiki, reason="duplicate", redirect="proper")

    assert result.redirect == "Proper"
    assert result.links_rewritten == 2
    live = _live_text(wiki)
    assert "Uses [[Proper|Old Name]]." in live
    assert "Uses [[Proper|it]]." in live
    body = target.read_text(encoding="utf-8")
    alias_map = build_page_alias_map({"Proper": body})
    assert resolve_wikilink_target("old-name", {"Proper"}, alias_map) == "Proper"
    assert "- Old Name — redirected " in body
    assert "(2 source pages)" in body
    reason = result.path.with_suffix(".reason.txt").read_text(encoding="utf-8")
    assert "Redirected to: Proper" in reason
    # Redirected names resolve through the alias, so they are not "discarded".
    assert discarded_names(wiki) == {}


def test_discard_redirect_always_writes_reason_file(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Dup")
    (wiki / "entities" / "Main.md").write_text("# Main\n", encoding="utf-8")
    result = discard("Dup", wiki, redirect="Main")
    assert "Redirected to: Main" in result.path.with_suffix(".reason.txt").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("redirect", ["Nowhere", "Pending"])
def test_discard_redirect_refuses_non_live_target_before_moving(
    tmp_path: Path, redirect: str
):
    """A redirect must land on a page that stays — not a candidate, not missing."""
    wiki = _mk_wiki(tmp_path)
    stub = _write_candidate(wiki, "entities", "Dup")
    _write_candidate(wiki, "entities", "Pending")
    with pytest.raises(FileNotFoundError):
        discard("Dup", wiki, redirect=redirect)
    assert stub.is_file()


def test_discard_redirect_refuses_itself(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    stub = _write_candidate(wiki, "entities", "dup")
    (wiki / "entities" / "Dup.md").write_text("# Dup\n", encoding="utf-8")
    with pytest.raises(ValueError):
        discard("dup", wiki, redirect="Dup")
    assert stub.is_file()


def test_discarded_names_excludes_merged_candidates(tmp_path: Path):
    """# @layer: unit  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Noise")
    _write_candidate(wiki, "entities", "Dup")
    (wiki / "entities" / "Main.md").write_text("# Main\n", encoding="utf-8")
    discard("Noise", wiki, reason="noise")
    merge("Dup", wiki, into_slug="Main")
    assert discarded_names(wiki) == {"noise": "Noise"}


def test_cli_discard_redirect_prints_counts(tmp_path: Path, capsys):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Dup")
    (wiki / "entities" / "Main.md").write_text("# Main\n", encoding="utf-8")
    (wiki / "sources" / "s.md").write_text("See [[Dup]].\n", encoding="utf-8")
    args = build_parser().parse_args([
        "candidates", "discard", "--slug", "Dup", "--redirect", "Main",
        "--wiki-dir", str(wiki),
    ])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "redirected 1 link(s) to [[Main]] in 1 page(s)" in out
    assert (wiki / "sources" / "s.md").read_text(encoding="utf-8") == "See [[Main|Dup]].\n"


def test_cli_discard_unknown_redirect_is_an_error(tmp_path: Path, capsys):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Dup")
    args = build_parser().parse_args([
        "candidates", "discard", "--slug", "Dup", "--redirect", "Nowhere",
        "--wiki-dir", str(wiki),
    ])
    assert args.func(args) == 2
    assert "redirect target not found" in capsys.readouterr().err


def test_discard_redirect_refuses_a_name_another_live_page_owns(tmp_path: Path):
    """Two live pages must never answer to one name. # @layer: unit  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    stub = _write_candidate(wiki, "entities", "Dup")
    (wiki / "entities" / "Main.md").write_text("# Main\n", encoding="utf-8")
    (wiki / "concepts" / "dup.md").write_text("# dup\n", encoding="utf-8")
    (wiki / "sources" / "s.md").write_text("See [[Dup]].\n", encoding="utf-8")

    with pytest.raises(ValueError, match="concepts/dup.md already answers"):
        discard("Dup", wiki, redirect="Main")

    assert stub.is_file()
    assert "## Aliases" not in (wiki / "entities" / "Main.md").read_text(encoding="utf-8")
    assert (wiki / "sources" / "s.md").read_text(encoding="utf-8") == "See [[Dup]].\n"


def test_discard_redirect_leaves_the_target_unlinked_to_itself(tmp_path: Path):
    """The redirect target's own mention reads as text, not a self-link. # @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    _harvest(wiki, {"a": "Uses [[Old Name]].", "b": "Uses [[old name|it]]."})
    target = wiki / "concepts" / "Proper.md"
    target.write_text(
        '---\ntitle: "Proper"\ntype: concept\n---\n\n# Proper\n\n'
        "## Connections\n- [[Old Name]] — the same thing\n",
        encoding="utf-8",
    )

    result = discard("Old Name", wiki, reason="duplicate", redirect="proper")

    body = target.read_text(encoding="utf-8")
    assert "- Old Name — the same thing" in body
    assert "[[Proper|Old Name]]" not in body
    assert result.links_rewritten == 3
    assert "concepts/Proper.md" in result.pages_changed
    # The alias still resolves the name, without the page linking to itself.
    assert parse_page_aliases(body) == ["Old Name"]


def test_record_redirect_alias_round_trips_a_name_with_an_em_dash(tmp_path: Path):
    """Re-running a redirect appends nothing. # @layer: unit  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    page = wiki / "entities" / "Main.md"
    page.write_text('---\ntitle: "Main"\ntype: entity\n---\n\n# Main\n', encoding="utf-8")

    assert record_redirect_alias(page, "A — B", source_count=2) is True
    assert record_redirect_alias(page, "a—b", source_count=2) is False

    body = page.read_text(encoding="utf-8")
    assert body.count("redirected") == 1
    assert parse_page_aliases(body) == ["A — B"]


def _write_undecodable_page(wiki: Path, rel: str) -> Path:
    path = wiki / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'---\ntitle: "bad"\n---\n\n\xff\xfe See [[Junk]].\n')
    return path


def test_discard_names_the_pages_it_could_not_read(tmp_path: Path):
    """A page that cannot be read is reported, not skipped in silence. # @layer: unit  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Junk")
    (wiki / "sources" / "s.md").write_text("See [[Junk]].\n", encoding="utf-8")
    _write_undecodable_page(wiki, "sources/broken.md")

    result = discard("Junk", wiki, reason="noise")

    assert result.links_rewritten == 1
    assert result.skipped
    assert all(entry.startswith("sources/broken.md:") for entry in result.skipped)


def test_cli_discard_warns_about_pages_it_could_not_read(tmp_path: Path, capsys):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Junk")
    _write_undecodable_page(wiki, "sources/broken.md")
    args = build_parser().parse_args([
        "candidates", "discard", "--slug", "Junk", "--wiki-dir", str(wiki),
    ])

    assert args.func(args) == 0

    err = capsys.readouterr().err
    assert "could not be read" in err
    assert "sources/broken.md" in err


@pytest.mark.parametrize("action", ["promote", "flip-promote", "merge", "list"])
def test_cli_candidates_refuses_redirect_on_anything_but_discard(
    tmp_path: Path, capsys, action: str,
):
    """The one-off CLI refuses the flag instead of dropping it. # @layer: unit  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Dup")
    args = build_parser().parse_args([
        "candidates", action, "--slug", "Dup", "--into", "Main",
        "--redirect", "Main", "--wiki-dir", str(wiki),
    ])

    assert args.func(args) == 2
    assert "redirect applies only to discard" in capsys.readouterr().err
    assert (wiki / "candidates" / "entities" / "Dup.md").is_file()


# ─── stale_candidates ────────────────────────────────────────────────


def test_stale_returns_only_old_candidates(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Old", date="2026-01-01")
    _write_candidate(wiki, "entities", "New", date="2026-04-15")
    now = datetime(2026, 4, 17, tzinfo=UTC)
    stale = stale_candidates(wiki, threshold_days=30, now=now)
    assert len(stale) == 1
    assert stale[0]["slug"] == "Old"


def test_stale_custom_threshold(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Medium", date="2026-04-05")
    now = datetime(2026, 4, 17, tzinfo=UTC)
    # age = 12 days; threshold 10 → stale; threshold 30 → not stale
    assert len(stale_candidates(wiki, threshold_days=10, now=now)) == 1
    assert len(stale_candidates(wiki, threshold_days=30, now=now)) == 0


# ─── Internals ───────────────────────────────────────────────────────


def test_parse_frontmatter_valid():
    meta, body = _parse_frontmatter('---\ntitle: "Foo"\ntype: entity\n---\n\nBody.\n')
    assert meta == {"title": "Foo", "type": "entity"}
    assert body.strip() == "Body."


def test_parse_frontmatter_missing():
    meta, body = _parse_frontmatter("no frontmatter")
    assert meta == {}
    assert body == "no frontmatter"


def test_age_days_none_returns_zero():
    assert _age_days(None) == 0


def test_age_days_invalid_returns_zero():
    assert _age_days("not-a-date") == 0


def test_age_days_computes_correctly():
    now = datetime(2026, 4, 17, tzinfo=UTC)
    assert _age_days("2026-04-01", now=now) == 16


def test_rewrite_status_replaces_existing():
    text = (
        '---\ntitle: X\nstatus: candidate\n---\n\nbody\n'
    )
    result = _rewrite_status(text, old="candidate", new="reviewed")
    assert "status: reviewed" in result
    assert "status: candidate" not in result


def test_rewrite_status_adds_when_missing():
    text = '---\ntitle: X\n---\n\nbody\n'
    result = _rewrite_status(text, old="candidate", new="reviewed")
    assert "status: reviewed" in result


# ─── Lint rule integration ───────────────────────────────────────────


def test_stale_candidates_lint_rule_registered():
    assert "stale_candidates" in REGISTRY


# ─── Slash command ───────────────────────────────────────────────────


def test_wiki_candidates_slash_command_exists():
    """#272: renamed from `wiki-review` → `wiki-candidates` so the slash
    matches the CLI subcommand (`llmwiki candidates …`)."""
    cmd = REPO_ROOT / "llmwiki" / "agent_kit" / "commands" / "wiki-candidates.md"
    assert cmd.is_file()
    text = cmd.read_text(encoding="utf-8")
    assert "promote" in text
    assert "flip-promote" in text
    assert "merge" in text
    assert "discard" in text
    assert "Key Facts" in text  # #103: promote fills empty Key Facts
    assert "candidates.html" in text
    assert "mv " not in text.lower() or "Do **not** hand-`mv`" in text
    # And the old name must be gone so docs can't regress.
    old = REPO_ROOT / "llmwiki" / "agent_kit" / "commands" / "wiki-review.md"
    assert not old.exists(), "old /wiki-review name should be removed"
    assert not (REPO_ROOT / ".claude" / "commands" / "wiki-review.md").exists()


# ─── Flip + promote / same-table merge (#97) ───────────────────────────


def test_flip_and_promote_entity_to_concept(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Misfiled")

    dest = flip_and_promote("Misfiled", wiki)

    assert dest == wiki / "concepts" / "Misfiled.md"
    assert not (wiki / "candidates" / "entities" / "Misfiled.md").exists()
    text = dest.read_text(encoding="utf-8")
    assert "status: reviewed" in text
    assert "type: concept" in text


def test_flip_and_promote_concept_to_entity(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "concepts", "Toolish")

    dest = flip_and_promote("Toolish", wiki)

    assert dest == wiki / "entities" / "Toolish.md"
    assert "type: entity" in dest.read_text(encoding="utf-8")


def test_merge_into_pending_same_table(tmp_path: Path) -> None:
    """#97: merge dropdown is same-table — target may still be a candidate."""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Dup", body="# Dup\n\nextra.")
    _write_candidate(wiki, "entities", "Canonical", body="# Canonical\n\nkeep.")

    dest = merge("Dup", wiki, into_slug="Canonical")

    assert dest == wiki / "candidates" / "entities" / "Canonical.md"
    text = dest.read_text(encoding="utf-8")
    assert "## Candidate merge" in text
    assert "extra." in text
    assert not (wiki / "candidates" / "entities" / "Dup.md").exists()


def test_cli_flip_promote_action_registered() -> None:
    parser = build_parser()
    args = parser.parse_args(["candidates", "flip-promote", "--slug", "X"])
    assert args.action == "flip-promote"


def test_cli_flip_promote_unknown_slug_is_an_error(tmp_path: Path, capsys):
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    args = build_parser().parse_args([
        "candidates", "flip-promote", "--slug", "Ghost", "--wiki-dir", str(wiki),
    ])
    assert args.func(args) == 2
    assert capsys.readouterr().err.startswith("error: candidate not found")


def test_cli_flip_promote_ambiguous_slug_is_an_error(tmp_path: Path, capsys):
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Junk")
    _write_candidate(wiki, "entities", "junk")
    args = build_parser().parse_args([
        "candidates", "flip-promote", "--slug", "JUNK", "--wiki-dir", str(wiki),
    ])
    assert args.func(args) == 2
    assert "is ambiguous" in capsys.readouterr().err


# ─── CLI integration ────────────────────────────────────────────────


def test_cli_candidates_subcommand_registered():
    parser = build_parser()
    sub_action = None
    for a in parser._actions:
        if hasattr(a, "choices") and a.choices:
            sub_action = a
            break
    assert sub_action is not None
    assert "candidates" in sub_action.choices
