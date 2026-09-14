"""Regression tests for #253: username redaction in home paths is opt-in.

A private vault's ``raw/`` must keep real home paths by default. The
``redaction.redact_username`` key turns the rewrite on for publishing.
Token, email and ``extra_patterns`` redaction always run.
"""

# @layer: integration
# @spec: 253-private-vault-real-paths
# @regression

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki import convert as c
from llmwiki.adapters.claude_code import ClaudeCodeAdapter
from llmwiki.add_doc import _source_path_label
from llmwiki.convert import (
    DEFAULT_CONFIG,
    DEFAULT_CONFIG_FILE,
    Redactor,
    _resolve_convert_config,
    load_config,
)

TOKEN = "sk-" + "Ab1" * 8
EMAIL = "alice@example.com"

PATH_FORMS = [
    "/home/alice/code/x",
    "-home-alice-code-x",
    "C:\\Users\\alice\\proj",
    "/Users/alice/x",
]


@pytest.fixture(autouse=True)
def _env_alice(monkeypatch, tmp_path):
    """Pin every username source to ``alice`` so results are machine-independent."""
    monkeypatch.setenv("USER", "alice")
    monkeypatch.setenv("USERNAME", "alice")
    fake_home = tmp_path / "home" / "alice"
    fake_home.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))


def _config_file(tmp_path: Path, redaction: dict | None = None) -> Path:
    path = tmp_path / "sessions_config.json"
    body = {"redaction": redaction} if redaction is not None else {}
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


# ── defaults ─────────────────────────────────────────────────────────


def test_default_config_disables_username_redaction():
    assert DEFAULT_CONFIG["redaction"]["redact_username"] is False


def test_example_sessions_config_disables_username_redaction():
    shipped = json.loads(DEFAULT_CONFIG_FILE.read_text(encoding="utf-8"))
    assert shipped["redaction"]["redact_username"] is False


@pytest.mark.parametrize(
    "redaction",
    [None, {}, {"real_username": ""}, {"replacement_username": "USER"}],
    ids=["no-section", "empty-section", "empty-real-username", "only-replacement"],
)
def test_load_config_fills_redact_username_false(tmp_path, redaction):
    cfg = load_config(_config_file(tmp_path, redaction))
    assert cfg["redaction"]["redact_username"] is False


def test_resolve_convert_config_fills_redact_username_false(tmp_path):
    cfg = _resolve_convert_config(_config_file(tmp_path, {}))
    assert cfg["redaction"]["redact_username"] is False


# ── core regression: default keeps real paths ───────────────────────


@pytest.mark.parametrize("path", PATH_FORMS)
def test_default_config_keeps_real_home_paths(tmp_path, path):
    redact = Redactor(load_config(_config_file(tmp_path)))
    assert redact(f"cwd {path} done") == f"cwd {path} done"


def test_default_config_still_redacts_tokens_and_emails(tmp_path):
    redact = Redactor(load_config(_config_file(tmp_path)))
    out = redact(f"/home/alice/code/x key={TOKEN} mail={EMAIL}")
    assert "/home/alice/code/x" in out
    assert TOKEN not in out
    assert EMAIL not in out
    assert out.count("<REDACTED>") == 2


def test_extra_patterns_run_with_username_redaction_off(tmp_path):
    cfg_file = _config_file(
        tmp_path, {"redact_username": False, "extra_patterns": [r"SECRET-\d+"]},
    )
    out = Redactor(load_config(cfg_file))("/home/alice/x SECRET-42")
    assert out == "/home/alice/x <REDACTED>"


# ── publish mode ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/home/alice/code/x", "/home/USER/code/x"),
        ("-home-alice-code-x", "-home-USER-code-x"),
        ("C:\\Users\\alice\\proj", "C:\\Users\\USER\\proj"),
        ("/Users/alice/x", "/Users/USER/x"),
    ],
)
def test_redact_username_true_rewrites_home_paths(tmp_path, path, expected):
    redact = Redactor(load_config(_config_file(tmp_path, {"redact_username": True})))
    assert redact(path) == expected


def test_redact_username_true_honors_custom_replacement(tmp_path):
    cfg_file = _config_file(
        tmp_path, {"redact_username": True, "replacement_username": "anon"},
    )
    redact = Redactor(load_config(cfg_file))
    assert redact("/home/alice/code/x -home-alice-y") == "/home/anon/code/x -home-anon-y"


def test_redact_username_true_still_redacts_tokens(tmp_path):
    redact = Redactor(load_config(_config_file(tmp_path, {"redact_username": True})))
    assert redact(f"/home/alice/x {TOKEN}") == "/home/USER/x <REDACTED>"


# ── hand-built dicts (programmatic back-compat) ──────────────────────


@pytest.mark.parametrize(
    ("redaction", "expected"),
    [
        ({"real_username": "alice"}, "/home/USER/code/x"),
        ({"real_username": "alice", "redact_username": True}, "/home/USER/code/x"),
        ({"real_username": "alice", "redact_username": False}, "/home/alice/code/x"),
    ],
    ids=["key-omitted-redacts", "explicit-true", "explicit-false"],
)
def test_hand_built_redactor_config(redaction, expected):
    assert Redactor({"redaction": redaction})("/home/alice/code/x") == expected


# ── end-to-end through convert_all ───────────────────────────────────


def _write_session(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        {
            "type": "user",
            "sessionId": "sess-253",
            "slug": "demo",
            "timestamp": "2026-04-16T10:00:00Z",
            "cwd": "/home/alice/code/proj",
            "entrypoint": "cli",
            "promptSource": "typed",
            "gitBranch": "main",
            "message": {"role": "user", "content": "read the notes"},
        },
        {
            "type": "assistant",
            "sessionId": "sess-253",
            "timestamp": "2026-04-16T10:00:01Z",
            "entrypoint": "cli",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tu-1",
                        "name": "Read",
                        "input": {"file_path": "/home/alice/code/proj/notes.md"},
                    },
                ],
            },
        },
    ]
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


@pytest.mark.parametrize(
    ("redaction", "present", "absent"),
    [
        (None, "/home/alice/code/proj", "/home/USER/"),
        ({"redact_username": True}, "/home/USER/code/proj", "/home/alice/"),
    ],
    ids=["default-keeps-real", "publish-redacts"],
)
def test_convert_all_raw_output_follows_toggle(
    tmp_path, monkeypatch, redaction, present, absent,
):
    home = tmp_path / "home" / "alice"
    store = home / ".claude" / "projects"
    _write_session(store / "-home-alice-code-proj" / "sess.jsonl")
    out_dir = tmp_path / "repo" / "raw" / "sessions"
    monkeypatch.setattr(ClaudeCodeAdapter, "session_store_path", store, raising=False)
    monkeypatch.setattr(c, "REPO_ROOT", tmp_path / "repo")
    c.discover_adapters()

    c.convert_all(
        adapters=["claude_code"],
        out_dir=out_dir,
        state_file=tmp_path / "state.json",
        config_file=_config_file(tmp_path, redaction),
        ignore_file=tmp_path / "no-ignore",
        include_current=True,
    )

    outputs = sorted(out_dir.rglob("*.md"))
    assert len(outputs) == 1
    text = outputs[0].read_text(encoding="utf-8")
    assert present in text
    assert "notes.md" in text
    assert absent not in text


# ── add_doc source label (#141) ──────────────────────────────────────


@pytest.mark.parametrize(
    ("redact_username", "expected"),
    [
        (False, "/home/alice/code/doc.md"),
        (True, "/home/USER/code/doc.md"),
    ],
)
def test_source_path_label_follows_toggle(
    tmp_path, monkeypatch, redact_username, expected,
):
    monkeypatch.setattr(
        "llmwiki.add_doc._resolve_convert_config",
        lambda _cfg: {
            "redaction": {
                "real_username": "alice",
                "replacement_username": "USER",
                "redact_username": redact_username,
            },
        },
    )
    monkeypatch.chdir(tmp_path)
    assert _source_path_label(Path("/home/alice/code/doc.md")) == expected


def test_source_path_label_default_config_keeps_real_path(tmp_path, monkeypatch):
    cfg_file = _config_file(tmp_path)
    monkeypatch.setattr(
        "llmwiki.add_doc._resolve_convert_config",
        lambda _cfg: _resolve_convert_config(cfg_file),
    )
    monkeypatch.chdir(tmp_path)
    assert _source_path_label(Path("/home/alice/code/doc.md")) == "/home/alice/code/doc.md"
