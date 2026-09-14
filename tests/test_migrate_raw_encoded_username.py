"""#56: deterministic raw/ migration for encoded-path username redaction.

Rewrites existing ``raw/sessions/*.md`` in place so ``-Users-<you>-…``
becomes ``-Users-USER-…`` without re-converting from agent stores
(transcripts are often gone after ~30 days) and without touching
``wiki/`` or enqueueing synthesize.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from llmwiki.cli import build_parser

REPO = Path(__file__).resolve().parents[1]


def _load_migrator():
    script = REPO / "scripts" / "migrate_raw_encoded_username.py"
    spec = importlib.util.spec_from_file_location(
        "migrate_raw_encoded_username", script
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SAMPLE = """---
title: "Session: abc — 2026-07-01"
cwd: /Users/USER/.claude/projects/-Users-alice-code-demo
description: "Work in /Users/USER/.claude/projects/-Users-alice-code-demo"
project: demo
---

# Session

Path under store: `/Users/USER/.claude/projects/-Users-alice-code-demo/x`
Also plain: `/Users/alice/code/other`
"""


EXPECTED = """---
title: "Session: abc — 2026-07-01"
cwd: /Users/USER/.claude/projects/-Users-USER-code-demo
description: "Work in /Users/USER/.claude/projects/-Users-USER-code-demo"
project: demo
---

# Session

Path under store: `/Users/USER/.claude/projects/-Users-USER-code-demo/x`
Also plain: `/Users/USER/code/other`
"""


def test_migrate_rewrites_encoded_and_plain_home_paths(tmp_path: Path):
    mod = _load_migrator()
    raw = tmp_path / "raw" / "sessions"
    raw.mkdir(parents=True)
    target = raw / "2026-07-01T12-00-demo-abc.md"
    target.write_text(SAMPLE, encoding="utf-8")
    # Unrelated wiki page must not be touched.
    wiki = tmp_path / "wiki" / "sources"
    wiki.mkdir(parents=True)
    wiki_page = wiki / "demo.md"
    wiki_page.write_text(
        "cwd: /Users/alice/.claude/projects/-Users-alice-code-demo\n",
        encoding="utf-8",
    )

    report = mod.run_migration(
        vault=tmp_path,
        real_username="alice",
        replacement_username="USER",
        dry_run=False,
    )
    assert report["scanned"] == 1
    assert report["rewritten"] == 1
    assert report["unchanged"] == 0
    assert target.read_text(encoding="utf-8") == EXPECTED
    assert "alice" in wiki_page.read_text(encoding="utf-8")


def test_migrate_dry_run_writes_nothing(tmp_path: Path):
    mod = _load_migrator()
    raw = tmp_path / "raw" / "sessions"
    raw.mkdir(parents=True)
    target = raw / "sess.md"
    target.write_text(SAMPLE, encoding="utf-8")

    report = mod.run_migration(
        vault=tmp_path,
        real_username="alice",
        replacement_username="USER",
        dry_run=True,
    )
    assert report["rewritten"] == 1
    assert report["dry_run"] is True
    assert target.read_text(encoding="utf-8") == SAMPLE


def test_migrate_noop_when_already_redacted(tmp_path: Path):
    mod = _load_migrator()
    raw = tmp_path / "raw" / "sessions"
    raw.mkdir(parents=True)
    target = raw / "sess.md"
    target.write_text(EXPECTED, encoding="utf-8")

    report = mod.run_migration(
        vault=tmp_path,
        real_username="alice",
        replacement_username="USER",
        dry_run=False,
    )
    assert report["rewritten"] == 0
    assert report["unchanged"] == 1


def test_migrate_requires_real_username(tmp_path: Path):
    mod = _load_migrator()
    with pytest.raises(ValueError, match="real_username"):
        mod.run_migration(
            vault=tmp_path,
            real_username="",
            replacement_username="USER",
            dry_run=False,
        )


# ─── #253: migrate raw-unredaction (placeholder → real username) ───────────

UNREDACT_SAMPLE = """---
cwd: /home/USER/code/demo
description: "Store /Users/USER/.claude/projects/-Users-USER-code-demo"
---

Set USER=alice then check C:\\Users\\USER\\repo and -home-USER-work.
Env var USER and /opt/USER/bin stay; so does /home/USERS/x.
"""


UNREDACT_EXPECTED = """---
cwd: /home/alice/code/demo
description: "Store /Users/alice/.claude/projects/-Users-alice-code-demo"
---

Set USER=alice then check C:\\Users\\alice\\repo and -home-alice-work.
Env var USER and /opt/USER/bin stay; so does /home/USERS/x.
"""


def _write_session(vault: Path, text: str) -> Path:
    raw = vault / "raw" / "sessions"
    raw.mkdir(parents=True)
    target = raw / "2026-07-01T12-00-demo-abc.md"
    target.write_text(text, encoding="utf-8")
    return target


def test_unredaction_restores_home_and_encoded_paths_only(tmp_path: Path):
    mod = _load_migrator()
    target = _write_session(tmp_path, UNREDACT_SAMPLE)
    report = mod.run_unredaction(
        vault=tmp_path, real_username="alice", replacement_username="USER"
    )
    assert report["rewritten"] == 1
    assert report["direction"] == "unredact"
    assert target.read_text(encoding="utf-8") == UNREDACT_EXPECTED


def test_unredaction_rewrites_typed_placeholder_path_in_prose(tmp_path: Path):
    """A deliberately typed ``/home/USER/…`` path in prose is rewritten too (documented limitation)."""
    mod = _load_migrator()
    target = _write_session(
        tmp_path, "Rule: use placeholders like `/home/USER/project` in docs.\n"
    )
    mod.run_unredaction(
        vault=tmp_path, real_username="alice", replacement_username="USER"
    )
    assert target.read_text(encoding="utf-8") == (
        "Rule: use placeholders like `/home/alice/project` in docs.\n"
    )


def test_unredaction_is_idempotent(tmp_path: Path):
    mod = _load_migrator()
    target = _write_session(tmp_path, UNREDACT_SAMPLE)
    kwargs = {"vault": tmp_path, "real_username": "alice", "replacement_username": "USER"}
    mod.run_unredaction(**kwargs)
    report = mod.run_unredaction(**kwargs)
    assert report["rewritten"] == 0
    assert report["unchanged"] == 1
    assert target.read_text(encoding="utf-8") == UNREDACT_EXPECTED


def test_unredaction_dry_run_writes_nothing(tmp_path: Path):
    mod = _load_migrator()
    target = _write_session(tmp_path, UNREDACT_SAMPLE)
    report = mod.run_unredaction(
        vault=tmp_path, real_username="alice", replacement_username="USER", dry_run=True
    )
    assert report["rewritten"] == 1
    assert target.read_text(encoding="utf-8") == UNREDACT_SAMPLE


def test_unredaction_round_trips_redaction(tmp_path: Path):
    mod = _load_migrator()
    target = _write_session(tmp_path, UNREDACT_EXPECTED)
    kwargs = {"vault": tmp_path, "real_username": "alice", "replacement_username": "USER"}
    mod.run_migration(**kwargs)
    mod.run_unredaction(**kwargs)
    assert target.read_text(encoding="utf-8") == UNREDACT_EXPECTED


@pytest.mark.parametrize(
    ("real", "repl", "match"),
    [("", "USER", "real_username is empty"), ("USER", "USER", "nothing to rewrite")],
)
def test_unredaction_refuses_empty_or_equal_usernames(tmp_path: Path, real, repl, match):
    mod = _load_migrator()
    target = _write_session(tmp_path, UNREDACT_SAMPLE)
    with pytest.raises(ValueError, match=match):
        mod.run_unredaction(vault=tmp_path, real_username=real, replacement_username=repl)
    assert target.read_text(encoding="utf-8") == UNREDACT_SAMPLE


def test_unredaction_cli_refuses_equal_usernames(tmp_path: Path, capsys):
    _write_session(tmp_path, UNREDACT_SAMPLE)
    args = build_parser().parse_args([
        "migrate", "raw-unredaction", "--vault", str(tmp_path),
        "--real-username", "USER", "--replacement-username", "USER",
    ])
    assert args.func(args) == 2
    assert "nothing to rewrite" in capsys.readouterr().err


def test_unredaction_cli_restores_and_notes_config(tmp_path: Path, capsys):
    target = _write_session(tmp_path, UNREDACT_SAMPLE)
    args = build_parser().parse_args([
        "migrate", "raw-unredaction", "--vault", str(tmp_path),
        "--real-username", "alice", "--replacement-username", "USER",
    ])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "USER → alice" in out
    assert target.read_text(encoding="utf-8") == UNREDACT_EXPECTED


def test_unredaction_prints_note_when_config_still_redacts(tmp_path: Path, capsys):
    mod = _load_migrator()
    _write_session(tmp_path, UNREDACT_SAMPLE)
    report = mod.run_unredaction(
        vault=tmp_path, real_username="alice", replacement_username="USER", dry_run=True
    )
    report["config_redact_username"] = True
    mod.print_report(report)
    assert "redact_username is still true" in capsys.readouterr().out
