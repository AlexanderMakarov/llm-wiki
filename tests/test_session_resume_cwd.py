"""#36: surface cwd + real sessionId + copyable resume command on
session pages; disk paths on project pages.

The static site is the browsing UI for session history, but gave no
direct way to get back into a session (`claude --resume`) and no way
to tell where on disk a project lives. All the data already exists in
raw frontmatter — the builder just didn't surface it.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from llmwiki.build import (
    build_search_index,
    project_disk_paths,
    render_project_page,
    render_projects_index,
    render_session,
    resume_command,
    supports_resume,
)
from llmwiki.exporters import write_page_json


# ─── helpers ──────────────────────────────────────────────────────────


def _meta(**overrides) -> dict:
    base = {
        "title": "Session: abc12345 — 2026-07-20",
        "slug": "abc12345",
        "project": "demo-proj",
        "date": "2026-07-20",
        "started": "2026-07-20T12:00:00+00:00",
        "model": "claude-sonnet-4-6",
        "agent": "claude-code",
        "sessionId": "8057bbe6-73e8-418f-b439-b4d11bad1ad7",
        "cwd": "/Users/USER/code/demo-proj",
        "gitBranch": "main",
        "is_subagent": False,
        "user_messages": 3,
        "tool_calls": 5,
        "tags": ["claude-code", "session-transcript"],
    }
    base.update(overrides)
    return base


def _src(meta: dict | None = None, stem: str = "2026-07-20T12-00-demo-proj-abc12345"):
    m = meta or _meta()
    return (Path(f"raw/sessions/{stem}.md"), m, "## Conversation\n\nhello\n")


# ─── resume helpers ───────────────────────────────────────────────────


def test_supports_resume_for_claude_main_session():
    assert supports_resume(_meta()) is True


def test_supports_resume_false_for_subagent():
    assert supports_resume(_meta(is_subagent=True)) is False


def test_supports_resume_false_for_codex():
    assert supports_resume(_meta(agent="codex", model="gpt-5", tags=["codex-cli"])) is False


def test_resume_command_shape():
    cmd = resume_command(_meta())
    assert cmd == (
        "cd /Users/USER/code/demo-proj && "
        "claude --resume 8057bbe6-73e8-418f-b439-b4d11bad1ad7"
    )


def test_resume_command_none_without_session_id_or_cwd():
    assert resume_command(_meta(sessionId=None, cwd="/x")) is None
    assert resume_command(_meta(sessionId="s", cwd=None)) is None
    assert resume_command(_meta(is_subagent=True)) is None


# ─── session page ─────────────────────────────────────────────────────


def test_session_page_shows_cwd_and_session_id(tmp_path: Path):
    path, meta, body = _src()
    out = render_session(path, meta, body, tmp_path, "demo-proj")
    html = out.read_text(encoding="utf-8")
    assert "/Users/USER/code/demo-proj" in html
    assert "8057bbe6-73e8-418f-b439-b4d11bad1ad7" in html


def test_session_page_has_copyable_resume_command(tmp_path: Path):
    path, meta, body = _src()
    out = render_session(path, meta, body, tmp_path, "demo-proj")
    html = out.read_text(encoding="utf-8")
    assert "claude --resume 8057bbe6-73e8-418f-b439-b4d11bad1ad7" in html
    assert "copyResume" in html or 'class="resume-command"' in html
    assert "resume-command" in html


def test_session_page_hides_resume_for_subagent(tmp_path: Path):
    path, meta, body = _src(_meta(is_subagent=True))
    out = render_session(path, meta, body, tmp_path, "demo-proj")
    html = out.read_text(encoding="utf-8")
    assert "claude --resume" not in html
    # cwd + sessionId still visible for orientation
    assert "/Users/USER/code/demo-proj" in html
    assert "8057bbe6-73e8-418f-b439-b4d11bad1ad7" in html


def test_session_page_hides_resume_for_non_claude(tmp_path: Path):
    path, meta, body = _src(
        _meta(agent="codex", model="gpt-5", tags=["codex-cli", "session-transcript"])
    )
    out = render_session(path, meta, body, tmp_path, "demo-proj")
    html = out.read_text(encoding="utf-8")
    assert "claude --resume" not in html


def test_old_session_resume_marked_stale(tmp_path: Path):
    old = (datetime.now(timezone.utc) - timedelta(days=45)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    path, meta, body = _src(_meta(started=old, date=old[:10]))
    out = render_session(path, meta, body, tmp_path, "demo-proj")
    html = out.read_text(encoding="utf-8")
    assert "resume-stale" in html
    assert "claude --resume" in html


# ─── JSON sibling ─────────────────────────────────────────────────────


def test_json_sibling_includes_session_id(tmp_path: Path):
    html_path = tmp_path / "sessions" / "demo-proj" / "sess.html"
    html_path.parent.mkdir(parents=True)
    html_path.write_text("<html></html>", encoding="utf-8")
    meta = _meta()
    jsn = write_page_json(html_path, meta, "body", [])
    data = json.loads(jsn.read_text(encoding="utf-8"))
    assert data["sessionId"] == "8057bbe6-73e8-418f-b439-b4d11bad1ad7"
    assert data["cwd"] == "/Users/USER/code/demo-proj"


# ─── project disk paths ───────────────────────────────────────────────


def test_project_disk_paths_picks_most_common():
    sessions = [
        _src(_meta(cwd="/Users/USER/code/a")),
        _src(_meta(cwd="/Users/USER/code/a")),
        _src(_meta(cwd="/Users/USER/code/b")),
    ]
    primary, all_paths = project_disk_paths(sessions)
    assert primary == "/Users/USER/code/a"
    assert all_paths == ["/Users/USER/code/a", "/Users/USER/code/b"]


def test_project_disk_paths_empty_when_no_cwd():
    sessions = [_src(_meta(cwd=None)), _src(_meta(cwd=""))]
    primary, all_paths = project_disk_paths(sessions)
    assert primary is None
    assert all_paths == []


def test_project_page_shows_disk_path(tmp_path: Path):
    sessions = [_src(_meta(cwd="/Users/USER/code/demo-proj"))]
    out = render_project_page("demo-proj", sessions, tmp_path)
    html = out.read_text(encoding="utf-8")
    assert "/Users/USER/code/demo-proj" in html
    assert "project-disk-path" in html


def test_project_page_lists_divergent_cwds(tmp_path: Path):
    sessions = [
        _src(_meta(cwd="/Users/USER/code/a")),
        _src(_meta(cwd="/Users/USER/code/b")),
    ]
    out = render_project_page("demo-proj", sessions, tmp_path)
    html = out.read_text(encoding="utf-8")
    assert "/Users/USER/code/a" in html
    assert "/Users/USER/code/b" in html


def test_projects_index_shows_disk_path(tmp_path: Path):
    sessions = [_src(_meta(cwd="/Users/USER/code/demo-proj"))]
    groups = {"demo-proj": sessions}
    out = render_projects_index(groups, tmp_path)
    html = out.read_text(encoding="utf-8")
    assert "/Users/USER/code/demo-proj" in html


# ─── search index ─────────────────────────────────────────────────────


def test_search_index_includes_session_id(tmp_path: Path):
    sources = [_src()]
    groups = {"demo-proj": sources}
    build_search_index(sources, groups, tmp_path)
    chunk = tmp_path / "search-chunks" / "demo-proj.json"
    entries = json.loads(chunk.read_text(encoding="utf-8"))
    assert entries[0]["sessionId"] == "8057bbe6-73e8-418f-b439-b4d11bad1ad7"
