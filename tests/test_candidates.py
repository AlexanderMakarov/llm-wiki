"""Tests for wiki/candidates/ approval workflow (v1.1.0, #51)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from llmwiki.candidates import (
    ARCHIVE_DIR_NAME,
    CANDIDATES_DIR_NAME,
    DEFAULT_STALE_DAYS,
    MIRRORED_SUBDIRS,
    KeyFactsBackendError,
    _age_days,
    _parse_frontmatter,
    _rewrite_status,
    apply_review_summary_to_pipeline,
    archive_dir,
    candidate_review_summary,
    candidates_dir,
    discard,
    fill_key_facts_from_evidence,
    is_candidate,
    list_candidates,
    merge,
    promote,
    stale_candidates,
)
from llmwiki.cli import build_parser
from llmwiki.lint import (
    REGISTRY,
    rules,  # noqa: F401
)
from llmwiki.synth.base import BaseSynthesizer, DummySynthesizer

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


def _write_subject_with_evidence(wiki: Path) -> Path:
    """A harvest stub whose two sources each name it twice."""
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


def test_promote_writes_llm_authored_key_facts(tmp_path: Path):
    """#103: the backend writes Key Facts; promote only places them."""
    wiki = _mk_wiki(tmp_path)
    _write_subject_with_evidence(wiki)
    fake = _FakeSynthesizer(
        "- Serves as the auth layer for the platform. [[alpha]]\n"
        "- Was scheduled for staged rollout. [[beta]]\n"
    )

    text = promote("Subject", wiki, synthesizer=fake).read_text(encoding="utf-8")
    assert "status: reviewed" in text
    assert "- Serves as the auth layer for the platform. [[alpha]]" in text
    assert "- Was scheduled for staged rollout. [[beta]]" in text


def test_key_facts_evidence_includes_every_mention_line(tmp_path: Path):
    """The line that describes an entity is often not its first mention."""
    wiki = _mk_wiki(tmp_path)
    _write_subject_with_evidence(wiki)
    fake = _FakeSynthesizer("- A fact. [[alpha]]\n")

    promote("Subject", wiki, synthesizer=fake)
    evidence = fake.calls[0]["body"]
    assert "work landed alongside" in evidence
    assert "built the auth layer" in evidence
    assert "rollout planning" in evidence


def test_promote_raises_without_llm_backend(tmp_path: Path):
    """#103: no backend means no Key Facts — never regex-assembled prose."""
    wiki = _mk_wiki(tmp_path)
    candidate = _write_subject_with_evidence(wiki)

    with pytest.raises(KeyFactsBackendError):
        promote("Subject", wiki)
    assert candidate.exists(), "failed promote must leave the candidate in place"


def test_promote_rejects_dummy_backend(tmp_path: Path):
    """The canned offline backend must not author knowledge-layer prose."""
    wiki = _mk_wiki(tmp_path)
    _write_subject_with_evidence(wiki)

    with pytest.raises(KeyFactsBackendError):
        promote("Subject", wiki, synthesizer=DummySynthesizer())


def test_promote_raises_when_backend_returns_no_bullets(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_subject_with_evidence(wiki)

    with pytest.raises(KeyFactsBackendError):
        promote("Subject", wiki, synthesizer=_FakeSynthesizer("I cannot help.\n"))


def test_promote_key_facts_drop_preamble_and_cap_at_five(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_subject_with_evidence(wiki)
    fake = _FakeSynthesizer(
        "Here are the facts:\n\n" +
        "".join(f"- Fact {i}. [[alpha]]\n" for i in range(8)) +
        "\nHope that helps!\n"
    )

    text = promote("Subject", wiki, synthesizer=fake).read_text(encoding="utf-8")
    assert "Here are the facts" not in text
    assert "Hope that helps" not in text
    assert text.count("- Fact ") == 5


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
    """#103: reviewer-authored Key Facts must survive promote."""
    wiki = _mk_wiki(tmp_path)
    (wiki / "sources").mkdir(parents=True, exist_ok=True)
    (wiki / "sources" / "alpha.md").write_text(
        "---\ntitle: Alpha\ntype: source\n---\n\n"
        "## Connections\n- [[Foo]] — should not overwrite\n",
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
    assert "should not overwrite" not in text


def test_fill_key_facts_is_a_no_op_for_bare_mentions(tmp_path: Path):
    """A source that only lists the name carries no fact to state."""
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


# ─── discard ────────────────────────────────────────────────────────


def test_discard_moves_to_archive(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    candidate = _write_candidate(wiki, "entities", "Bogus")
    archived = discard("Bogus", wiki, reason="hallucinated")

    assert not candidate.exists()
    assert archived.is_file()
    # Archive structure: wiki/archive/candidates/<timestamp>/Bogus.md
    assert "archive" in archived.parts
    assert "candidates" in archived.parts
    assert archived.name == "Bogus.md"


def test_discard_writes_reason_file(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Fake")
    archived = discard("Fake", wiki, reason="not a real thing")

    reason_file = archived.with_suffix(".reason.txt")
    assert reason_file.is_file()
    text = reason_file.read_text(encoding="utf-8")
    assert "not a real thing" in text
    assert "Discarded at:" in text


def test_discard_raises_when_candidate_missing(tmp_path: Path):
    wiki = _mk_wiki(tmp_path)
    with pytest.raises(FileNotFoundError):
        discard("Ghost", wiki, reason="x")


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
    cmd = REPO_ROOT / ".claude" / "commands" / "wiki-candidates.md"
    assert cmd.is_file()
    text = cmd.read_text(encoding="utf-8")
    assert "promote" in text
    assert "merge" in text
    assert "discard" in text
    assert "Key Facts" in text  # #103: promote fills empty Key Facts
    # And the old name must be gone so docs can't regress.
    old = REPO_ROOT / ".claude" / "commands" / "wiki-review.md"
    assert not old.exists(), "old /wiki-review name should be removed"


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
