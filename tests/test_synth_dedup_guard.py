"""A real wiki/sources page already claiming a raw file suppresses re-synth.

A source page can be hand-written under an arbitrary folder/slug — it is
tied to its raw file only by the ``source_file`` frontmatter key, not by
the slug scheme the synth writer would derive. Synthesis only tracks its
own ``synth.files`` state, so such a page is invisible to it: without a
guard, ``synthesize_new_sessions`` writes a second, sibling page for the
same raw file (#37). These tests cover the dedup guard:

* a REAL (non-stub) page claiming the source suppresses a second page;
* a STUB claiming the source does NOT suppress — its slot is backlog;
* ``--force`` still re-synthesizes past a real page.
"""
from __future__ import annotations

from pathlib import Path

from llmwiki.synth.base import DummySynthesizer
from llmwiki.synth.pipeline import synthesize_new_sessions


DOC = """---
title: "OpenClaw Overview"
slug: openclaw-openclaw
---

# OpenClaw

OpenClaw is an agent runtime. It mentions [[pytest]] and [[FastAPI]].
"""

# A hand-written page for the doc above, filed under an arbitrary folder
# and slug, tied to the raw file only by its ``source_file`` key.
MANUAL_REAL_PAGE = """---
title: "My Hand-Written OpenClaw Notes"
type: source
tags: [manual]
source_file: raw/docs/openclaw-openclaw.md
project: manual
---

## Summary

A human-quality synthesis with real link data.

## Connections

- [[OpenClaw]] — the runtime
"""

MANUAL_STUB_PAGE = """---
title: "Pending OpenClaw"
type: source
source_file: raw/docs/openclaw-openclaw.md
project: manual
---

<!-- llmwiki-pending: 123 -->

*Pending agent synthesis*
"""


def _seed_doc(tmp_path: Path) -> Path:
    docs = tmp_path / "raw" / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "openclaw-openclaw.md").write_text(DOC, encoding="utf-8")
    return docs


def _wiki(tmp_path: Path) -> tuple[Path, Path]:
    sources = tmp_path / "wiki" / "sources"
    sources.mkdir(parents=True)
    log = tmp_path / "wiki" / "log.md"
    log.write_text("# Log\n", encoding="utf-8")
    return sources, log


def _write_manual(sources: Path, body: str) -> Path:
    page = sources / "manual" / "hand-written-notes.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(body, encoding="utf-8")
    return page


def _run(tmp_path: Path, docs: Path, sources: Path, log: Path,
         force: bool = False) -> dict:
    return synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=tmp_path / "raw" / "sessions",  # empty / missing
        docs_dir=docs,
        wiki_sources_dir=sources,
        log_path=log,
        state_file=tmp_path / "state.json",
        force=force,
    )


def test_real_page_suppresses_duplicate(tmp_path: Path):
    docs = _seed_doc(tmp_path)
    sources, log = _wiki(tmp_path)
    manual = _write_manual(sources, MANUAL_REAL_PAGE)

    summary = _run(tmp_path, docs, sources, log)

    assert summary["synthesized"] == 0
    assert summary["skipped"] >= 1
    # No sibling page written at the derived slug location.
    assert not (sources / "docs" / "openclaw-openclaw.md").exists()
    # The hand-written page is left untouched.
    assert manual.read_text(encoding="utf-8") == MANUAL_REAL_PAGE


def test_stub_page_does_not_suppress(tmp_path: Path):
    docs = _seed_doc(tmp_path)
    sources, log = _wiki(tmp_path)
    _write_manual(sources, MANUAL_STUB_PAGE)

    summary = _run(tmp_path, docs, sources, log)

    # A stub is backlog, not coverage — synthesis proceeds.
    assert summary["synthesized"] == 1
    assert (sources / "docs" / "openclaw-openclaw.md").exists()


def test_force_resynthesizes_past_real_page(tmp_path: Path):
    docs = _seed_doc(tmp_path)
    sources, log = _wiki(tmp_path)
    _write_manual(sources, MANUAL_REAL_PAGE)

    summary = _run(tmp_path, docs, sources, log, force=True)

    assert summary["synthesized"] == 1
    assert (sources / "docs" / "openclaw-openclaw.md").exists()
