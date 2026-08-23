"""Tests for ``llmwiki/source_topics.py`` — topic bullets on source pages (#147)."""

from __future__ import annotations

from llmwiki.source_topics import (
    TopicRecord,
    parse_source_topics,
    source_page_needs_topics_rewrite,
)

# ─── parse_source_topics ────────────────────────────────────────────────────


def test_happy_path_entity_and_concept_with_facts() -> None:
    body = """\
## Connections
- [[OpenAI]] (entity) — AI company
  - fact: Founded in 2015.
  - fact: Releases GPT models.
- [[RAG]] (concept) — retrieval-augmented generation
  - fact: Combines search with generation.
"""
    records = parse_source_topics(body)
    assert records == [
        TopicRecord(
            name="OpenAI",
            kind="entity",
            description="AI company",
            facts=["Founded in 2015.", "Releases GPT models."],
        ),
        TopicRecord(
            name="RAG",
            kind="concept",
            description="retrieval-augmented generation",
            facts=["Combines search with generation."],
        ),
    ]


def test_missing_kind_yields_none() -> None:
    body = "- [[OpenAI]] — AI company\n"
    records = parse_source_topics(body)
    assert len(records) == 1
    assert records[0].name == "OpenAI"
    assert records[0].kind is None
    assert records[0].description == "AI company"


def test_invalid_kind_yields_none() -> None:
    body = "- [[OpenAI]] (project) — not a usable kind\n"
    records = parse_source_topics(body)
    assert len(records) == 1
    assert records[0].kind is None
    assert records[0].description == "not a usable kind"


def test_description_only() -> None:
    body = "- [[OpenAI]] (entity) — AI company\n"
    records = parse_source_topics(body)
    assert records == [
        TopicRecord(name="OpenAI", kind="entity", description="AI company", facts=[]),
    ]


def test_facts_only() -> None:
    body = """\
- [[OpenAI]] (entity)
  - fact: Founded in 2015.
"""
    records = parse_source_topics(body)
    assert records == [
        TopicRecord(
            name="OpenAI",
            kind="entity",
            description="",
            facts=["Founded in 2015."],
        ),
    ]


def test_empty_body_parses_to_empty() -> None:
    assert parse_source_topics("") == []


# ─── source_page_needs_topics_rewrite ───────────────────────────────────────


def test_missing_kind_needs_rewrite() -> None:
    body = """\
## Connections
- [[OpenAI]] — AI company
"""
    assert source_page_needs_topics_rewrite(body) is True


def test_kind_present_does_not_need_rewrite() -> None:
    body = """\
## Connections
- [[OpenAI]] (entity) — AI company
- [[BareLink]] — no kind here
"""
    assert source_page_needs_topics_rewrite(body) is False


def test_old_connections_bullets_need_rewrite() -> None:
    """Legacy Connections shape: ``- [[Name]] — how`` without ``(kind)``."""
    body = """\
## Connections
- [[OpenAI]] — how they relate
- [[RAG]] — how it connects
"""
    assert source_page_needs_topics_rewrite(body) is True


def test_empty_body_does_not_need_rewrite() -> None:
    assert source_page_needs_topics_rewrite("") is False
