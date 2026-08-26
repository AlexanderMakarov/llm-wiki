"""Shared synth done-predicate (#163).

``synth --estimate`` and a real ``synth`` run must agree on whether a source
is already done. Both call ``source_synth_is_done`` — pages on disk alone are
not enough; state must have a fresh-enough mtime and the page must not be
pending.
"""

from __future__ import annotations

from pathlib import Path

from llmwiki.synth.estimate import synthesize_estimate_report
from llmwiki.synth.pipeline import (
    _discover_raw_sessions,
    source_synth_is_done,
)

# Real (non-stub) page body — never the dummy "Auto-synthesized…" filler.
_REAL_PAGE = """---
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

- [[ProjectAlpha]] (entity) — project
"""

_SENTINEL_PAGE = """---
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

_RAW_SESSION = """---
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

_REL = "proj/2026-04-09-alpha.md"


# ─── pure predicate ─────────────────────────────────────────────────────


def test_predicate_false_when_rel_absent_from_state():
    assert source_synth_is_done(_REL, {}, 1_000.0) is False


def test_predicate_false_when_state_mtime_stale():
    assert source_synth_is_done(_REL, {_REL: 100.0}, mtime=200.0) is False


def test_predicate_true_when_state_mtime_fresh():
    assert source_synth_is_done(_REL, {_REL: 200.0}, mtime=200.0) is True
    assert source_synth_is_done(_REL, {_REL: 200.0}, mtime=199.0) is True


def test_predicate_tolerates_float_mtime_roundtrip():
    """Match the run's ``1e-6`` tolerance for state-file float round-trips."""
    raw = 1_700_000_000.123456
    assert source_synth_is_done(_REL, {_REL: raw - 5e-7}, mtime=raw) is True
    assert source_synth_is_done(_REL, {_REL: raw - 2e-6}, mtime=raw) is False


def test_predicate_false_when_force():
    assert source_synth_is_done(_REL, {_REL: 999.0}, 1.0, force=True) is False


def test_predicate_false_when_page_is_pending():
    assert (
        source_synth_is_done(_REL, {_REL: 999.0}, 1.0, page_is_pending=True) is False
    )


# ─── estimate ↔ predicate agreement ─────────────────────────────────────


def _vault(tmp_path: Path) -> dict[str, Path]:
    raw = tmp_path / "raw" / "sessions" / "proj"
    raw.mkdir(parents=True)
    (raw / "2026-04-09-alpha.md").write_text(_RAW_SESSION, encoding="utf-8")
    sources = tmp_path / "wiki" / "sources"
    (sources / "proj").mkdir(parents=True)
    (tmp_path / "raw" / "docs").mkdir(parents=True)
    return {
        "raw_dir": tmp_path / "raw" / "sessions",
        "docs_dir": tmp_path / "raw" / "docs",
        "sources": sources,
        "page": sources / "proj" / "2026-04-09-alpha.md",
        "raw_file": raw / "2026-04-09-alpha.md",
    }


def _estimate(vault: dict[str, Path], state_keys):
    return synthesize_estimate_report(
        raw_sessions=_discover_raw_sessions(vault["raw_dir"]),
        state_keys=state_keys,
        wiki_sources_dir=vault["sources"],
        raw_root=vault["raw_dir"],
        docs_root=vault["docs_dir"],
        prefix_tokens=2000,
        include_subagents="all",
        exclude_headless=False,
    )


def test_estimate_real_page_without_state_is_not_synthesized(tmp_path: Path):
    """Direction 1 (#163): page on disk + empty state → not done."""
    vault = _vault(tmp_path)
    vault["page"].write_text(_REAL_PAGE, encoding="utf-8")
    raw_mtime = vault["raw_file"].stat().st_mtime

    assert source_synth_is_done(_REL, {}, raw_mtime) is False
    rpt = _estimate(vault, {})
    assert rpt["synthesized"] == 0
    assert rpt["new"] == 1
    assert _REL in {it["rel"] for it in rpt["unsynth_items"]}


def test_estimate_real_page_with_stale_state_is_not_synthesized(tmp_path: Path):
    vault = _vault(tmp_path)
    vault["page"].write_text(_REAL_PAGE, encoding="utf-8")
    raw_mtime = vault["raw_file"].stat().st_mtime
    stale = {_REL: raw_mtime - 10.0}

    assert source_synth_is_done(_REL, stale, raw_mtime) is False
    rpt = _estimate(vault, stale)
    assert rpt["synthesized"] == 0
    assert rpt["new"] == 1


def test_estimate_real_page_with_fresh_state_is_synthesized(tmp_path: Path):
    """Direction 2 (#163): page on disk + fresh state + not pending → done."""
    vault = _vault(tmp_path)
    vault["page"].write_text(_REAL_PAGE, encoding="utf-8")
    raw_mtime = vault["raw_file"].stat().st_mtime
    fresh = {_REL: raw_mtime}

    assert source_synth_is_done(_REL, fresh, raw_mtime) is True
    rpt = _estimate(vault, fresh)
    assert rpt["synthesized"] == 1
    assert rpt["new"] == 0
    assert rpt["incremental_usd"] == 0.0


def test_estimate_pending_page_with_fresh_state_is_not_synthesized(tmp_path: Path):
    """Pending sentinel wins over a fresh state entry (#163 optional)."""
    vault = _vault(tmp_path)
    vault["page"].write_text(_SENTINEL_PAGE, encoding="utf-8")
    raw_mtime = vault["raw_file"].stat().st_mtime
    fresh = {_REL: raw_mtime}

    assert (
        source_synth_is_done(_REL, fresh, raw_mtime, page_is_pending=True) is False
    )
    rpt = _estimate(vault, fresh)
    assert rpt["synthesized"] == 0
    assert rpt["new"] == 1
