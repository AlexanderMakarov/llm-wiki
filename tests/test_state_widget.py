"""Home pipeline State widget — estimate rows + dashboard mount."""

from __future__ import annotations

import json
from pathlib import Path

from llmwiki import build as build_mod
from llmwiki.build import build_site
from llmwiki.raw_docs_site import render_dashboard_body
from llmwiki.render import js
from llmwiki.state_store import read_state, synth_pipeline_shape_ok
from llmwiki.synth.estimate import synthesize_estimate_report
from llmwiki.synth.pipeline import _discover_raw_sessions, refresh_synth_pending


def test_dashboard_inlines_state_mount_not_old_cards():
    body = render_dashboard_body([], 0)
    assert 'id="llmwiki-state-widget"' in body
    assert "data-llmwiki-state-widget" in body
    assert "Pipeline state" in body
    assert "Recent raw documents" in body
    assert "queue-home-content" not in body
    assert "Sync, synthesis, and queue status at a glance" not in body
    assert "<summary><h3" not in body  # commands now live in the JS widget


def test_dashboard_mount_includes_vault_root_attr(tmp_path: Path):
    body = render_dashboard_body([], 0, vault_root=tmp_path, repo_root=tmp_path / "repo")
    assert f'data-vault-root="{tmp_path}"' in body
    assert f'data-repo-root="{tmp_path / "repo"}"' in body


def test_state_widget_js_has_pipeline_table_and_collapsibles():
    assert "renderStateWidget" in js.JS
    assert "state-pipeline-table" in js.JS
    assert "state-knowledge-table" in js.JS
    assert "To synthesize" in js.JS
    assert "Files layer:" in js.JS
    assert "Handled by shell commands." in js.JS
    assert "Knowledge layer: Candidates → Entities / Concepts." in js.JS
    assert "Review on the Candidates page (header/count below) or via agent Commands below." in js.JS
    assert "candidates.html" in js.JS
    assert "trusted_entities" in js.JS
    assert "trusted_concepts" in js.JS
    assert "Candidates to review" in js.JS
    assert "Not synthesized sessions" in js.JS
    assert "Not synthesized docs" in js.JS
    assert "Estimate warnings" in js.JS
    assert "collapse-section" in js.JS
    assert "collapse-sections" in js.JS
    assert "collapse-section-count" in js.JS
    assert "data-llmwiki-state-widget" in js.JS
    assert "llmwiki sync --project" in js.JS
    assert "llmwiki synth" in js.JS
    assert "llmwiki synth --sources-only" in js.JS
    assert "llmwiki synth --candidates-only" in js.JS
    assert "llmwiki synth --estimate" in js.JS
    assert "llmwiki candidates list" in js.JS
    assert "llmwiki candidates promote --slug" in js.JS
    assert "escapeHtml(cmd)" in js.JS
    assert "code.textContent" in js.JS
    assert "Prefer the Command cell text" in js.JS
    assert "/wiki-candidates" in js.JS
    assert "data-repo-root" in js.JS
    assert "llmwiki checkout" in js.JS
    # One-shot agent launchers (prompt starts /wiki-candidates).
    assert 'agentReview("claude")' in js.JS
    assert 'agentReview("agent")' in js.JS
    assert 'agentReview("codex")' in js.JS
    # Gemini CLI adapter is still scaffold — no Home launcher.
    assert 'agentReview("gemini")' not in js.JS
    assert "' \"/wiki-candidates\"'" in js.JS or ' "/wiki-candidates"' in js.JS
    assert "Review/edit pending candidates" in js.JS
    assert "</span> sessions" in js.JS
    assert "state-source-docs" in js.JS
    # Vault is wrong cwd for slash commands — do not advertise opening agents there.
    assert "Open Claude Code in the vault" not in js.JS
    assert " && cursor ." not in js.JS
    assert 'detailsSection("Commands", 13,' in js.JS
    assert "queued " in js.JS
    assert "in progress " in js.JS
    # Knowledge layer is a second table — not dashes on per-agent rows.
    assert 'class="muted">—</td>' not in js.JS
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
    # Path-specific synthesize rows were replaced by the review-gate Commands set (#84).
    assert "llmwiki synthesize --path raw/sessions/" not in js.JS
    assert "llmwiki synthesize --path raw/docs/" not in js.JS
    # Prefer synth over the deprecated synthesize alias in Home Commands.
    assert "llmwiki synthesize --candidates-only" not in js.JS
    # Combined static blurb moved into per-table captions in JS.
    assert "Knowledge layer: To review → Entities / Concepts (vault-wide)." not in js.JS
    assert "vault-wide — not split by agent" not in js.JS
def test_synth_pipeline_shape_ok():
    assert synth_pipeline_shape_ok({"pipeline": {"rows": []}})
    assert synth_pipeline_shape_ok({"pipeline": {"stages": ["raw"], "rows": [{"label": "Claude"}]}})
    assert not synth_pipeline_shape_ok({})
    assert not synth_pipeline_shape_ok({"pipeline": {}})
    assert not synth_pipeline_shape_ok({"pipeline": {"rows": "bad"}})
    assert not synth_pipeline_shape_ok({"pipeline": None})
    assert not synth_pipeline_shape_ok(None)


def test_estimate_pipeline_rows_by_agent(tmp_path: Path):

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
    assert "to_review" in out["pipeline"]["stages"]
    assert out["pipeline"]["to_review"] == 0

    state = read_state(state_file)
    assert state["synth"]["pipeline"]["rows"][0]["label"] == "OpenClaw"
    assert state["synth"]["pending"][0]["agent"] == "OpenClaw"
    assert state["synth"]["pipeline"]["to_review"] == 0


def test_refresh_synth_pending_counts_candidates(tmp_path: Path):
    vault = tmp_path / "vault"
    raw = vault / "raw" / "sessions"
    docs = vault / "raw" / "docs"
    wiki = vault / "wiki"
    (wiki / "sources").mkdir(parents=True)
    cand = wiki / "candidates" / "entities"
    cand.mkdir(parents=True)
    (cand / "Foo.md").write_text(
        "---\ntitle: Foo\nstatus: candidate\nlast_updated: 2020-01-01\n---\n\n# Foo\n",
        encoding="utf-8",
    )
    raw.mkdir(parents=True)
    docs.mkdir(parents=True)
    out = refresh_synth_pending(
        raw_dir=raw,
        docs_dir=docs,
        wiki_sources_dir=wiki / "sources",
        state_file=vault / "llmwiki-state.json",
        include_subagents="all",
        exclude_headless=False,
    )
    assert out["pipeline"]["to_review"] == 1
    assert out["pipeline"]["to_review_by_kind"]["entities"] == 1
    assert out["pipeline"]["to_review_stale"] == 1

def _seed_build_vault(tmp_path: Path) -> Path:
    """Minimal vault with one session so ``build_site`` has something to walk."""
    vault = tmp_path / "vault"
    raw = vault / "raw" / "sessions" / "demo"
    raw.mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki" / "sources").mkdir(parents=True)
    (raw / "2026-07-01T10-00-demo-x.md").write_text(
        '---\ntitle: "S"\ntype: source\nproject: demo\nagent: claude-code\n---\n# S\n',
        encoding="utf-8",
    )
    return vault


def test_build_backfills_missing_pipeline(tmp_path: Path, monkeypatch):
    """#70: v1.4-shaped state (no synth.pipeline) → first build writes rows."""

    vault = _seed_build_vault(tmp_path)
    # Pre-v1.5 state: pending/estimate present, pipeline absent.
    state_path = vault / "llmwiki-state.json"
    state_path.write_text(
        json.dumps(
            {
                "queue": {"items": [], "legacy_pending_paths": []},
                "sync": {"files": {}, "meta": {}, "counters": {}},
                "synth": {
                    "files": {},
                    "pending": [],
                    "pending_total": 0,
                    "pending_updated_at": "2026-07-01T00:00:00Z",
                    "estimate": {"updated_at": "2026-07-01T00:00:00Z"},
                },
                "quarantine": {"entries": []},
                "ops": {
                    "last_queue_run_at": "",
                    "last_lint_run_at": "",
                    "last_reflect_run_at": "",
                },
                "meta": {"schema_version": 1, "updated_at": "", "revision": 1},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert "pipeline" not in json.loads(state_path.read_text(encoding="utf-8"))["synth"]

    monkeypatch.setattr(build_mod, "REPO_ROOT", vault)
    monkeypatch.setattr(build_mod, "RAW_DIR", vault / "raw")
    monkeypatch.setattr(build_mod, "RAW_SESSIONS", vault / "raw" / "sessions")
    monkeypatch.setattr(build_mod, "DEFAULT_OUT_DIR", vault / "site")

    rc = build_site(
        out_dir=vault / "site",
        raw_sessions=vault / "raw" / "sessions",
        raw_dir=vault / "raw",
        wiki_dir=vault / "wiki",
    )
    assert rc == 0
    state = read_state(state_path)
    assert isinstance(state["synth"]["pipeline"]["rows"], list)
    assert state["synth"]["pipeline"]["rows"]
    sidecar = (vault / "llmwiki-state.js").read_text(encoding="utf-8")
    assert "pipeline" in sidecar


def test_build_skips_pipeline_refresh_when_shape_ok(tmp_path: Path, monkeypatch):
    """#70: once pipeline shape exists, build must not re-run the estimate walk."""

    vault = _seed_build_vault(tmp_path)
    state_path = vault / "llmwiki-state.json"
    refresh_synth_pending(
        raw_dir=vault / "raw" / "sessions",
        docs_dir=vault / "raw" / "docs",
        wiki_sources_dir=vault / "wiki" / "sources",
        state_file=state_path,
        include_subagents="all",
        exclude_headless=False,
    )
    calls: list[object] = []

    def _spy(**kwargs):
        calls.append(kwargs)
        raise AssertionError("refresh_synth_pending must not run when shape is ok")

    monkeypatch.setattr(build_mod, "REPO_ROOT", vault)
    monkeypatch.setattr(build_mod, "RAW_DIR", vault / "raw")
    monkeypatch.setattr(build_mod, "RAW_SESSIONS", vault / "raw" / "sessions")
    monkeypatch.setattr(build_mod, "DEFAULT_OUT_DIR", vault / "site")
    monkeypatch.setattr(
        "llmwiki.synth.pipeline.refresh_synth_pending",
        _spy,
    )

    rc = build_site(
        out_dir=vault / "site",
        raw_sessions=vault / "raw" / "sessions",
        raw_dir=vault / "raw",
        wiki_dir=vault / "wiki",
    )
    assert rc == 0
    assert calls == []
