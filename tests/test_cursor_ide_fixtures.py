"""Smoke test for synthetic Cursor IDE DB helper."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from tests.fixtures_cursor_ide import make_cursor_ide_db


def test_make_cursor_ide_db_shape(tmp_path: Path):
    db = make_cursor_ide_db(
        tmp_path / "state.vscdb",
        composers=[
            {
                "composer_id": "11111111-1111-1111-1111-111111111111",
                "workspace_id": "aabbccddeeff00112233445566778899",
                "is_archived": True,
                "is_subagent": False,
                "bubbles": [
                    {"bubble_id": "22222222-2222-2222-2222-222222222222", "type": 1, "text": "hi"},
                    {"bubble_id": "33333333-3333-3333-3333-333333333333", "type": 2, "text": "hello"},
                ],
            }
        ],
    )
    con = sqlite3.connect(db)
    n_comp = con.execute(
        "SELECT COUNT(*) FROM cursorDiskKV WHERE key LIKE 'composerData:%'"
    ).fetchone()[0]
    n_bub = con.execute(
        "SELECT COUNT(*) FROM cursorDiskKV WHERE key LIKE 'bubbleId:%'"
    ).fetchone()[0]
    arch, sub = con.execute(
        "SELECT isArchived, isSubagent FROM composerHeaders"
    ).fetchone()
    assert n_comp == 1 and n_bub == 2
    assert arch == 1 and sub == 0
    raw = con.execute(
        "SELECT value FROM cursorDiskKV WHERE key LIKE 'composerData:%'"
    ).fetchone()[0]
    meta = json.loads(raw)
    assert len(meta["conversation"]) == 2
    con.close()
