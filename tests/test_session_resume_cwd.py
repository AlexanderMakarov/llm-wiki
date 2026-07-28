"""#36: surface cwd + real sessionId + copyable resume command on
session pages; absolute disk paths as project names.

Frontmatter stores home paths with the username redacted to ``USER``
so ``raw/`` is safe to commit. The site restores the local username
at build time so resume commands and project titles are usable.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from llmwiki import build as build_mod
from llmwiki.build import (
    build_search_index,
    local_cwd,
    project_disk_paths,
    render_project_page,
    render_projects_index,
    render_session,
    render_sessions_index,
    resume_command,
    supports_resume,
)
from llmwiki.convert import restore_local_path

REAL = "alice"
REPL = "USER"


@pytest.fixture(autouse=True)
def _fixed_restore_user(monkeypatch):
    """Pin redaction reverse to alice/USER so tests don't depend on $USER."""
    monkeypatch.setattr(
        "llmwiki.convert.restore_local_path",
        lambda path, real_user=None, repl_user=None: restore_local_path(
            path, real_user=REAL, repl_user=REPL
        ),
    )
    # local_cwd imports restore_local_path inside the function — patch
    # the convert module symbol (already done) is enough.
    yield


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
        "cwd": f"/Users/{REPL}/code/demo-proj",
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


LOCAL_CWD = f"/Users/{REAL}/code/demo-proj"


# ─── path restore ─────────────────────────────────────────────────────


def test_restore_local_path_reverses_username():
    assert (
        restore_local_path(
            f"/home/{REPL}/code/x", real_user=REAL, repl_user=REPL
        )
        == f"/home/{REAL}/code/x"
    )


def test_restore_local_path_noop_without_real_user():
    assert (
        restore_local_path(
            f"/home/{REPL}/code/x", real_user="", repl_user=REPL
        )
        == f"/home/{REPL}/code/x"
    )


def test_local_cwd_restores_redacted_frontmatter():
    assert local_cwd(_meta()) == LOCAL_CWD


# ─── resume helpers ───────────────────────────────────────────────────


def test_supports_resume_for_claude_main_session():
    assert supports_resume(_meta()) is True


def test_supports_resume_false_for_subagent():
    assert supports_resume(_meta(is_subagent=True)) is False


def test_supports_resume_false_for_codex():
    assert supports_resume(_meta(agent="codex", model="gpt-5", tags=["codex-cli"])) is False


def test_resume_command_uses_real_local_path_not_USER():
    cmd = resume_command(_meta())
    assert cmd == (
        f"cd {LOCAL_CWD} && "
        "claude --resume 8057bbe6-73e8-418f-b439-b4d11bad1ad7"
    )
    assert "/Users/USER/" not in cmd
    assert f"/Users/{REAL}/" in cmd


def test_resume_command_none_without_session_id_or_cwd():
    assert resume_command(_meta(sessionId=None, cwd="/x")) is None
    assert resume_command(_meta(sessionId="s", cwd=None)) is None
    assert resume_command(_meta(is_subagent=True)) is None


# ─── session page ─────────────────────────────────────────────────────


def test_session_page_shows_local_cwd_and_session_id(tmp_path: Path):
    path, meta, body = _src()
    out = render_session(path, meta, body, tmp_path, "demo-proj")
    html = out.read_text(encoding="utf-8")
    assert LOCAL_CWD in html
    assert "/Users/USER/code/demo-proj" not in html
    assert "8057bbe6-73e8-418f-b439-b4d11bad1ad7" in html


def test_session_page_has_copyable_resume_command(tmp_path: Path):
    path, meta, body = _src()
    out = render_session(path, meta, body, tmp_path, "demo-proj")
    html = out.read_text(encoding="utf-8")
    assert f"cd {LOCAL_CWD} &amp;&amp; claude --resume 8057bbe6-73e8-418f-b439-b4d11bad1ad7" in html
    assert "resume-command" in html


def test_session_page_hides_resume_for_subagent(tmp_path: Path):
    path, meta, body = _src(_meta(is_subagent=True))
    out = render_session(path, meta, body, tmp_path, "demo-proj")
    html = out.read_text(encoding="utf-8")
    assert "claude --resume" not in html
    assert LOCAL_CWD in html
    assert "8057bbe6-73e8-418f-b439-b4d11bad1ad7" in html


def test_session_page_hides_resume_for_non_claude(tmp_path: Path):
    path, meta, body = _src(
        _meta(agent="codex", model="gpt-5", tags=["codex-cli", "session-transcript"])
    )
    out = render_session(path, meta, body, tmp_path, "demo-proj")
    html = out.read_text(encoding="utf-8")
    assert "claude --resume" not in html


def test_old_session_resume_marked_stale(tmp_path: Path):
    old = (datetime.now(UTC) - timedelta(days=45)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    path, meta, body = _src(_meta(started=old, date=old[:10]))
    out = render_session(path, meta, body, tmp_path, "demo-proj")
    html = out.read_text(encoding="utf-8")
    assert "resume-stale" in html
    assert "claude --resume" in html


# ─── HTML metadata (session id + cwd for agents) ──────────────────────


def test_session_html_metadata_includes_session_id_and_local_cwd(tmp_path: Path):
    path, meta, body = _src()
    out = render_session(path, meta, body, tmp_path, "demo-proj")
    html = out.read_text(encoding="utf-8")
    assert "llmwiki:metadata" in html
    assert "sessionId: 8057bbe6-73e8-418f-b439-b4d11bad1ad7" in html
    assert f"cwd: {LOCAL_CWD}" in html
    assert "md_source: sources/demo-proj/" in html
    assert "txt_sibling:" not in html
    assert "json_sibling:" not in html
    assert 'title="plain-text sibling' not in html
    assert 'title="structured JSON sibling' not in html
    assert "Download .md" in html
    assert 'href="../../sources/demo-proj/' in html

# ─── project disk paths / names ───────────────────────────────────────


def test_project_disk_paths_picks_most_common_restored():
    sessions = [
        _src(_meta(cwd=f"/Users/{REPL}/code/a")),
        _src(_meta(cwd=f"/Users/{REPL}/code/a")),
        _src(_meta(cwd=f"/Users/{REPL}/code/b")),
    ]
    primary, all_paths = project_disk_paths(sessions)
    assert primary == f"/Users/{REAL}/code/a"
    assert all_paths == [f"/Users/{REAL}/code/a", f"/Users/{REAL}/code/b"]


def test_project_disk_paths_empty_when_no_cwd():
    sessions = [_src(_meta(cwd=None)), _src(_meta(cwd=""))]
    primary, all_paths = project_disk_paths(sessions)
    assert primary is None
    assert all_paths == []


def test_project_page_titled_by_absolute_path(tmp_path: Path):
    sessions = [_src(_meta(cwd=f"/Users/{REPL}/code/demo-proj"))]
    out = render_project_page("demo-proj", sessions, tmp_path)
    html = out.read_text(encoding="utf-8")
    assert f"<h1>{LOCAL_CWD}</h1>" in html
    assert "slug <code>demo-proj</code>" in html
    # Single path → no redundant "Also seen at" strip
    assert "Also seen at" not in html


def test_project_page_lists_divergent_cwds(tmp_path: Path):
    sessions = [
        _src(_meta(cwd=f"/Users/{REPL}/code/a")),
        _src(_meta(cwd=f"/Users/{REPL}/code/b")),
    ]
    out = render_project_page("demo-proj", sessions, tmp_path)
    html = out.read_text(encoding="utf-8")
    assert f"/Users/{REAL}/code/a" in html
    assert f"/Users/{REAL}/code/b" in html
    assert "Also seen at" in html
    # comma-delimited, not middot
    assert (
        f"<code>/Users/{REAL}/code/a</code>, "
        f"<code>/Users/{REAL}/code/b</code>"
    ) in html
    assert " · " not in html.split("Also seen at", 1)[1].split("</div>", 1)[0]


def test_projects_index_titled_by_absolute_path(tmp_path: Path):
    sessions = [_src(_meta(cwd=f"/Users/{REPL}/code/demo-proj"))]
    groups = {"demo-proj": sessions}
    out = render_projects_index(groups, tmp_path)
    html = out.read_text(encoding="utf-8")
    assert f"<code>{LOCAL_CWD}</code>" in html
    assert "slug <code>demo-proj</code>" in html


def test_projects_index_other_cwds_label(tmp_path: Path):
    sessions = [
        _src(_meta(cwd=f"/Users/{REPL}/code/a")),
        _src(_meta(cwd=f"/Users/{REPL}/code/b")),
        _src(_meta(cwd=f"/Users/{REPL}/code/c")),
    ]
    out = render_projects_index({"demo-proj": sessions}, tmp_path)
    html = out.read_text(encoding="utf-8")
    assert "(+2 other cwd-s)" in html
    assert "(+2 more)" not in html


def test_project_page_does_not_render_homepage(tmp_path: Path, monkeypatch):
    """External homepage under the topic chips was noise next to the cwd title."""

    monkeypatch.setattr(
        build_mod,
        "load_project_profile",
        lambda *_a, **_k: {
            "topics": ["python"],
            "homepage": "https://github.com/example/repo",
            "description": "",
        },
    )
    monkeypatch.setattr(
        build_mod,
        "get_project_topics",
        lambda *_a, **_k: ["python"],
    )
    sessions = [_src(_meta(cwd=f"/Users/{REPL}/code/demo-proj"))]
    out = render_project_page("demo-proj", sessions, tmp_path)
    html = out.read_text(encoding="utf-8")
    assert "project-homepage" not in html
    assert "https://github.com/example/repo" not in html
    assert 'class="project-page"' in html


# ─── search index ─────────────────────────────────────────────────────


def test_search_index_includes_session_id(tmp_path: Path):
    sources = [_src()]
    groups = {"demo-proj": sources}
    build_search_index(sources, groups, tmp_path)
    chunk = tmp_path / "search-chunks" / "demo-proj.json"
    entries = json.loads(chunk.read_text(encoding="utf-8"))
    assert entries[0]["sessionId"] == "8057bbe6-73e8-418f-b439-b4d11bad1ad7"


# ─── #56: encoded segments + index pages ───────────────────────────────


def test_restore_local_path_encoded_users_segment():
    assert (
        restore_local_path(
            "/Users/USER/.claude/projects/-Users-USER-code-demo/x",
            real_user=REAL,
            repl_user=REPL,
        )
        == f"/Users/{REAL}/.claude/projects/-Users-{REAL}-code-demo/x"
    )


def test_restore_local_path_encoded_home_segment():
    assert (
        restore_local_path(
            "/home/USER/.claude/projects/-home-USER-code-app/x",
            real_user=REAL,
            repl_user=REPL,
        )
        == f"/home/{REAL}/.claude/projects/-home-{REAL}-code-app/x"
    )


def test_projects_index_restores_all_titles_including_encoded(tmp_path: Path):
    """#56 defect 1: every card title must be restored, including cwds
    under ``~/.claude/projects/-Users-…``."""
    groups = {
        "demo-a": [_src(_meta(cwd=f"/Users/{REPL}/code/demo-a", project="demo-a"))],
        "demo-b": [
            _src(
                _meta(
                    cwd=(
                        f"/Users/{REPL}/.claude/projects/"
                        f"-Users-{REPL}-code-demo-b"
                    ),
                    project="demo-b",
                )
            )
        ],
    }
    out = render_projects_index(groups, tmp_path)
    html = out.read_text(encoding="utf-8")
    assert f"/Users/{REAL}/code/demo-a" in html
    assert (
        f"/Users/{REAL}/.claude/projects/-Users-{REAL}-code-demo-b" in html
    )
    assert "/Users/USER/" not in html


def test_sessions_index_shows_restored_cwd(tmp_path: Path):
    """#56 defect 2: sessions table cwd column uses restored local path."""

    sources = [
        _src(
            _meta(
                cwd=(
                    f"/Users/{REPL}/.claude/projects/"
                    f"-Users-{REPL}-code-demo"
                )
            )
        )
    ]
    groups = {"demo-proj": sources}
    out = render_sessions_index(sources, groups, tmp_path)
    html = out.read_text(encoding="utf-8")
    restored = (
        f"/Users/{REAL}/.claude/projects/-Users-{REAL}-code-demo"
    )
    assert restored in html
    assert "/Users/USER/" not in html


def test_sessions_index_restores_paths_in_description(tmp_path: Path):

    sources = [
        _src(
            _meta(
                description=(
                    f"Review the repo at /Users/{REPL}/code/demo-proj"
                )
            )
        )
    ]
    out = render_sessions_index(sources, {"demo-proj": sources}, tmp_path)
    html = out.read_text(encoding="utf-8")
    assert f"/Users/{REAL}/code/demo-proj" in html
    assert "/Users/USER/" not in html
