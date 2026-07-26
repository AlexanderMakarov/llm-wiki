"""Home pipeline State widget — estimate rows + dashboard mount."""

from __future__ import annotations

from pathlib import Path

from llmwiki.raw_docs_site import render_dashboard_body
from llmwiki.render import js
from llmwiki.synth.estimate import synthesize_estimate_report
from llmwiki.synth.pipeline import refresh_synth_pending


def test_dashboard_inlines_state_mount_not_old_cards():
    body = render_dashboard_body([], 0)
    assert 'id="llmwiki-state-widget"' in body
    assert "data-llmwiki-state-widget" in body
    assert "Pipeline state" in body
    assert "Recent raw documents" in body
    assert "queue-home-content" not in body
    assert "Sync, synthesis, and queue status at a glance" not in body
    assert "<summary><h3" not in body  # commands now live in the JS widget


def test_state_widget_js_has_pipeline_table_and_collapsibles():
    assert "renderStateWidget" in js.JS
    assert "state-pipeline-table" in js.JS
    assert "To synthesize" in js.JS
    assert "Not synthesized sessions" in js.JS
    assert "Not synthesized docs" in js.JS
    assert "Estimate warnings" in js.JS
    assert "collapse-section" in js.JS
    assert "collapse-sections" in js.JS
    assert "collapse-section-count" in js.JS
    assert "data-llmwiki-state-widget" in js.JS
    assert "llmwiki sync --project" in js.JS
    assert "llmwiki synthesize --path raw/sessions/" in js.JS
    assert "llmwiki synthesize --path raw/docs/" in js.JS
    assert 'detailsSection("Commands", 8,' in js.JS
    assert "queued " in js.JS
    assert "in progress " in js.JS
    # Timeline must appear before the backlog lists in the render order.
    timeline_idx = js.JS.index('detailsSection("Timeline"')
    sessions_idx = js.JS.index('detailsSection("Not synthesized sessions"')
    assert timeline_idx < sessions_idx
    # Old dashboard chrome removed from the renderer.
    assert "Unsynth estimate" not in js.JS
    assert "Queue task types" not in js.JS
    assert "Cost estimate" not in js.JS
    assert "previewLimit = 3" not in js.JS
    # Cost renders as ``42 ($1.2345)`` on one line, not ``$… → synth`` on a second.
    assert " → \" + escapeHtml(nextLabel" not in js.JS


def test_estimate_pipeline_rows_by_agent(tmp_path: Path):
    from llmwiki.synth.pipeline import _discover_raw_sessions

    raw = tmp_path / "raw" / "sessions"
    docs = tmp_path / "raw" / "docs"
    wiki = tmp_path / "wiki" / "sources"
    raw.mkdir(parents=True)
    docs.mkdir(parents=True)
    wiki.mkdir(parents=True)

    (raw / "2026-07-01-claude.md").write_text(
        "---\ntitle: c\nproject: p\nagent: claude-code\n---\n\nhello claude\n",
        encoding="utf-8",
    )
    (raw / "2026-07-01-cursor.md").write_text(
        "---\ntitle: u\nproject: p\nagent: cursor\n---\n\nhello cursor\n",
        encoding="utf-8",
    )
    (docs / "note.md").write_text(
        "---\ntitle: Note\nproject: docs\n---\n\ndoc body\n",
        encoding="utf-8",
    )

    report = synthesize_estimate_report(
        raw_sessions=_discover_raw_sessions(raw),
        raw_root=raw,
        docs_root=docs,
        wiki_sources_dir=wiki,
        state_keys=set(),
        synthesized_source_keys=set(),
        prefix_tokens=2000,
        include_subagents="all",
        exclude_headless=False,
    )
    labels = [r["label"] for r in report["pipeline_rows"]]
    assert "Claude" in labels
    assert "Cursor" in labels
    assert "Documents" in labels
    assert report["pipeline_stages"] == ["raw", "synthesized"]
    by_label = {r["label"]: r for r in report["pipeline_rows"]}
    assert by_label["Claude"]["raw"] == 1
    assert by_label["Claude"]["pending"] == 1
    assert by_label["Claude"]["synthesized"] == 0
    assert by_label["Claude"]["next_usd"] > 0
    assert by_label["Documents"]["raw"] == 1
    assert by_label["Documents"]["pending"] == 1
    agents = {it["agent"] for it in report["unsynth_items"]}
    assert "Claude" in agents
    assert "Cursor" in agents
    assert "Documents" in agents


def test_refresh_synth_pending_stores_pipeline(tmp_path: Path):
    vault = tmp_path / "vault"
    raw = vault / "raw" / "sessions"
    docs = vault / "raw" / "docs"
    wiki = vault / "wiki" / "sources"
    raw.mkdir(parents=True)
    docs.mkdir(parents=True)
    wiki.mkdir(parents=True)
    (raw / "2026-07-01-openclaw.md").write_text(
        "---\ntitle: o\nproject: p\nagent: openclaw\n---\n\nhello openclaw\n",
        encoding="utf-8",
    )
    state_file = vault / "llmwiki-state.json"
    out = refresh_synth_pending(
        raw_dir=raw,
        docs_dir=docs,
        wiki_sources_dir=wiki,
        state_file=state_file,
        include_subagents="all",
        exclude_headless=False,
    )
    assert out["pending_total"] == 1
    assert out["pipeline"]["rows"]
    assert out["pipeline"]["rows"][0]["label"] == "OpenClaw"
    from llmwiki.state_store import read_state

    state = read_state(state_file)
    assert state["synth"]["pipeline"]["rows"][0]["label"] == "OpenClaw"
    assert state["synth"]["pending"][0]["agent"] == "OpenClaw"
