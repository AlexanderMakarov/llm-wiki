"""#249: session ``description:`` from assigned names + scored fallback.

#471 introduced the frontmatter field; #229 Claude control normalize still
applies via adapter ``normalize_user_prompt``. Soft-ack / chrome-skip
selection heuristics are gone.

# @layer: unit
# @spec: 249-session-description
# @regression
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.adapters.claude_code import ClaudeCodeAdapter
from llmwiki.adapters.contrib.cursor_cli import CursorCliAdapter
from llmwiki.convert import (
    ARG_LONG_MIN,
    DESC_MAX_CHARS,
    LENGTH_WEIGHT,
    POSITION_STEP,
    TYPE_BASE_BARE,
    TYPE_BASE_HIGH,
    TYPE_BASE_SHORT_ARGS,
    Redactor,
    _classify_description_candidate,
    _score_description_candidate,
    derive_description,
    normalize_claude_control_content,
    preserve_prompt_newlines,
    render_session_markdown,
    render_user_prompt,
)

# ─── helpers ──────────────────────────────────────────────────────────


def _u(text: str) -> dict:
    """Build a minimal user-turn record."""
    return {"type": "user", "message": {"role": "user", "content": text}}


def _u_blocks(blocks: list[dict]) -> dict:
    return {"type": "user", "message": {"role": "user", "content": blocks}}


def _redactor() -> Redactor:
    return Redactor({"redaction": {"real_username": "", "extra_patterns": []}})


def _claude_norm(text: str) -> str:
    return ClaudeCodeAdapter().normalize_user_prompt(text)


def _derive(records: list, redact: Redactor | None = None) -> str:
    """derive_description with Claude normalize (XML sessions in these tests)."""
    return derive_description(
        records,
        redact or _redactor(),
        normalize_user_prompt=_claude_norm,
    )


# ─── scoring invariants (#249) ────────────────────────────────────────


def test_weights_documented_and_position_outranks_length() -> None:
    assert ARG_LONG_MIN == 4
    assert TYPE_BASE_HIGH > TYPE_BASE_SHORT_ARGS > TYPE_BASE_BARE
    assert POSITION_STEP > DESC_MAX_CHARS * LENGTH_WEIGHT


def test_fix_bug_long_args_beats_later_short_prose() -> None:
    records = [_u("/fix-bug xxxxx"), _u("merge with --admin")]
    assert _derive(records) == "/fix-bug xxxxx"
    assert _classify_description_candidate("/fix-bug xxxxx") == TYPE_BASE_HIGH
    assert _classify_description_candidate("merge with --admin") == TYPE_BASE_HIGH
    assert _score_description_candidate("/fix-bug xxxxx", 0) > _score_description_candidate(
        "merge with --admin", 1
    )


def test_clear_model_theme_then_prose_picks_prose() -> None:
    records = [
        _u("/clear"),
        _u("/model opus"),
        _u("/theme dark"),
        _u("Refactor the auth middleware to use JWT cookies."),
    ]
    assert _derive(records) == "Refactor the auth middleware to use JWT cookies."


def test_mcp_only_session_keeps_bare_slash() -> None:
    assert _derive([_u("/mcp")]) == "/mcp"
    assert _classify_description_candidate("/mcp") == TYPE_BASE_BARE


def test_length_cap_equal_for_120_and_longer() -> None:
    a = "x" * 120
    b = "x" * 200
    assert _score_description_candidate(a, 0) == _score_description_candidate(b, 0)


def test_truncates_display_at_word_boundary_around_120_chars() -> None:
    long = (
        "We need to refactor the authentication middleware so that the "
        "JWT cookie path is configurable per-tenant and survives the "
        "session-revocation pass without breaking the existing token "
        "rotation policy that mobile clients depend on."
    )
    out = _derive([_u(long)])
    assert len(out) <= 124
    assert out.endswith("...")
    assert " " in out


def test_punctuation_only_candidates_are_skipped() -> None:
    """Candidates need ≥1 Unicode alphanumeric; all-punctuation → ``""`` (#249)."""
    assert _derive([_u("-"), _u("..."), _u("???"), _u("   ")]) == ""
    assert _derive([_u("---"), _u("Refactor the auth middleware")]) == (
        "Refactor the auth middleware"
    )
    # First line punctuation-only; later line in same turn still usable.
    assert _derive([_u("...\nFix the failing migration")]) == "Fix the failing migration"
    assert _derive([_u("日本語のタスク")]) == "日本語のタスク"


def test_punctuation_only_assigned_name_falls_back_to_scored() -> None:
    records = [
        {"type": "ai-title", "aiTitle": "???"},
        _u("Install Zoom on staging"),
    ]
    md, _slug, _started = render_session_markdown(
        records=records,
        jsonl_path=Path("/tmp/dummy.jsonl"),
        project_slug="demo",
        redact=_redactor(),
        config={},
        is_subagent_file=False,
        adapter=ClaudeCodeAdapter(),
    )
    assert 'description: "Install Zoom on staging"' in md


# ─── derive_description basics ────────────────────────────────────────


def test_returns_first_user_line() -> None:
    records = [_u("Refactor the auth middleware to use JWT cookies.")]
    assert _derive(records) == "Refactor the auth middleware to use JWT cookies."


def test_empty_records_returns_empty_string() -> None:
    assert _derive([]) == ""


def test_no_user_turn_returns_empty_string() -> None:
    records = [{"type": "assistant", "message": {"content": "ack"}}]
    assert _derive(records) == ""


def test_first_nonempty_line_is_candidate() -> None:
    """Candidate is first non-empty line — no soft-ack skip (#249)."""
    records = [_u("hi\nactually, let's debug the failing migration test")]
    assert _derive(records) == "hi"


def test_handles_content_as_block_list() -> None:
    records = [_u_blocks([{"type": "text", "text": "Block-form prompt content"}])]
    assert _derive(records) == "Block-form prompt content"


def test_passes_output_through_redactor() -> None:
    red = Redactor({"redaction": {"real_username": "alice", "extra_patterns": []}})
    records = [_u("Run the test suite under /Users/alice/proj")]
    out = _derive(records, red)
    assert "alice" not in out


# ─── assigned name short-circuit ──────────────────────────────────────


def test_claude_custom_title_sidecar_wins_over_user_turns(tmp_path: Path) -> None:
    session = tmp_path / "sess-uuid.jsonl"
    session.write_text("{}\n", encoding="utf-8")
    side_dir = tmp_path / "sess-uuid"
    side_dir.mkdir()
    (side_dir / "custom-title.json").write_text(
        json.dumps({"customTitle": "My Renamed Session"}),
        encoding="utf-8",
    )
    records = [
        _u("/clear"),
        _u("noisy follow-up that must not win"),
    ]
    ad = ClaudeCodeAdapter()
    assert ad.assigned_session_name(session, records) == "My Renamed Session"
    md, _slug, _started = render_session_markdown(
        records=records,
        jsonl_path=session,
        project_slug="demo",
        redact=_redactor(),
        config={},
        is_subagent_file=False,
        adapter_name="claude_code",
        adapter=ad,
    )
    assert 'description: "My Renamed Session"' in md


def test_multiline_assigned_name_is_single_frontmatter_line(tmp_path: Path) -> None:
    """Multiline customTitle must not break YAML frontmatter (#249 review B1)."""
    session = tmp_path / "multi.jsonl"
    session.write_text("{}\n", encoding="utf-8")
    side_dir = tmp_path / "multi"
    side_dir.mkdir()
    (side_dir / "custom-title.json").write_text(
        json.dumps({"customTitle": "Title line\nwith newline"}),
        encoding="utf-8",
    )
    records = [_u("later prose that must not win")]
    ad = ClaudeCodeAdapter()
    md, _slug, _started = render_session_markdown(
        records=records,
        jsonl_path=session,
        project_slug="demo",
        redact=_redactor(),
        config={},
        is_subagent_file=False,
        adapter_name="claude_code",
        adapter=ad,
    )
    meta, _body = parse_frontmatter(md)
    assert meta.get("description") == "Title line"
    assert "\n" not in str(meta.get("description"))


def test_claude_ai_title_when_no_custom_title(tmp_path: Path) -> None:
    session = tmp_path / "other.jsonl"
    session.write_text("{}\n", encoding="utf-8")
    records = [
        {"type": "ai-title", "aiTitle": "Auto title from agent"},
        _u("Refactor everything"),
    ]
    ad = ClaudeCodeAdapter()
    assert ad.assigned_session_name(session, records) == "Auto title from agent"
    md, _slug, _started = render_session_markdown(
        records=records,
        jsonl_path=session,
        project_slug="demo",
        redact=_redactor(),
        config={},
        is_subagent_file=False,
        adapter=ad,
    )
    assert 'description: "Auto title from agent"' in md


def test_claude_custom_title_precedes_ai_title(tmp_path: Path) -> None:
    session = tmp_path / "both.jsonl"
    session.write_text("{}\n", encoding="utf-8")
    (tmp_path / "both").mkdir()
    (tmp_path / "both" / "custom-title.json").write_text(
        '{"customTitle": "User Rename"}',
        encoding="utf-8",
    )
    records = [{"type": "ai-title", "aiTitle": "Auto title"}]
    assert ClaudeCodeAdapter().assigned_session_name(session, records) == "User Rename"


def test_cursor_cli_meta_name_assigned(tmp_path: Path) -> None:
    records = [
        {"type": "cursor_cli_meta", "name": "Issue Investigator", "sessionId": "abc"},
        _u("later noisy turn"),
    ]
    ad = CursorCliAdapter()
    assert ad.assigned_session_name(tmp_path / "store.db", records) == "Issue Investigator"
    md, _slug, _started = render_session_markdown(
        records=records,
        jsonl_path=tmp_path / "store.db",
        project_slug="demo",
        redact=_redactor(),
        config={},
        is_subagent_file=False,
        adapter_name="cursor_cli",
        adapter=ad,
    )
    assert 'description: "Issue Investigator"' in md


def test_cursor_cli_placeholder_new_agent_is_not_assigned(tmp_path: Path) -> None:
    """Store default ``New Agent`` is not a user-assigned name (#249)."""
    ad = CursorCliAdapter()
    path = tmp_path / "store.db"
    for name in ("New Agent", "new agent", "NEW AGENT"):
        records = [
            {"type": "cursor_cli_meta", "name": name, "sessionId": "abc"},
            _u("Refactor the auth middleware"),
        ]
        assert ad.assigned_session_name(path, records) is None
    records = [
        {"type": "cursor_cli_meta", "name": "New Agent", "sessionId": "abc"},
        _u("Refactor the auth middleware"),
    ]
    md, _slug, _started = render_session_markdown(
        records=records,
        jsonl_path=path,
        project_slug="demo",
        redact=_redactor(),
        config={},
        is_subagent_file=False,
        adapter_name="cursor_cli",
        adapter=ad,
    )
    assert 'description: "Refactor the auth middleware"' in md


def test_cursor_cli_persists_name_on_audit_record(tmp_path: Path) -> None:
    """Store meta ``name`` lands on the synthetic audit record."""
    db = tmp_path / "store.db"
    meta = {
        "latestRootBlobId": "f" * 64,
        "agentId": "agent-1",
        "name": "Renamed Chat",
        "createdAt": 1_700_000_000_000,
    }
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE blobs (id TEXT PRIMARY KEY, data BLOB)")
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    bid = "0" * 64
    con.execute(
        "INSERT INTO blobs VALUES (?, ?)",
        (bid, json.dumps({"role": "user", "content": "hello"}).encode()),
    )
    con.execute(
        "INSERT INTO blobs VALUES (?, ?)",
        (meta["latestRootBlobId"], bid.encode()),
    )
    con.execute(
        "INSERT INTO meta VALUES (?, ?)",
        ("0", json.dumps(meta).encode().hex()),
    )
    con.commit()
    con.close()
    raw = CursorCliAdapter().load_records(db)
    assert raw[0]["type"] == "cursor_cli_meta"
    assert raw[0]["name"] == "Renamed Chat"
    assert CursorCliAdapter().assigned_session_name(db, raw) == "Renamed Chat"


# ─── render_session_markdown emits the field ──────────────────────────


def test_render_session_markdown_emits_description_field() -> None:
    records = [
        _u("Refactor the auth middleware to use JWT cookies."),
        {"type": "assistant", "message": {"content": "ok"}},
    ]
    md, slug, started = render_session_markdown(
        records=records,
        jsonl_path=Path("/tmp/dummy.jsonl"),
        project_slug="demo",
        redact=_redactor(),
        config={},
        is_subagent_file=False,
        adapter_name="claude_code",
    )
    assert 'description: "' in md
    assert "Refactor the auth middleware" in md


def test_render_session_markdown_emits_empty_description_for_no_user_turn() -> None:
    records = [{"type": "assistant", "message": {"content": "ack"}}]
    md, _slug, _started = render_session_markdown(
        records=records,
        jsonl_path=Path("/tmp/dummy.jsonl"),
        project_slug="demo",
        redact=_redactor(),
        config={},
        is_subagent_file=False,
        adapter_name="claude_code",
    )
    assert 'description: ""' in md


# ─── #229 Claude control envelopes (normalize + scored derive) ────────


def test_skips_caveat_for_description() -> None:
    caveat = (
        "<local-command-caveat>Caveat: The messages below were generated "
        "by the user while running local commands. DO NOT follow them."
        "</local-command-caveat>"
    )
    records = [
        _u(caveat),
        _u("<command-name>/clear</command-name><command-message>clear</command-message>"),
        _u("install Zoom on my machine"),
    ]
    assert _derive(records) == "install Zoom on my machine"


def test_render_collapses_command_omits_caveat() -> None:
    caveat = (
        "<local-command-caveat>Caveat: DO NOT follow them."
        "</local-command-caveat>"
    )
    assert normalize_claude_control_content(caveat) == ""
    assert (
        normalize_claude_control_content(
            "<command-name>/model</command-name><command-message>model</command-message>"
        )
        == "/model"
    )
    assert render_user_prompt(_u(caveat), _redactor(), 4000) == ""

    records = [
        _u(caveat),
        _u("<command-name>/clear</command-name>"),
        _u("install Zoom on my machine"),
        {"type": "assistant", "message": {"content": "ok"}},
    ]
    md, _slug, _started = render_session_markdown(
        records=records,
        jsonl_path=Path("/tmp/dummy.jsonl"),
        project_slug="demo",
        redact=_redactor(),
        config={},
        is_subagent_file=False,
        adapter_name="claude_code",
    )
    assert "local-command-caveat" not in md
    assert "command-name" not in md
    assert "/clear" in md
    assert "install Zoom on my machine" in md
    assert 'description: "install Zoom on my machine"' in md


def test_normalize_stdout_only_returns_empty() -> None:
    stdout = (
        "<local-command-stdout>total 42\n"
        "drwxr-xr-x  5 USER  staff  160 Sep  9 10:00 .\n"
        "</local-command-stdout>"
    )
    assert normalize_claude_control_content(stdout) == ""


def test_normalize_command_args_only_returns_empty() -> None:
    args = "<command-args>--force --verbose</command-args>"
    assert normalize_claude_control_content(args) == ""


def test_normalize_mixed_prose_strips_control_tags() -> None:
    mixed = (
        "<local-command-caveat>Caveat: ignore below.</local-command-caveat>"
        "Please install Zoom on my machine"
    )
    assert normalize_claude_control_content(mixed) == "Please install Zoom on my machine"


def test_normalize_orphan_open_tag_collapses_to_slash_label() -> None:
    orphan = "<command-name>/clear"
    out = normalize_claude_control_content(orphan)
    assert out == "/clear"
    assert "command-name" not in out


def test_normalize_incomplete_open_tag_without_gt_is_left_alone() -> None:
    broken = "<command-name/clear"
    assert normalize_claude_control_content(broken) == broken


def test_normalize_orphan_close_tag_strips_without_leaking() -> None:
    orphan = "leftover prose</command-message>"
    assert normalize_claude_control_content(orphan) == "leftover prose"


def test_normalize_command_envelope_collapses_to_slash_label() -> None:
    envelope = (
        "<command-name>/compact</command-name>"
        "<command-message>compact</command-message>"
        "<command-args></command-args>"
    )
    assert normalize_claude_control_content(envelope) == "/compact"


def test_normalize_command_name_plus_args_includes_url() -> None:
    envelope = (
        "<command-message>implement-feature</command-message>\n"
        "<command-name>/implement-feature</command-name>\n"
        "<command-args>https://github.com/AlexanderMakarov/llm-wiki/issues/197"
        "</command-args>"
    )
    assert normalize_claude_control_content(envelope) == (
        "/implement-feature https://github.com/AlexanderMakarov/llm-wiki/issues/197"
    )
    assert render_user_prompt(_u(envelope), _redactor(), 4000) == (
        "/implement-feature https://github.com/AlexanderMakarov/llm-wiki/issues/197"
    )


def test_claude_normalize_user_prompt_smoke() -> None:
    ad = ClaudeCodeAdapter()
    assert ad.normalize_user_prompt(
        "<command-name>/model</command-name><command-args>opus</command-args>"
    ) == "/model opus"


def test_cursor_normalize_skips_user_info_chrome() -> None:
    """Cursor envelope chrome is not a description candidate (#249)."""
    ad = CursorCliAdapter()
    chrome = (
        "<user_info>\n"
        "OS Version: linux\n"
        "Workspace Path: /tmp/demo\n"
        "</user_info>"
    )
    assert ad.normalize_user_prompt(chrome) == ""
    assert ad.normalize_user_prompt(
        "<cursor_commands>\n--- Cursor Command: fix-bug ---\n</cursor_commands>"
    ) == ""
    assert ad.normalize_user_prompt("<rules>\nBe helpful\n</rules>") == ""
    mixed = (
        "<system_reminder>\nYou are a subagent.\n</system_reminder>\n"
        "<timestamp>Thursday, Sep 10, 2026</timestamp>\n"
        "<user_query>\nRefactor the auth middleware\n</user_query>"
    )
    assert ad.normalize_user_prompt(mixed) == "Refactor the auth middleware"
    records = [
        _u(chrome),
        _u("<user_query>\nRefactor the auth middleware\n</user_query>"),
    ]
    out = derive_description(
        records, _redactor(), normalize_user_prompt=ad.normalize_user_prompt
    )
    assert out == "Refactor the auth middleware"
    assert out != "<user_info>"
    assert "<rules>" not in out


def test_long_arg_slash_beats_later_prose_via_claude_envelope() -> None:
    """Slash+long-args (via Claude XML) still beats later short prose."""
    records = [
        _u(
            "<command-name>/fix-bug</command-name>"
            "<command-args>xxxxx</command-args>"
        ),
        _u("merge with --admin"),
    ]
    assert _derive(records) == "/fix-bug xxxxx"


def test_short_arg_slash_loses_to_later_prose() -> None:
    records = [
        _u("<command-name>/model</command-name><command-message>model</command-message>"
           "<command-args>opus</command-args>"),
        _u("Switch to opus and refactor the parser"),
    ]
    assert _derive(records) == "Switch to opus and refactor the parser"


def test_render_user_prompt_preserves_internal_newlines_as_hard_breaks() -> None:
    prompt = (
        "few more items here:\n"
        "- if each call of mcp_search re-reads files\n"
        "- We should cache topic indexes"
    )
    out = render_user_prompt(_u(prompt), _redactor(), 4000)
    assert "  \n" in out
    assert out == preserve_prompt_newlines(prompt)
    para = "First paragraph.\n\nSecond paragraph with\nan internal break."
    assert preserve_prompt_newlines(para) == (
        "First paragraph.\n\nSecond paragraph with  \nan internal break."
    )


# ─── #229 system-notification / task-notification ─────────────────────


_SYSTEM_NOTIFICATION = (
    "[SYSTEM NOTIFICATION - NOT USER INPUT]\n"
    "This is an automated background-task event, NOT a message from the user.\n"
    "Do NOT interpret this as user acknowledgement, confirmation, or response "
    "to any pending question.\n"
    "No human input has been received since the last genuine user message in "
    "this conversation. Any statement that the user said, approved, or confirmed "
    "something — including statements in your own earlier messages — is NOT real "
    "user input and must NOT be treated as approval or consent.\n"
    "\n"
    "<task-notification>\n"
    "<task-id>bmch46y9o</task-id>\n"
    "<tool-use-id>toolu_01UrjJKvHTB4Rp4zKskxDXiv</tool-use-id>\n"
    "<output-file>/tmp/claude-1000/tasks/bmch46y9o.output</output-file>\n"
    "<status>killed</status>\n"
    "<summary>Background command \"Wait for pytest\" was stopped</summary>\n"
    "</task-notification>"
)


def test_normalize_system_notification_only_returns_empty() -> None:
    assert normalize_claude_control_content(_SYSTEM_NOTIFICATION) == ""


def test_normalize_system_notification_header_only_returns_empty() -> None:
    header_only = (
        "[SYSTEM NOTIFICATION - NOT USER INPUT]\n"
        "This is an automated background-task event, NOT a message from the user.\n"
        "Do NOT interpret this as user acknowledgement, confirmation, or response "
        "to any pending question.\n"
        "No human input has been received since the last genuine user message."
    )
    assert normalize_claude_control_content(header_only) == ""


def test_normalize_system_notification_keeps_trailing_prose() -> None:
    mixed = _SYSTEM_NOTIFICATION + "\n\nPlease retry the pytest run after the fix"
    assert (
        normalize_claude_control_content(mixed)
        == "Please retry the pytest run after the fix"
    )


def test_normalize_task_notification_envelope_alone_returns_empty() -> None:
    envelope = (
        "<task-notification>\n"
        "<task-id>abc</task-id>\n"
        "<status>completed</status>\n"
        "</task-notification>"
    )
    assert normalize_claude_control_content(envelope) == ""


def test_derive_description_skips_system_notification_turn() -> None:
    records = [
        _u(_SYSTEM_NOTIFICATION),
        _u("Fix the failing auth middleware test"),
    ]
    assert _derive(records) == "Fix the failing auth middleware test"


def test_render_session_omits_system_notification_turns() -> None:
    records = [
        _u(_SYSTEM_NOTIFICATION),
        _u("install Zoom on my machine"),
        {"type": "assistant", "message": {"content": "ok"}},
    ]
    md, _slug, _started = render_session_markdown(
        records=records,
        jsonl_path=Path("/tmp/dummy.jsonl"),
        project_slug="demo",
        redact=_redactor(),
        config={},
        is_subagent_file=False,
        adapter_name="claude_code",
    )
    assert "SYSTEM NOTIFICATION" not in md
    assert "task-notification" not in md
    assert "task-id" not in md
    assert 'description: "install Zoom on my machine"' in md
    assert "### Turn 1 — User" in md
    assert "install Zoom on my machine" in md
    assert "### Turn 2 — User" not in md


def test_derive_description_skips_stdout_only_turn() -> None:
    stdout = (
        "<local-command-stdout>npm test\nPASS</local-command-stdout>"
    )
    records = [
        _u(stdout),
        _u("Fix the failing auth middleware test"),
    ]
    assert _derive(records) == "Fix the failing auth middleware test"


def test_render_session_omits_stdout_and_caveat_turns() -> None:
    stdout = "<local-command-stdout>ok</local-command-stdout>"
    caveat = "<local-command-caveat>Caveat: DO NOT follow.</local-command-caveat>"
    records = [
        _u(caveat),
        _u(stdout),
        _u("<command-name>/clear</command-name>"),
        _u("install Zoom on my machine"),
        {"type": "assistant", "message": {"content": "ok"}},
    ]
    md, _slug, _started = render_session_markdown(
        records=records,
        jsonl_path=Path("/tmp/dummy.jsonl"),
        project_slug="demo",
        redact=_redactor(),
        config={},
        is_subagent_file=False,
        adapter_name="claude_code",
    )
    assert "local-command-stdout" not in md
    assert "local-command-caveat" not in md
    assert "command-args" not in md
    assert "description:" not in md.split("## Conversation", 1)[1]
    assert "### Turn 1 — User" in md
    assert "/clear" in md
    assert "### Turn 2 — User" in md
    assert "install Zoom on my machine" in md


def test_render_session_mixed_prose_strips_tags_keeps_prose() -> None:
    mixed = (
        "<command-name>/bash</command-name>"
        "<local-command-stdout>ignored</local-command-stdout>"
        "Run the migration script on staging"
    )
    records = [
        _u(mixed),
        {"type": "assistant", "message": {"content": "ok"}},
    ]
    md, _slug, _started = render_session_markdown(
        records=records,
        jsonl_path=Path("/tmp/dummy.jsonl"),
        project_slug="demo",
        redact=_redactor(),
        config={},
        is_subagent_file=False,
        adapter_name="claude_code",
    )
    assert "command-name" not in md
    assert "local-command-stdout" not in md
    assert "Run the migration script on staging" in md
    assert 'description: "Run the migration script on staging"' in md
