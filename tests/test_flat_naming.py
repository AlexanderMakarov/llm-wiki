"""Tests for flat raw/ naming scheme (v1.0, #141)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from llmwiki.convert import _source_hash8, flat_output_name


def test_basic_flat_name():
    started = datetime(2026, 4, 16, 10, 30, tzinfo=UTC)
    result = flat_output_name(started, "ai-newsletter", "kind-tinkering-hejlsberg")
    assert result == "2026-04-16T10-30-ai-newsletter-kind-tinkering-hejlsberg.md"


def test_midnight():
    started = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    result = flat_output_name(started, "demo", "test")
    assert result == "2026-01-01T00-00-demo-test.md"


def test_single_digit_hour():
    started = datetime(2026, 3, 5, 9, 5, tzinfo=UTC)
    result = flat_output_name(started, "myproject", "slug")
    assert result == "2026-03-05T09-05-myproject-slug.md"


def test_ends_with_md():
    result = flat_output_name(
        datetime(2026, 4, 1, 14, 0, tzinfo=UTC),
        "proj",
        "test-slug",
    )
    assert result.endswith(".md")


def test_no_slashes_in_name():
    """Flat naming must not produce nested directories."""
    result = flat_output_name(
        datetime(2026, 4, 1, 14, 0, tzinfo=UTC),
        "my-project",
        "my-slug",
    )
    assert "/" not in result
    assert "\\" not in result


def test_chronological_sort():
    """Files should sort chronologically by name."""
    names = [
        flat_output_name(datetime(2026, 4, 16, 10, 0, tzinfo=UTC), "a", "s1"),
        flat_output_name(datetime(2026, 4, 16, 9, 0, tzinfo=UTC), "a", "s2"),
        flat_output_name(datetime(2026, 4, 15, 23, 59, tzinfo=UTC), "b", "s3"),
    ]
    assert sorted(names) == [names[2], names[1], names[0]]  # oldest first


def test_project_embedded():
    """Project slug is in the filename for traceability."""
    result = flat_output_name(
        datetime(2026, 4, 1, 14, 0, tzinfo=UTC),
        "germanly",
        "slug",
    )
    assert "germanly" in result


def test_subagent_slug():
    """Subagent slugs (with -subagent- suffix) work fine."""
    result = flat_output_name(
        datetime(2026, 4, 1, 14, 0, tzinfo=UTC),
        "research",
        "my-slug-subagent-abc12345",
    )
    assert "subagent" in result
    assert "/" not in result


# ─── #339: disambiguator for subagent + same-minute collisions ────────


def test_flat_output_name_with_disambiguator():

    ts = datetime(2026, 4, 16, 10, 0, tzinfo=UTC)
    out = flat_output_name(ts, "proj", "slug", disambiguator="ab12cd34")
    assert out == "2026-04-16T10-00-proj-slug--ab12cd34.md"


def test_flat_output_name_empty_disambiguator_stays_canonical():

    ts = datetime(2026, 4, 16, 10, 0, tzinfo=UTC)
    out_none = flat_output_name(ts, "proj", "slug")
    out_empty = flat_output_name(ts, "proj", "slug", disambiguator="")
    assert out_none == out_empty
    assert "--" not in out_none  # no spurious double-dash


def test_source_hash8_is_stable():

    a1 = _source_hash8(Path("/a/b/c.jsonl"))
    a2 = _source_hash8(Path("/a/b/c.jsonl"))
    assert a1 == a2
    assert len(a1) == 8
    # Different paths → different hashes.
    assert _source_hash8(Path("/a/b/d.jsonl")) != a1


def test_source_hash8_handles_unicode_path():

    h = _source_hash8(Path("/home/日本語/session.jsonl"))
    assert len(h) == 8
    assert all(c in "0123456789abcdef" for c in h)


def test_collision_produces_distinct_filenames():
    """#339 regression — subagents and same-minute siblings get
    distinct output names when both sources exist."""

    ts = datetime(2026, 4, 16, 10, 0, tzinfo=UTC)

    # Simulate: parent session + one subagent, same minute + slug.
    sub_src = Path("/u/.claude/projects/p/sess/subagents/agent-abc.jsonl")

    parent_name = flat_output_name(ts, "proj", "slug")
    sub_name = flat_output_name(
        ts, "proj", "slug", disambiguator=_source_hash8(sub_src),
    )

    assert parent_name != sub_name
    assert sub_name.endswith(".md")
    assert "--" in sub_name
