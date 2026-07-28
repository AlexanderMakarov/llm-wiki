"""Stub output must never replace a real synthesized page.

The dummy backend's canned body and the agent-delegate pending sentinel
carry no link data. If either overwrites a page written by a real
backend, the knowledge graph silently loses its edges — this happened
to a 1,000-page corpus in one ``--force`` run with an unconfigured
backend. ``synthesize_new_sessions`` therefore refuses the downgrade,
even under ``--force``, and reports it via ``summary["protected"]``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.synth.base import DummySynthesizer
from llmwiki.synth.pipeline import _is_stub_page, synthesize_new_sessions

REAL_PAGE = """---
title: "Session: real — 2026-04-01"
type: source
tags: [claude-code]
date: 2026-04-01
project: proj
---
## Summary

A human-quality synthesis with real link data.

## Connections

- [[ProjectAlpha]] — main project
- [[Redis]] — cache layer discussed
"""


@pytest.fixture
def corpus(tmp_path: Path) -> dict[str, Path]:
    raw = tmp_path / "raw" / "sessions" / "proj"
    raw.mkdir(parents=True)
    (raw / "2026-04-01-real.md").write_text(
        "---\nslug: real\nproject: proj\ndate: 2026-04-01\n---\n# body\n",
        encoding="utf-8",
    )
    sources = tmp_path / "wiki" / "sources"
    (sources / "proj").mkdir(parents=True)
    log = tmp_path / "wiki" / "log.md"
    log.write_text("# Log\n", encoding="utf-8")
    return {
        "raw_dir": tmp_path / "raw" / "sessions",
        "sources": sources,
        "log": log,
        "state": tmp_path / "state.json",
        "page": sources / "proj" / "2026-04-01-real.md",
    }


def _run(corpus: dict[str, Path], force: bool = False) -> dict:
    return synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=corpus["raw_dir"],
        wiki_sources_dir=corpus["sources"],
        log_path=corpus["log"],
        state_file=corpus["state"],
        force=force,
    )


def test_dummy_never_overwrites_real_page_even_forced(corpus):
    corpus["page"].write_text(REAL_PAGE, encoding="utf-8")
    summary = _run(corpus, force=True)
    assert summary["protected"] == 1
    assert summary["synthesized"] == 1  # source still marked processed
    text = corpus["page"].read_text(encoding="utf-8")
    assert "[[Redis]]" in text
    assert "Auto-synthesized" not in text


def test_dummy_may_overwrite_stub_page(corpus):
    corpus["page"].write_text(
        "<!-- llmwiki-pending: 123 -->\n\n*Pending agent synthesis*\n",
        encoding="utf-8",
    )
    summary = _run(corpus, force=True)
    assert summary["protected"] == 0
    assert "Auto-synthesized" in corpus["page"].read_text(encoding="utf-8")


def test_dummy_writes_new_page(corpus):
    summary = _run(corpus)
    assert summary["protected"] == 0
    assert corpus["page"].exists()


def test_is_stub_page_markers():
    assert _is_stub_page("x <!-- llmwiki-pending: abc --> y")
    assert _is_stub_page("Auto-synthesized from session `x` on ...")
    assert not _is_stub_page(REAL_PAGE)
