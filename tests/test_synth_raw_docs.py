"""Tests for synthesizing manually-added documents under ``raw/docs/`` (#1).

Documents added via the kbbuilder ``wikiAddDocument`` path land in
``raw/docs/<slug>.md`` but were historically never distilled into the
wiki — synthesis only ever walked ``raw/sessions/``. These tests cover:

* ``_discover_raw_docs`` — discovery of ``raw/docs/`` markdown.
* ``synthesize_new_sessions(docs_dir=...)`` — docs get source pages,
  grouped under a ``docs`` project, alongside (not instead of) sessions.
* ``_chunk_markdown`` — oversized docs are split in memory (headings first)
  so each chunk fits one backend call; the chunks stitch into one page (#311).
* Regression: a doc with a non-string / missing slug must not crash.
* Provenance (#307) — a doc page claims ``source_file: raw/docs/<rel>`` and is
  tagged as a document, never as a session transcript; that claim is what makes
  a repeated synthesis recognise the page instead of duplicating it.
"""

from __future__ import annotations

from pathlib import Path

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.synth.base import BaseSynthesizer, DummySynthesizer
from llmwiki.synth.pipeline import (
    _chunk_markdown,
    _discover_raw_docs,
    discover_synth_source_keys,
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
    # ``name`` may carry a sub-path — that is how `llmwiki add` lands a doc
    # (``raw/docs/<slug>/<slug>.md``).
    (docs / name).parent.mkdir(parents=True, exist_ok=True)
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


class RealSynthesizer(BaseSynthesizer):
    """Backend whose output is a real page body — not a stub (#24)."""

    name = "real"

    def is_available(self) -> bool:
        return True

    def synthesize_source_page(self, body, meta, prompt_template):
        return (
            "## Summary\n\nReal synthesis.\n\n"
            "## Connections\n\n"
            "- [[OpenClaw]] (entity) — runtime\n"
        )


def test_synthesize_docs_idempotent_rerun_is_noop(tmp_path: Path):
    docs = _seed_docs(tmp_path)
    wiki_sources, log_file = _wiki(tmp_path)
    common = dict(
        backend=RealSynthesizer(),
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


# ─── Provenance: a doc page claims its raw file (#307) ───────────────────
# @layer: integration
# @spec: 307-doc-source-provenance
# @regression


SESSION = """---
title: "Session: proj"
tags: [claude-code, session-transcript]
slug: sess
project: proj
date: 2026-04-09
source_file: raw/sessions/proj/2026-04-09-sess.md
---

# s
"""


def test_synthesized_doc_claims_raw_file_while_session_stays_a_transcript(tmp_path: Path):
    """A doc page states ``source_file: raw/docs/<rel>`` and carries doc tags, while a session in the same run keeps its transcript stamp (#307)."""
    raw_sessions = tmp_path / "raw" / "sessions" / "proj"
    raw_sessions.mkdir(parents=True)
    (raw_sessions / "2026-04-09-sess.md").write_text(SESSION, encoding="utf-8")
    # Nested exactly like `llmwiki add` writes it, so the claim must carry
    # the sub-path rather than just the filename.
    docs = _seed_docs(
        tmp_path,
        name="openclaw-openclaw/openclaw-openclaw.md",
        content=DEMO_DOC.replace(
            "slug: openclaw-openclaw",
            "slug: openclaw-openclaw\ntags: [wiki-add, raw-doc]",
        ),
    )
    wiki_sources, log_file = _wiki(tmp_path)

    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=tmp_path / "raw" / "sessions",
        docs_dir=docs,
        wiki_sources_dir=wiki_sources,
        log_path=log_file,
        state_file=tmp_path / "state.json",
    )
    assert summary["synthesized"] == 2, summary["errors"]

    doc_meta, _body = parse_frontmatter(
        (wiki_sources / "docs" / "openclaw-openclaw.md").read_text(encoding="utf-8")
    )
    assert doc_meta["source_file"] == "raw/docs/openclaw-openclaw/openclaw-openclaw.md"
    assert "raw-doc" in doc_meta["tags"]
    assert "session-transcript" not in doc_meta["tags"]

    sess_meta, _body = parse_frontmatter(
        (wiki_sources / "proj" / "2026-04-09-sess.md").read_text(encoding="utf-8")
    )
    assert sess_meta["source_file"] == "raw/sessions/proj/2026-04-09-sess.md"
    assert "session-transcript" in sess_meta["tags"]


def test_doc_declaring_its_own_source_file_keeps_that_claim(tmp_path: Path):
    """A raw doc that already states a ``source_file`` is not overwritten by the derived ``raw/docs/`` key (#307)."""
    docs = _seed_docs(
        tmp_path,
        name="imported.md",
        content=(
            "---\nslug: imported\n"
            "source_file: raw/docs/legacy/imported.md\n---\n\n# Imported\n"
        ),
    )
    wiki_sources, log_file = _wiki(tmp_path)
    synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=tmp_path / "raw" / "sessions",
        docs_dir=docs,
        wiki_sources_dir=wiki_sources,
        log_path=log_file,
        state_file=tmp_path / "state.json",
    )
    meta, _body = parse_frontmatter(
        (wiki_sources / "docs" / "imported.md").read_text(encoding="utf-8")
    )
    assert meta["source_file"] == "raw/docs/legacy/imported.md"


def test_resynth_recognizes_the_doc_page_it_wrote_by_its_own_claim(tmp_path: Path):
    """A synthesized doc page is found by the ``raw/docs/`` key it claims, so a later run with no synth state skips it instead of writing a duplicate (#307)."""
    docs = _seed_docs(tmp_path)
    wiki_sources, log_file = _wiki(tmp_path)
    common = dict(
        backend=RealSynthesizer(),
        raw_dir=tmp_path / "raw" / "sessions",
        docs_dir=docs,
        wiki_sources_dir=wiki_sources,
        log_path=log_file,
    )
    first = synthesize_new_sessions(**common, state_file=tmp_path / "state-1.json")
    assert first["synthesized"] == 1
    page = wiki_sources / "docs" / "openclaw-openclaw.md"
    assert discover_synth_source_keys(wiki_sources) == {"raw/docs/openclaw-openclaw.md"}

    # Page filed under another folder/slug (a migrated vault) and the synth
    # state gone: the claim is the only thing tying it to the raw doc.
    moved = wiki_sources / "manual" / "openclaw-notes.md"
    moved.parent.mkdir(parents=True)
    moved.write_text(page.read_text(encoding="utf-8"), encoding="utf-8")
    page.unlink()

    second = synthesize_new_sessions(**common, state_file=tmp_path / "state-2.json")
    assert second["synthesized"] == 0
    assert second["skipped"] == 1
    assert not page.exists(), "a duplicate page was written for an already-claimed doc"
    assert sorted(p.name for p in wiki_sources.rglob("*.md")) == ["openclaw-notes.md"]


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
    # Coverage: every character survives; only chunk-edge whitespace may go.
    assert "".join(c.strip() for c in chunks) == text


def test_chunk_markdown_never_exceeds_budget_with_paragraphs():
    paras = "\n\n".join("para " + "w" * 95 for _ in range(40))
    chunks = _chunk_markdown("## Big\n\n" + paras, max_chars=500)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)
    assert "".join(chunks).count("para ") == 40


def test_synthesize_oversized_doc_produces_one_page(tmp_path: Path):
    """#311: a doc over the budget is chunked in memory into ONE wiki page."""
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
    assert summary["synthesized"] == 1
    assert sorted(p.name for p in (wiki_sources / "docs").glob("*.md")) == ["big-doc.md"]
    assert "type: source" in (wiki_sources / "docs" / "big-doc.md").read_text(encoding="utf-8")
