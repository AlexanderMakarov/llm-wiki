"""Tests for synthesizing manually-added documents under ``raw/docs/`` (#1).

Documents added via the kbbuilder ``wikiAddDocument`` path land in
``raw/docs/<slug>.md`` but were historically never distilled into the
wiki — synthesis only ever walked ``raw/sessions/``. These tests cover:

* ``_discover_raw_docs`` — discovery of ``raw/docs/`` markdown.
* ``synthesize_new_sessions(docs_dir=...)`` — docs get source pages,
  grouped under a ``docs`` project, alongside (not instead of) sessions.
* ``_chunk_markdown`` — oversized docs are split on headings before the
  synthesis pass so they fit a single backend call.
* Regression: a doc with a non-string / missing slug must not crash.
"""

from __future__ import annotations

from pathlib import Path

from llmwiki.synth.base import DummySynthesizer
from llmwiki.synth.pipeline import (
    _chunk_markdown,
    _discover_raw_docs,
    synthesize_new_sessions,
)


DEMO_DOC = """---
title: "OpenClaw Overview"
slug: openclaw-openclaw
source_url: https://docs.openclaw.ai/
---

# OpenClaw

OpenClaw is an agent runtime. It mentions [[pytest]] and [[FastAPI]].
"""


def _seed_docs(tmp_path: Path, name: str = "openclaw-openclaw.md",
               content: str = DEMO_DOC) -> Path:
    docs = tmp_path / "raw" / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / name).write_text(content, encoding="utf-8")
    return docs


def _wiki(tmp_path: Path) -> tuple[Path, Path]:
    wiki_sources = tmp_path / "wiki" / "sources"
    wiki_sources.mkdir(parents=True)
    log_file = tmp_path / "wiki" / "log.md"
    log_file.write_text("# Log\n", encoding="utf-8")
    return wiki_sources, log_file


# ─── _discover_raw_docs ──────────────────────────────────────────────────


def test_discover_raw_docs_finds_md_files(tmp_path: Path):
    docs = _seed_docs(tmp_path)
    found = _discover_raw_docs(docs)
    assert len(found) == 1
    path, meta, body = found[0]
    assert meta["slug"] == "openclaw-openclaw"
    assert "OpenClaw is an agent runtime" in body


def test_discover_raw_docs_skips_underscore_files(tmp_path: Path):
    docs = _seed_docs(tmp_path)
    (docs / "_context.md").write_text("# ctx\n", encoding="utf-8")
    assert len(_discover_raw_docs(docs)) == 1


def test_discover_raw_docs_missing_dir(tmp_path: Path):
    assert _discover_raw_docs(tmp_path / "nope") == []


# ─── synthesize_new_sessions with docs ───────────────────────────────────


def test_synthesize_distils_raw_docs(tmp_path: Path):
    docs = _seed_docs(tmp_path)
    wiki_sources, log_file = _wiki(tmp_path)

    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=tmp_path / "raw" / "sessions",  # empty / missing
        docs_dir=docs,
        wiki_sources_dir=wiki_sources,
        log_path=log_file,
    )
    assert summary["synthesized"] == 1
    assert summary["errors"] == []
    out_file = wiki_sources / "docs" / "openclaw-openclaw.md"
    assert out_file.exists(), f"expected distilled doc at {out_file}"
    content = out_file.read_text(encoding="utf-8")
    assert "type: source" in content
    assert "## Summary" in content
    # Frontmatter project must match where the page lives (sources/docs/)
    # so the index + graph group it correctly — not "unknown".
    assert "project: docs" in content


def test_synthesize_docs_and_sessions_together(tmp_path: Path):
    # One session + one doc → both distilled, under their own projects.
    raw = tmp_path / "raw" / "sessions" / "proj"
    raw.mkdir(parents=True)
    (raw / "2026-04-09-sess.md").write_text(
        "---\nslug: sess\nproject: proj\ndate: 2026-04-09\n---\n# s\n",
        encoding="utf-8",
    )
    docs = _seed_docs(tmp_path)
    wiki_sources, log_file = _wiki(tmp_path)

    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=tmp_path / "raw" / "sessions",
        docs_dir=docs,
        wiki_sources_dir=wiki_sources,
        log_path=log_file,
    )
    assert summary["synthesized"] == 2
    assert (wiki_sources / "proj" / "2026-04-09-sess.md").exists()
    assert (wiki_sources / "docs" / "openclaw-openclaw.md").exists()


def test_synthesize_docs_idempotent_rerun_is_noop(tmp_path: Path):
    docs = _seed_docs(tmp_path)
    wiki_sources, log_file = _wiki(tmp_path)
    common = dict(
        backend=DummySynthesizer(),
        raw_dir=tmp_path / "raw" / "sessions",
        docs_dir=docs,
        wiki_sources_dir=wiki_sources,
        log_path=log_file,
    )
    s1 = synthesize_new_sessions(**common)
    assert s1["synthesized"] == 1
    s2 = synthesize_new_sessions(**common)
    assert s2["new_files"] == 0
    assert s2["synthesized"] == 0


def test_synthesize_doc_with_numeric_slug_does_not_crash(tmp_path: Path):
    # YAML parses a bare-number slug as int; the pipeline must fall back
    # to the filename stem rather than crash on slug normalisation (#1).
    docs = _seed_docs(
        tmp_path,
        name="42.md",
        content="---\nslug: 42\n---\n# numeric slug doc\n",
    )
    wiki_sources, log_file = _wiki(tmp_path)
    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=tmp_path / "raw" / "sessions",
        docs_dir=docs,
        wiki_sources_dir=wiki_sources,
        log_path=log_file,
    )
    assert summary["errors"] == []
    assert summary["synthesized"] == 1
    assert (wiki_sources / "docs" / "42.md").exists()


# ─── _chunk_markdown (oversized-doc handling) ────────────────────────────


def test_chunk_markdown_small_returns_single():
    text = "# Title\n\nShort body.\n"
    assert _chunk_markdown(text, max_chars=10_000) == [text]


def test_chunk_markdown_splits_on_headings():
    # Three ~equal sections; a small cap forces a split at heading
    # boundaries, and every chunk must start with a heading.
    sections = [f"## Section {i}\n\n" + ("word " * 200) + "\n" for i in range(3)]
    text = "\n".join(sections)
    chunks = _chunk_markdown(text, max_chars=1500)
    assert len(chunks) > 1
    for c in chunks:
        assert c.lstrip().startswith("#"), f"chunk not heading-aligned:\n{c[:60]}"
    # No content lost: every section heading survives somewhere.
    joined = "".join(chunks)
    for i in range(3):
        assert f"## Section {i}" in joined


def test_chunk_markdown_oversized_single_section_is_hard_split():
    # A single heading-less blob bigger than the cap still gets split so
    # no chunk exceeds the cap (the 6.67 MB llms-full.txt case).
    text = "x" * 5000
    chunks = _chunk_markdown(text, max_chars=1000)
    assert len(chunks) >= 5
    assert all(len(c) <= 1000 for c in chunks)
    assert "".join(chunks) == text


def test_synthesize_oversized_doc_produces_multiple_parts(tmp_path: Path):
    big = "---\nslug: big-doc\n---\n" + "\n".join(
        f"## Part {i}\n\n" + ("lorem ipsum " * 300) for i in range(6)
    )
    docs = _seed_docs(tmp_path, name="big-doc.md", content=big)
    wiki_sources, log_file = _wiki(tmp_path)
    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=tmp_path / "raw" / "sessions",
        docs_dir=docs,
        wiki_sources_dir=wiki_sources,
        log_path=log_file,
        doc_chunk_max_chars=1500,
    )
    assert summary["errors"] == []
    parts = sorted((wiki_sources / "docs").glob("big-doc--part-*.md"))
    assert len(parts) >= 2, f"expected multiple parts, got {parts}"
    # Each part is a valid source page.
    for p in parts:
        assert "type: source" in p.read_text(encoding="utf-8")
