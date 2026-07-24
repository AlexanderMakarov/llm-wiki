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
