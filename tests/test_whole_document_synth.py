"""Whole-document synth: in-memory chunk → stitch → ONE wiki page (#311, Slice 3).

Spec: ``context/spec/324-whole-document-storage/``. A document longer than the
active backend's ``usable_body_chars()`` is chunked in memory, each chunk goes
to the backend, and the outputs are stitched by fixed rules into one canonical
page that is written only after EVERY chunk succeeded. Any chunk failure fails
the whole document. Sessions are never chunked.
"""

from __future__ import annotations

import threading
from pathlib import Path

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.doc_chunking import MAX_DOC_MARKDOWN_BYTES
from llmwiki.synth.base import BackendUsageLimitError, BaseSynthesizer
from llmwiki.synth.estimate import synthesize_estimate_report
from llmwiki.synth.pipeline import _load_state, synthesize_new_sessions
from llmwiki.synth.stitch import stitch_chunk_bodies

BUDGET = 900
TAGS = ["prompt-caching", "sqlite-fts", "github-actions", "rag-pipeline", "token-budget", "regex-vs-llm"]


class CappedBackend(BaseSynthesizer):
    """Capped mock backend: records every call, can fail or hit a usage limit."""

    name = "capped-mock"
    is_llm = False  # skip the per-run known-names call so call counts are exact

    def __init__(self, budget: int = BUDGET, *, fail_on: int | None = None, limit_on: int | None = None):
        self.budget = budget
        self.fail_on = fail_on
        self.limit_on = limit_on
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def usable_body_chars(self) -> int:
        return self.budget

    def is_available(self) -> bool:
        return True

    def synthesize_source_page(self, raw_body, meta, prompt_template):
        with self._lock:
            self.calls.append(raw_body)
            n = len(self.calls)
        if n == self.fail_on:
            raise RuntimeError("backend exploded")
        if n == self.limit_on:
            raise BackendUsageLimitError("usage limit: out of credits", reset="1pm")
        return (
            f"<!-- suggested-tags: {TAGS[n % len(TAGS)]}, {TAGS[(n + 1) % len(TAGS)]} -->\n\n"
            f"## Summary\n\nChunk {n} summary.\n\n"
            f"## Key Claims\n\n- claim from chunk {n}\n- shared claim\n\n"
            f"## Key Quotes\n\n> \"quote {n}\" — ctx\n\n"
            f"## Connections\n\n- [[Shared]] (entity) — shared\n  - fact: fact {n}\n"
            f"- [[Own{n}]] (concept) — own {n}\n"
        )


def _long_doc(sections: int = 8) -> str:
    return "---\nslug: big-doc\ntags: [wiki-add, raw-doc]\n---\n" + "\n".join(
        f"## Section {i}\n\nMARKER-{i} " + ("lorem ipsum " * 40) + "\n" for i in range(sections)
    )


def _vault(tmp_path: Path, doc: str | None = None) -> dict:
    docs = tmp_path / "raw" / "docs"
    docs.mkdir(parents=True)
    if doc is not None:
        (docs / "big-doc.md").write_text(doc, encoding="utf-8")
    sources = tmp_path / "wiki" / "sources"
    sources.mkdir(parents=True)
    log = tmp_path / "wiki" / "log.md"
    log.write_text("# Log\n", encoding="utf-8")
    return {
        "docs": docs,
        "sources": sources,
        "page": sources / "docs" / "big-doc.md",
        "common": dict(
            raw_dir=tmp_path / "raw" / "sessions",
            docs_dir=docs,
            wiki_sources_dir=sources,
            log_path=log,
            state_file=tmp_path / "state.json",
        ),
    }


# ─── N calls, one page, full coverage ──────────────────────────────────


def test_long_doc_on_capped_backend_makes_n_calls_and_writes_one_page(tmp_path: Path):
    v = _vault(tmp_path, _long_doc())
    backend = CappedBackend()
    summary = synthesize_new_sessions(backend=backend, **v["common"])

    assert summary["errors"] == []
    assert summary["synthesized"] == 1
    assert len(backend.calls) > 2, "fixture must need several chunks"
    assert all(len(c) <= BUDGET for c in backend.calls), "a chunk exceeded the backend budget"
    # Full coverage: every section marker reached the backend, none truncated.
    seen = "".join(backend.calls)
    for i in range(8):
        assert f"MARKER-{i} " in seen
    # One canonical page; no part pages.
    assert sorted(p.name for p in (v["sources"] / "docs").glob("*.md")) == ["big-doc.md"]
    page = v["page"].read_text(encoding="utf-8")
    meta, body = parse_frontmatter(page)
    assert meta["source_file"] == "raw/docs/big-doc.md"
    for n in range(1, len(backend.calls) + 1):
        assert f"Chunk {n} summary." in body


def test_stitched_page_follows_fixed_rules(tmp_path: Path):
    v = _vault(tmp_path, _long_doc())
    backend = CappedBackend()
    synthesize_new_sessions(backend=backend, **v["common"])
    n = len(backend.calls)
    meta, body = parse_frontmatter(v["page"].read_text(encoding="utf-8"))

    # Summary concatenated in document order.
    summaries = [body.index(f"Chunk {i} summary.") for i in range(1, n + 1)]
    assert summaries == sorted(summaries)
    # Claims: ordered union, exact duplicate dropped.
    assert body.count("- shared claim") == 1
    assert all(f"- claim from chunk {i}" in body for i in range(1, n + 1))
    # Quotes: every distinct quote kept.
    assert all(f'"quote {i}"' in body for i in range(1, n + 1))
    # Connections: union by target — one [[Shared]], every nested fact kept.
    assert body.count("[[Shared]]") == 1
    assert all(f"fact: fact {i}" in body for i in range(1, n + 1))
    assert all(f"[[Own{i}]]" in body for i in range(1, n + 1))
    # Tags: union of every chunk's suggestions (beyond a single chunk's two).
    suggested = {t for t in meta["tags"] if t in TAGS}
    assert len(suggested) > 2
    assert "suggested-tags" not in body


def test_curated_tags_are_preserved_and_suggestions_unioned(tmp_path: Path):
    v = _vault(tmp_path, _long_doc())
    v["page"].parent.mkdir(parents=True)
    v["page"].write_text(
        "---\ntitle: \"Big\"\ntype: source\ntags: [my-curated-tag]\nsource_file: raw/docs/big-doc.md\n"
        "project: docs\n---\n\n## Summary\n\nOld real page.\n\n## Connections\n\n- [[Old]]\n",
        encoding="utf-8",
    )
    synthesize_new_sessions(backend=CappedBackend(), force=True, **v["common"])
    meta, _body = parse_frontmatter(v["page"].read_text(encoding="utf-8"))
    assert meta["tags"][0] == "my-curated-tag"
    assert any(t in TAGS for t in meta["tags"])


def test_doc_within_budget_is_a_single_call_with_the_unstitched_body(tmp_path: Path):
    v = _vault(tmp_path, "---\nslug: big-doc\n---\n# Small\n\nShort.\n")
    backend = CappedBackend()
    synthesize_new_sessions(backend=backend, **v["common"])
    assert len(backend.calls) == 1
    _meta, body = parse_frontmatter(v["page"].read_text(encoding="utf-8"))
    assert "Chunk 1 summary." in body


def test_doc_chunk_override_can_tighten_but_never_exceed_the_backend_budget(tmp_path: Path):
    v = _vault(tmp_path, _long_doc())
    backend = CappedBackend(budget=900)
    synthesize_new_sessions(backend=backend, doc_chunk_max_chars=10**9, **v["common"])
    assert all(len(c) <= 900 for c in backend.calls)


# ─── mid-chunk failure fails the whole document ────────────────────────


def test_failure_on_chunk_two_leaves_no_page_and_the_doc_pending(tmp_path: Path):
    v = _vault(tmp_path, _long_doc())
    backend = CappedBackend(fail_on=2)
    summary = synthesize_new_sessions(backend=backend, **v["common"])

    assert summary["synthesized"] == 0
    assert len(summary["errors"]) == 1
    assert "chunk 2/" in summary["errors"][0], "diagnostics should name the failing chunk"
    assert not v["page"].exists(), "a prefix-only page must never look like the whole doc"
    assert list((v["sources"] / "docs").glob("*")) == []
    assert "docs::big-doc.md" not in _load_state(v["common"]["state_file"])

    # Still pending as ONE document; a retry on a healthy backend completes it.
    dry = synthesize_new_sessions(backend=CappedBackend(), dry_run=True, **v["common"])
    assert dry["new_files"] == 1
    retry_backend = CappedBackend()
    retry = synthesize_new_sessions(backend=retry_backend, **v["common"])
    assert retry["synthesized"] == 1 and retry["errors"] == []
    assert all(f"Chunk {i} summary." in v["page"].read_text(encoding="utf-8")
               for i in range(1, len(retry_backend.calls) + 1))


def test_failure_never_overwrites_a_curated_page(tmp_path: Path):
    v = _vault(tmp_path, _long_doc())
    v["page"].parent.mkdir(parents=True)
    curated = (
        "---\ntitle: \"Big\"\ntype: source\ntags: [curated]\nsource_file: raw/docs/big-doc.md\n"
        "project: docs\n---\n\n## Summary\n\nHand-curated real summary.\n\n## Connections\n\n- [[Old]]\n"
    )
    v["page"].write_text(curated, encoding="utf-8")

    summary = synthesize_new_sessions(backend=CappedBackend(fail_on=3), force=True, **v["common"])

    assert summary["synthesized"] == 0 and len(summary["errors"]) == 1
    assert v["page"].read_text(encoding="utf-8") == curated


def test_failure_never_replaces_a_stub_with_a_partial_stitch(tmp_path: Path):
    v = _vault(tmp_path, _long_doc())
    v["page"].parent.mkdir(parents=True)
    stub = (
        "---\ntitle: \"Big\"\ntype: source\ntags: [raw-doc]\nsource_file: raw/docs/big-doc.md\n"
        "project: docs\n---\n\n<!-- llmwiki-pending: 8f2c -->\n\n*Pending agent synthesis.*\n"
    )
    v["page"].write_text(stub, encoding="utf-8")
    synthesize_new_sessions(backend=CappedBackend(fail_on=2), force=True, **v["common"])
    assert v["page"].read_text(encoding="utf-8") == stub


def test_usage_limit_on_a_later_chunk_defers_the_whole_document(tmp_path: Path):
    v = _vault(tmp_path, _long_doc())
    summary = synthesize_new_sessions(backend=CappedBackend(limit_on=2), **v["common"])

    assert summary["usage_limit"] == {"reset": "1pm"}
    assert summary["synthesized"] == 0
    assert summary["deferred"] == 1
    assert not v["page"].exists()
    assert "docs::big-doc.md" not in _load_state(v["common"]["state_file"])


def test_a_stub_stitch_does_not_replace_a_real_page(tmp_path: Path):
    v = _vault(tmp_path, _long_doc())
    v["page"].parent.mkdir(parents=True)
    real = (
        "---\ntitle: \"Big\"\ntype: source\ntags: [raw-doc]\nsource_file: raw/docs/big-doc.md\n"
        "project: docs\n---\n\n## Summary\n\nReal.\n\n## Connections\n\n- [[Old]]\n"
    )
    v["page"].write_text(real, encoding="utf-8")

    class StubBackend(CappedBackend):
        def synthesize_source_page(self, raw_body, meta, prompt_template):
            super().synthesize_source_page(raw_body, meta, prompt_template)
            return "<!-- llmwiki-pending: 8f2c -->\n\n*Pending agent synthesis.*\n"

    summary = synthesize_new_sessions(backend=StubBackend(), force=True, **v["common"])
    assert summary["protected"] == 1
    assert v["page"].read_text(encoding="utf-8") == real


# ─── legacy part pages are left for migrate ────────────────────────────


def test_synth_leaves_legacy_part_pages_in_place(tmp_path: Path):
    v = _vault(tmp_path, _long_doc())
    out = v["sources"] / "docs"
    out.mkdir(parents=True)
    legacy = []
    for n in (1, 2):
        path = out / f"big-doc--part-{n:02d}.md"
        path.write_text(
            "---\ntitle: \"Big\"\ntype: source\ntags: [raw-doc]\nsource_file: raw/docs/big-doc.md\n"
            f"project: docs\n---\n\n## Summary\n\nLegacy part {n}.\n\n## Connections\n\n- [[Old]]\n",
            encoding="utf-8",
        )
        legacy.append((path, path.read_text(encoding="utf-8")))

    synthesize_new_sessions(backend=CappedBackend(), force=True, **v["common"])

    assert v["page"].is_file()
    for path, text in legacy:
        assert path.read_text(encoding="utf-8") == text


# ─── sessions are never chunked ────────────────────────────────────────


def test_sessions_stay_a_single_unchunked_call(tmp_path: Path):
    sessions = tmp_path / "raw" / "sessions" / "proj"
    sessions.mkdir(parents=True)
    body = "# s\n\n" + "\n\n".join(f"turn {i} " + "x" * 200 for i in range(30))  # >> BUDGET
    (sessions / "2026-04-09-sess.md").write_text(
        f"---\nslug: sess\nproject: proj\ndate: 2026-04-09\n---\n{body}\n", encoding="utf-8"
    )
    v = _vault(tmp_path)
    backend = CappedBackend()
    summary = synthesize_new_sessions(backend=backend, **v["common"])

    assert summary["synthesized"] == 1
    assert len(backend.calls) == 1
    assert len(backend.calls[0]) > BUDGET, "the session body must reach the backend whole"
    assert (v["sources"] / "proj" / "2026-04-09-sess.md").is_file()


# ─── estimate prices one document job = the run's N calls ──────────────


def test_estimate_counts_one_doc_job_and_the_same_calls_the_run_makes(tmp_path: Path):
    v = _vault(tmp_path, _long_doc())
    backend = CappedBackend()
    report = synthesize_estimate_report(
        raw_sessions=[],
        docs_root=v["docs"],
        wiki_sources_dir=v["sources"],
        state_keys=set(),
        prefix_tokens=2000,
        backend=backend,
    )
    assert report["new_docs"] == 1
    assert [it["rel"] for it in report["unsynth_items"]] == ["docs::big-doc.md"]
    synthesize_new_sessions(backend=backend, **v["common"])
    assert report["new_doc_calls"] == len(backend.calls) > 1
    assert report["unsynth_items"][0]["chunks"] == len(backend.calls)


def test_failed_doc_stays_one_pending_item_in_the_estimate(tmp_path: Path):
    v = _vault(tmp_path, _long_doc())
    backend = CappedBackend(fail_on=2)
    synthesize_new_sessions(backend=backend, **v["common"])
    report = synthesize_estimate_report(
        raw_sessions=[],
        docs_root=v["docs"],
        wiki_sources_dir=v["sources"],
        state_keys=_load_state(v["common"]["state_file"]),
        prefix_tokens=2000,
        backend=backend,
    )
    assert report["new_docs"] == 1 and report["synthesized_docs"] == 0


# ─── stitch rules (pure) ───────────────────────────────────────────────


def test_stitch_single_body_is_returned_unchanged():
    body = "## Summary\n\nOnly.\n"
    assert stitch_chunk_bodies([body]) == body


def test_stitch_claims_and_quotes_drop_only_exact_duplicates():
    a = "## Key Claims\n\n- same\n- Different case\n\n## Key Quotes\n\n> \"q\" — c\n"
    b = "## Key Claims\n\n- same\n- different case\n\n## Key Quotes\n\n> \"q\" — c\n\n> \"r\" — d\n"
    out = stitch_chunk_bodies([a, b])
    assert out.count("- same") == 1
    assert "- Different case" in out and "- different case" in out
    assert out.count('> "q" — c') == 1 and '> "r" — d' in out


def test_stitch_connections_union_by_target_keeps_first_bullet_and_merges_facts():
    a = "## Connections\n\n- [[Foo]] (entity) — first\n  - fact: a\n"
    b = "## Connections\n\n- [[Foo#sec]] (entity) — second\n  - fact: a\n  - fact: b\n- [[Bar]] (concept) — bar\n"
    out = stitch_chunk_bodies([a, b])
    assert out.count("[[Foo") == 1
    assert "first" in out and "second" not in out
    assert out.count("fact: a") == 1 and "fact: b" in out
    assert "[[Bar]]" in out


def test_stitch_section_order_follows_first_appearance_and_unknown_sections_union():
    a = "## Summary\n\nA.\n\n## Contradictions\n\n- X vs Y\n"
    b = "## Summary\n\nB.\n\n## Key Claims\n\n- c\n\n## Contradictions\n\n- X vs Y\n- Z vs W\n"
    out = stitch_chunk_bodies([a, b])
    assert out.index("## Summary") < out.index("## Contradictions") < out.index("## Key Claims")
    assert "A.\n\nB." in out
    assert out.count("- X vs Y") == 1 and "- Z vs W" in out


def test_stitch_ignores_headings_inside_code_fences():
    a = "## Summary\n\n```\n## not a heading\n```\n"
    out = stitch_chunk_bodies([a, "## Summary\n\nB.\n"])
    assert out.count("## Summary") == 1 and "## not a heading" in out


# ─── hard per-document cap (legacy raw docs over 512 KiB) ──────────────


def test_legacy_raw_doc_over_512_kib_is_refused_without_a_backend_call(tmp_path: Path):
    huge = "---\nslug: big-doc\n---\n# Huge\n\n" + "x" * MAX_DOC_MARKDOWN_BYTES
    v = _vault(tmp_path, huge)
    backend = CappedBackend(budget=10**9)

    summary = synthesize_new_sessions(backend=backend, **v["common"])

    assert backend.calls == []
    assert summary["synthesized"] == 0
    assert len(summary["errors"]) == 1 and "512 KiB" in summary["errors"][0]
    assert not v["page"].exists()
    assert "docs::big-doc.md" not in _load_state(v["common"]["state_file"])
