"""A number-shaped session slug keeps its exact text in the page filename (#265).

The frontmatter reader keeps ``slug:`` as written, so ``0123`` stays ``0123``
and ``12e4`` stays ``12e4`` instead of turning into a number. The page filename
therefore carries the slug exactly as the converter wrote it —
``<date>-<slug>`` — and never falls back to the whole raw stem, which doubled
the date into the name. Raw names and titles are built with the converter's
own helpers, so a change to either format fails here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.convert import flat_output_name, session_title
from llmwiki.synth.base import DummySynthesizer
from llmwiki.synth.pipeline import synth_page_filename, synthesize_new_sessions

_STARTED = datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
_DATE = "2026-07-01"
_PROJECT = "demo-proj"

_RAW = """---
title: "{title}"
type: source
date: {date}
slug: {slug}
project: {project}
---

# Session

Synthetic transcript body.
"""


def _raw_text(slug: str) -> str:
    return _RAW.format(
        title=session_title(slug, _DATE), date=_DATE, slug=slug, project=_PROJECT
    )


@pytest.mark.parametrize(
    ("slug", "disambiguator"),
    [
        ("68657849", ""),
        ("0123", ""),
        ("12e4", ""),
        ("1e-5", ""),
        ("true", ""),
        ("0123", "abcd1234"),
    ],
)
def test_number_shaped_slug_keeps_its_text(slug: str, disambiguator: str) -> None:
    meta, _body = parse_frontmatter(_raw_text(slug))
    assert meta["slug"] == slug
    stem = flat_output_name(
        _STARTED, _PROJECT, slug, disambiguator=disambiguator
    ).removesuffix(".md")

    assert synth_page_filename(meta, stem) == f"{_DATE}-{slug}"


def test_text_slug_is_unchanged() -> None:
    meta, _body = parse_frontmatter(_raw_text("brave-otter"))

    assert synth_page_filename(meta, "whatever") == f"{_DATE}-brave-otter"


def test_non_string_slug_from_a_built_dict_is_used_as_text() -> None:
    meta = {"slug": 42, "date": _DATE}

    assert synth_page_filename(meta, "notes") == f"{_DATE}-42"


def test_synth_writes_the_page_under_the_literal_slug(tmp_path: Path) -> None:
    sessions = tmp_path / "raw" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / flat_output_name(_STARTED, _PROJECT, "0123")).write_text(
        _raw_text("0123"), encoding="utf-8"
    )
    sources = tmp_path / "wiki" / "sources"
    sources.mkdir(parents=True)

    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=sessions,
        docs_dir=tmp_path / "raw" / "docs",
        wiki_sources_dir=sources,
        log_path=tmp_path / "wiki" / "log.md",
        state_file=tmp_path / "state.json",
        include_subagents="all",
        exclude_headless=False,
    )

    assert summary["synthesized"] == 1
    assert [p.name for p in (sources / _PROJECT).iterdir()] == [f"{_DATE}-0123.md"]
