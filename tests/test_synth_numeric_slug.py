"""A number-shaped session slug keeps its exact text in the page filename (#265).

The stdlib frontmatter parser turns ``slug: 68657849`` into an int, ``0123``
into ``123`` and ``12e4`` into a float. The page filename must still carry the
slug exactly as the converter wrote it — ``<date>-<slug>`` — and never fall
back to the whole raw stem, which doubles the date into the name.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.synth.base import DummySynthesizer
from llmwiki.synth.pipeline import synth_page_filename, synthesize_new_sessions

_RAW = """---
title: "Session: {slug} — 2026-07-01"
type: source
date: 2026-07-01
slug: {slug}
project: demo-proj
---

# Session

Synthetic transcript body.
"""


@pytest.mark.parametrize(
    ("slug", "suffix"),
    [
        ("68657849", ""),
        ("0123", ""),
        ("12e4", ""),
        ("1e-5", ""),
        ("true", ""),
        ("0123", "--abcd1234"),
    ],
)
def test_number_shaped_slug_keeps_its_text(slug: str, suffix: str) -> None:
    meta, _body = parse_frontmatter(_RAW.format(slug=slug))
    assert not isinstance(meta["slug"], str)
    stem = f"2026-07-01T10-00-demo-proj-{slug}{suffix}"

    assert synth_page_filename(meta, stem) == f"2026-07-01-{slug}"


def test_text_slug_is_unchanged() -> None:
    meta, _body = parse_frontmatter(_RAW.format(slug="brave-otter"))

    assert synth_page_filename(meta, "whatever") == "2026-07-01-brave-otter"


def test_unrecoverable_slug_falls_back_to_the_stem() -> None:
    meta = {"slug": 42, "date": "2026-07-01"}

    assert synth_page_filename(meta, "notes") == "2026-07-01-notes"


def test_synth_writes_the_page_under_the_literal_slug(tmp_path: Path) -> None:
    sessions = tmp_path / "raw" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "2026-07-01T10-00-demo-proj-0123.md").write_text(
        _RAW.format(slug="0123"), encoding="utf-8"
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
    assert [p.name for p in (sources / "demo-proj").iterdir()] == [
        "2026-07-01-0123.md"
    ]
