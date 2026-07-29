"""Stub/sentinel pages in wiki/sources count as UNSYNTHESIZED (#24).

A page carrying the agent-delegate pending sentinel
(``<!-- llmwiki-pending: … -->``) or the dummy backend's canned body
(``Auto-synthesized from session``) is machine-generated filler. Backlog
discovery (``discover_synth_source_keys`` → estimate → ``refresh_synth_pending``
→ ``queue status``) must treat it as work still to do, and
``synthesize_new_sessions`` must re-synthesize it even when the state file
claims the source is done.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.lint import load_pages, run_all
from llmwiki.lint.rules import StubSourcePages
from llmwiki.synth.base import BaseSynthesizer
from llmwiki.synth.estimate import synthesize_estimate_report
from llmwiki.synth.pipeline import (
    _DOC_CHUNK_MAX_CHARS,
    _discover_raw_sessions,
    _save_state,
    discover_stub_source_keys,
    discover_synth_source_keys,
    page_is_stub,
    refresh_synth_pending,
    synth_page_filename,
    synthesize_new_sessions,
)

RAW_SESSION = """---
title: "Session: alpha — 2026-04-09"
type: source
tags: [claude-code]
date: 2026-04-09
slug: alpha
project: proj
model: claude-sonnet-4-6
---

# Session: alpha

Some transcript body.
"""

REAL_PAGE = """---
title: "Session: alpha — 2026-04-09"
type: source
tags: [claude-code]
date: 2026-04-09
source_file: raw/sessions/proj/2026-04-09-alpha.md
project: proj
---

## Summary

A real synthesis.

## Connections

- [[ProjectAlpha]]
"""

SENTINEL_PAGE = """---
title: "Session: alpha — 2026-04-09"
type: source
tags: [claude-code]
date: 2026-04-09
source_file: raw/sessions/proj/2026-04-09-alpha.md
project: proj
---

<!-- llmwiki-pending: 8f2c -->

*Pending agent synthesis.*
"""

DUMMY_PAGE = """---
title: "Session: alpha — 2026-04-09"
type: source
tags: [claude-code]
date: 2026-04-09
source_file: raw/sessions/proj/2026-04-09-alpha.md
project: proj
---

## Summary

Auto-synthesized from session `alpha` on 2026-04-09.
"""


class RealSynthesizer(BaseSynthesizer):
    """Backend whose output is a real (non-stub) page body."""

    name = "real"

    def is_available(self) -> bool:
        return True

    def synthesize_source_page(self, body, meta, prompt_template):
        return "## Summary\n\nA real synthesis.\n\n## Connections\n\n- [[ProjectAlpha]]\n"


@pytest.fixture
def vault(tmp_path: Path) -> dict[str, Path]:
    raw = tmp_path / "raw" / "sessions" / "proj"
    raw.mkdir(parents=True)
    (raw / "2026-04-09-alpha.md").write_text(RAW_SESSION, encoding="utf-8")
    sources = tmp_path / "wiki" / "sources"
    (sources / "proj").mkdir(parents=True)
    (tmp_path / "wiki" / "log.md").write_text("# Log\n", encoding="utf-8")
    return {
        "root": tmp_path,
        "raw_dir": tmp_path / "raw" / "sessions",
        "docs_dir": tmp_path / "raw" / "docs",
        "sources": sources,
        "log": tmp_path / "wiki" / "log.md",
        "state": tmp_path / "llmwiki-state.json",
        "page": sources / "proj" / "2026-04-09-alpha.md",
    }


# ─── discover_synth_source_keys ────────────────────────────────────────


def test_discover_skips_sentinel_page(vault):
    vault["page"].write_text(SENTINEL_PAGE, encoding="utf-8")
    assert discover_synth_source_keys(vault["sources"]) == set()


def test_discover_skips_dummy_stub_page(vault):
    vault["page"].write_text(DUMMY_PAGE, encoding="utf-8")
    assert discover_synth_source_keys(vault["sources"]) == set()


def test_discover_counts_real_page(vault):
    vault["page"].write_text(REAL_PAGE, encoding="utf-8")
    assert discover_synth_source_keys(vault["sources"]) == {
        "raw/sessions/proj/2026-04-09-alpha.md"
    }


# ─── page helpers ──────────────────────────────────────────────────────


def test_synth_page_filename_matches_pipeline_output(vault):
    meta = {"slug": "alpha", "date": "2026-04-09"}
    assert synth_page_filename(meta, "fallback") == "2026-04-09-alpha"
    assert synth_page_filename({}, "fallback") == "fallback"


def test_page_is_stub(vault):
    vault["page"].write_text(SENTINEL_PAGE, encoding="utf-8")
    assert page_is_stub(vault["page"])
    vault["page"].write_text(REAL_PAGE, encoding="utf-8")
    assert not page_is_stub(vault["page"])
    assert not page_is_stub(vault["sources"] / "nope.md")


def test_page_is_stub_on_unreadable_page(vault):
    # An undecodable page cannot be shown to be filler, so it is not one.
    # It must not take down the synthesize run that walks past it.
    vault["page"].write_bytes(b"---\ntitle: x\n---\n\n## Summary\n\n\xff\xfe\n")
    assert page_is_stub(vault["page"]) is False
    assert page_is_stub(vault["sources"]) is False  # a directory


def test_discover_source_keys_survives_unreadable_page(vault):
    vault["page"].write_text(SENTINEL_PAGE, encoding="utf-8")
    (vault["sources"] / "proj" / "binary.md").write_bytes(
        b"---\nsource_file: raw/sessions/proj/other.md\n---\n\xff\xfe\n"
    )
    assert discover_synth_source_keys(vault["sources"]) == set()
    assert discover_stub_source_keys(vault["sources"]) == {
        "raw/sessions/proj/2026-04-09-alpha.md"
    }


# ─── estimate + refresh_synth_pending ──────────────────────────────────


def _report(vault, state_keys: set[str]) -> dict:

    return synthesize_estimate_report(
        raw_sessions=_discover_raw_sessions(vault["raw_dir"]),
        state_keys=state_keys,
        synthesized_source_keys=discover_synth_source_keys(vault["sources"]),
        wiki_sources_dir=vault["sources"],
        raw_root=vault["raw_dir"],
        docs_root=vault["docs_dir"],
    )


def test_estimate_counts_stub_page_as_new_even_when_state_says_done(vault):
    vault["page"].write_text(SENTINEL_PAGE, encoding="utf-8")
    rpt = _report(vault, {"proj/2026-04-09-alpha.md"})
    assert rpt["new"] == 1
    assert rpt["synthesized"] == 0
    assert [it["rel"] for it in rpt["unsynth_items"]] == ["proj/2026-04-09-alpha.md"]


def test_estimate_counts_stub_page_filed_under_another_name(vault):
    # A vault migrated from an older release holds pages named under that
    # release's slug scheme, so the page cannot be found by deriving its
    # filename from the raw session. The page declares which source it stands
    # for — that claim is what makes it a stub for THIS source.
    legacy = vault["sources"] / "proj" / "legacy-name.md"
    legacy.write_text(SENTINEL_PAGE, encoding="utf-8")
    rpt = _report(vault, {"proj/2026-04-09-alpha.md"})
    assert rpt["new"] == 1
    assert [it["rel"] for it in rpt["unsynth_items"]] == ["proj/2026-04-09-alpha.md"]


def test_real_page_wins_over_a_leftover_stub_for_the_same_source(vault):
    # Re-synthesis can file the real page under a different name than the stub
    # it replaces, leaving both on disk claiming the same source. The source is
    # synthesized — the stale stub must not hold it in the backlog forever.
    (vault["sources"] / "proj" / "legacy-name.md").write_text(SENTINEL_PAGE, encoding="utf-8")
    vault["page"].write_text(REAL_PAGE, encoding="utf-8")
    rpt = _report(vault, {"proj/2026-04-09-alpha.md"})
    assert rpt["new"] == 0
    assert rpt["synthesized"] == 1


def test_stub_page_filed_under_another_name_is_resynthesized(vault):

    legacy = vault["sources"] / "proj" / "legacy-name.md"
    legacy.write_text(SENTINEL_PAGE, encoding="utf-8")
    mtime = (vault["raw_dir"] / "proj" / "2026-04-09-alpha.md").stat().st_mtime
    _save_state({"proj/2026-04-09-alpha.md": mtime}, vault["state"])

    summary = synthesize_new_sessions(
        backend=RealSynthesizer(),
        raw_dir=vault["raw_dir"],
        wiki_sources_dir=vault["sources"],
        log_path=vault["log"],
        state_file=vault["state"],
    )
    assert summary["synthesized"] == 1


def test_estimate_counts_real_page_as_synthesized(vault):
    vault["page"].write_text(REAL_PAGE, encoding="utf-8")
    rpt = _report(vault, set())
    assert rpt["new"] == 0
    assert rpt["synthesized"] == 1


def test_refresh_synth_pending_lists_stub_backed_source(vault):
    vault["page"].write_text(DUMMY_PAGE, encoding="utf-8")
    out = refresh_synth_pending(
        raw_dir=vault["raw_dir"],
        docs_dir=vault["docs_dir"],
        wiki_sources_dir=vault["sources"],
        state_file=vault["state"],
    )
    assert out["pending_total"] == 1
    assert out["pending"][0]["rel"] == "proj/2026-04-09-alpha.md"


def test_refresh_synth_pending_empty_for_real_page(vault):
    vault["page"].write_text(REAL_PAGE, encoding="utf-8")
    out = refresh_synth_pending(
        raw_dir=vault["raw_dir"],
        docs_dir=vault["docs_dir"],
        wiki_sources_dir=vault["sources"],
        state_file=vault["state"],
    )
    assert out["pending_total"] == 0


# ─── re-synthesis of a stub page whose state says "done" ───────────────


def test_stub_page_is_resynthesized_even_when_state_says_done(vault):
    # First pass: a stub landed on disk and state recorded the source as done.
    vault["page"].write_text(SENTINEL_PAGE, encoding="utf-8")

    mtime = (vault["raw_dir"] / "proj" / "2026-04-09-alpha.md").stat().st_mtime
    _save_state({"proj/2026-04-09-alpha.md": mtime}, vault["state"])

    summary = synthesize_new_sessions(
        backend=RealSynthesizer(),
        raw_dir=vault["raw_dir"],
        wiki_sources_dir=vault["sources"],
        log_path=vault["log"],
        state_file=vault["state"],
    )
    assert summary["synthesized"] == 1
    text = vault["page"].read_text(encoding="utf-8")
    assert "llmwiki-pending" not in text
    assert "[[ProjectAlpha]]" in text

    # Now the page is real — a re-run is a no-op.
    again = synthesize_new_sessions(
        backend=RealSynthesizer(),
        raw_dir=vault["raw_dir"],
        wiki_sources_dir=vault["sources"],
        log_path=vault["log"],
        state_file=vault["state"],
    )
    assert again["synthesized"] == 0
    assert again["new_files"] == 0


# ─── chunked docs: a stub PART is backlog too ──────────────────────────


class _StubSynthesizer(BaseSynthesizer):
    """Backend whose output is a pending sentinel — the agent-delegate shape."""

    name = "stub"

    def is_available(self) -> bool:
        return True

    def synthesize_source_page(self, body, meta, prompt_template):
        return "<!-- llmwiki-pending: 8f2c -->\n\n*Pending agent synthesis.*\n"


@pytest.fixture
def chunked_doc_vault(vault) -> dict[str, Path]:
    """A doc big enough to be split into part-pages at the default chunk size."""

    docs = vault["docs_dir"]
    docs.mkdir(parents=True, exist_ok=True)
    section = "lorem ipsum " * (_DOC_CHUNK_MAX_CHARS // 12)  # ~1 chunk each
    body = "---\nslug: big-doc\n---\n" + "\n".join(
        f"## Part {i}\n\n{section}\n" for i in range(2)
    )
    (docs / "big-doc.md").write_text(body, encoding="utf-8")
    vault["doc_out"] = vault["sources"] / "docs"
    return vault


def _doc_parts(vault) -> list[Path]:
    return sorted(vault["doc_out"].glob("big-doc--part-*.md"))


def test_chunked_doc_written_as_stub_parts_is_resynthesized(chunked_doc_vault):
    v = chunked_doc_vault
    common = dict(
        raw_dir=v["raw_dir"],
        docs_dir=v["docs_dir"],
        wiki_sources_dir=v["sources"],
        log_path=v["log"],
        state_file=v["state"],
    )
    # A legacy agent-delegate run left every part a sentinel and marked the
    # source done in state.
    synthesize_new_sessions(backend=_StubSynthesizer(), **common)
    parts = _doc_parts(v)
    assert len(parts) > 1, f"expected part pages, got {parts}"
    assert all(page_is_stub(p) for p in parts)

    summary = synthesize_new_sessions(backend=RealSynthesizer(), **common)
    assert summary["synthesized"] == 2  # the session + the doc
    assert not any(page_is_stub(p) for p in _doc_parts(v))


def test_chunked_doc_with_one_real_part_still_has_stub_parts_pending(chunked_doc_vault):
    # A partially hand-filled doc: part 1 was written out for real, the rest
    # are still sentinels. The parts are complementary — one real part does NOT
    # make the source synthesized, so the stub parts stay in the backlog and a
    # real-backend run must fill them.
    v = chunked_doc_vault
    common = dict(
        raw_dir=v["raw_dir"],
        docs_dir=v["docs_dir"],
        wiki_sources_dir=v["sources"],
        log_path=v["log"],
        state_file=v["state"],
    )
    synthesize_new_sessions(backend=_StubSynthesizer(), **common)
    parts = _doc_parts(v)
    parts[0].write_text(
        "---\ntitle: \"Big Doc\"\ntype: source\n"
        "source_file: raw/docs/big-doc.md\nproject: docs\n---\n\n"
        "## Summary\n\nHand-filled real content.\n\n## Connections\n\n- [[Thing]]\n",
        encoding="utf-8",
    )
    assert any(page_is_stub(p) for p in _doc_parts(v))

    summary = synthesize_new_sessions(backend=RealSynthesizer(), **common)
    assert summary["synthesized"] == 2  # the session + the doc
    leftover = [p.name for p in _doc_parts(v) if page_is_stub(p)]
    assert leftover == [], f"stub parts never drained: {leftover}"


def test_chunked_doc_with_real_parts_is_a_noop_on_rerun(chunked_doc_vault):
    v = chunked_doc_vault
    common = dict(
        raw_dir=v["raw_dir"],
        docs_dir=v["docs_dir"],
        wiki_sources_dir=v["sources"],
        log_path=v["log"],
        state_file=v["state"],
    )
    first = synthesize_new_sessions(backend=RealSynthesizer(), **common)
    assert first["synthesized"] == 2
    again = synthesize_new_sessions(backend=RealSynthesizer(), **common)
    assert again["synthesized"] == 0
    assert again["new_files"] == 0


# ─── lint rule ─────────────────────────────────────────────────────────


def test_lint_flags_stub_source_page(vault):
    vault["page"].write_text(SENTINEL_PAGE, encoding="utf-8")
    pages = load_pages(vault["root"] / "wiki")
    issues = StubSourcePages().run(pages)
    assert len(issues) == 1
    assert issues[0]["rule"] == "stub_source_pages"
    assert "2026-04-09-alpha.md" in issues[0]["page"]


def test_lint_flags_dummy_stub_source_page(vault):
    vault["page"].write_text(DUMMY_PAGE, encoding="utf-8")
    issues = StubSourcePages().run(load_pages(vault["root"] / "wiki"))
    assert len(issues) == 1


def test_lint_ignores_real_source_page(vault):
    vault["page"].write_text(REAL_PAGE, encoding="utf-8")
    assert StubSourcePages().run(load_pages(vault["root"] / "wiki")) == []


def test_lint_rule_registered_and_runs(vault):
    vault["page"].write_text(SENTINEL_PAGE, encoding="utf-8")
    issues = run_all(load_pages(vault["root"] / "wiki"), selected=["stub_source_pages"])
    assert [i["rule"] for i in issues] == ["stub_source_pages"]


def test_lint_ignores_stub_marker_outside_sources(vault):
    concepts = vault["root"] / "wiki" / "concepts"
    concepts.mkdir(parents=True)
    (concepts / "Pending.md").write_text(
        "---\ntitle: Pending\ntype: concept\n---\n\n"
        "The sentinel looks like `<!-- llmwiki-pending: x -->`.\n",
        encoding="utf-8",
    )
    vault["page"].write_text(REAL_PAGE, encoding="utf-8")
    assert StubSourcePages().run(load_pages(vault["root"] / "wiki")) == []
