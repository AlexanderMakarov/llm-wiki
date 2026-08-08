"""Provenance walker unit tests (#122).

Covers ``llmwiki.trace.trace_page``: full chain, missing hops, empty
provenance, unresolvable start pages, and path-traversal rejection.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.trace import TraceError, TraceHop, trace_page


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / "raw" / "sessions").mkdir(parents=True)
    return vault


def _roles(result) -> list[tuple[str, str]]:
    return [(h.role, h.status) for h in result.hops]


# ─── full chain ───────────────────────────────────────────────────────────


def test_full_chain_entity_to_source_to_raw(tmp_path: Path):
    vault = _vault(tmp_path)
    raw = _write(
        vault / "raw" / "sessions" / "2026-01-01T12-00-demo-kickoff.md",
        '---\ntitle: "Kickoff transcript"\ntype: source\n---\n\nbody\n',
    )
    _write(
        vault / "wiki" / "sources" / "kickoff.md",
        (
            '---\ntitle: "Kickoff session"\ntype: source\n'
            "source_file: raw/sessions/2026-01-01T12-00-demo-kickoff.md\n"
            "---\n\n## Summary\n\nok\n"
        ),
    )
    entity = _write(
        vault / "wiki" / "entities" / "Demo.md",
        (
            '---\ntitle: "Demo"\ntype: entity\nsources: [kickoff]\n'
            "last_updated: 2026-01-02\n---\n\n# Demo\n"
        ),
    )

    result = trace_page(vault, "wiki/entities/Demo.md")

    assert _roles(result) == [
        ("page", "ok"),
        ("source", "ok"),
        ("raw", "ok"),
    ]
    page, source, raw_hop = result.hops
    assert isinstance(page, TraceHop)
    assert page.title == "Demo"
    assert page.location == "wiki/entities/Demo.md"
    assert source.title == "Kickoff session"
    assert source.location == "wiki/sources/kickoff.md"
    assert raw_hop.title == "Kickoff transcript"
    assert raw_hop.location == raw.relative_to(vault.resolve()).as_posix()
    # Locator by stem also resolves.
    by_name = trace_page(vault, "Demo")
    assert by_name.hops[0].location == entity.relative_to(vault.resolve()).as_posix()
    assert _roles(by_name) == _roles(result)


def test_full_chain_from_source_page_emits_raw(tmp_path: Path):
    vault = _vault(tmp_path)
    _write(
        vault / "raw" / "sessions" / "sess.md",
        '---\ntitle: "Raw Sess"\n---\n\nx\n',
    )
    _write(
        vault / "wiki" / "sources" / "sess.md",
        (
            '---\ntitle: "Sess summary"\ntype: source\n'
            "source_file: raw/sessions/sess.md\n---\n\n## Summary\n\nok\n"
        ),
    )

    result = trace_page(vault, "wiki/sources/sess.md")

    assert _roles(result) == [("page", "ok"), ("raw", "ok")]
    assert result.hops[1].location == "raw/sessions/sess.md"
    assert result.hops[1].title == "Raw Sess"


# ─── missing hops (still succeed) ─────────────────────────────────────────


def test_missing_source_slug_is_marked(tmp_path: Path):
    vault = _vault(tmp_path)
    _write(
        vault / "wiki" / "entities" / "Orphan.md",
        (
            '---\ntitle: "Orphan"\ntype: entity\n'
            "sources: [gone-slug]\n---\n\n# Orphan\n"
        ),
    )

    result = trace_page(vault, "Orphan")

    assert _roles(result) == [("page", "ok"), ("source", "missing")]
    missing = result.hops[1]
    assert missing.role == "source"
    assert missing.title == "gone-slug"
    assert missing.location == "gone-slug"


def test_missing_raw_file_is_marked(tmp_path: Path):
    vault = _vault(tmp_path)
    _write(
        vault / "wiki" / "sources" / "dangling.md",
        (
            '---\ntitle: "Dangling"\ntype: source\n'
            "source_file: raw/sessions/does-not-exist.md\n---\n\n## Summary\n\nx\n"
        ),
    )
    _write(
        vault / "wiki" / "concepts" / "Idea.md",
        (
            '---\ntitle: "Idea"\ntype: concept\nsources: [dangling]\n'
            "---\n\n# Idea\n"
        ),
    )

    result = trace_page(vault, "wiki/concepts/Idea.md")

    assert _roles(result) == [
        ("page", "ok"),
        ("source", "ok"),
        ("raw", "missing"),
    ]
    raw_hop = result.hops[2]
    assert raw_hop.location == "raw/sessions/does-not-exist.md"
    assert raw_hop.status == "missing"


def test_partial_chain_keeps_valid_hops(tmp_path: Path):
    """One missing source does not drop a sibling chain that still resolves."""
    vault = _vault(tmp_path)
    _write(
        vault / "raw" / "sessions" / "good.md",
        '---\ntitle: "Good raw"\n---\n\nx\n',
    )
    _write(
        vault / "wiki" / "sources" / "good.md",
        (
            '---\ntitle: "Good src"\ntype: source\n'
            "source_file: raw/sessions/good.md\n---\n\n## Summary\n\nok\n"
        ),
    )
    _write(
        vault / "wiki" / "entities" / "Mixed.md",
        (
            '---\ntitle: "Mixed"\ntype: entity\n'
            "sources: [missing-one, good]\n---\n\n# Mixed\n"
        ),
    )

    result = trace_page(vault, "Mixed")

    assert _roles(result) == [
        ("page", "ok"),
        ("source", "missing"),
        ("source", "ok"),
        ("raw", "ok"),
    ]


# ─── no provenance ────────────────────────────────────────────────────────


def test_page_with_no_provenance(tmp_path: Path):
    vault = _vault(tmp_path)
    _write(
        vault / "wiki" / "entities" / "Bare.md",
        '---\ntitle: "Bare"\ntype: entity\n---\n\n# Bare\n\nno sources\n',
    )

    result = trace_page(vault, "Bare")

    assert len(result.hops) == 1
    assert result.hops[0].role == "page"
    assert result.hops[0].status == "ok"
    assert result.hops[0].title == "Bare"


# ─── unresolvable start / traversal ───────────────────────────────────────


def test_unresolvable_start_page_raises(tmp_path: Path):
    vault = _vault(tmp_path)
    _write(vault / "wiki" / "index.md", "# Wiki Index\n")

    with pytest.raises(TraceError, match="page not found"):
        trace_page(vault, "DoesNotExist")

    with pytest.raises(TraceError, match="page not found"):
        trace_page(vault, "wiki/entities/Missing.md")

    with pytest.raises(TraceError, match="empty page locator"):
        trace_page(vault, "   ")


def test_traversal_rejection(tmp_path: Path):
    vault = _vault(tmp_path)
    _write(vault / "wiki" / "entities" / "Safe.md", '---\ntitle: "Safe"\n---\n')
    # Outside the vault — must not resolve even if a sibling file exists.
    secret = tmp_path / "secret.md"
    secret.write_text("outside\n", encoding="utf-8")

    with pytest.raises(TraceError, match="path outside vault|page not found"):
        trace_page(vault, "../secret.md")

    with pytest.raises(TraceError, match="path outside vault|page not found"):
        trace_page(vault, "wiki/../../secret.md")

    with pytest.raises(TraceError, match="path outside vault|page not found"):
        trace_page(vault, str(secret))
