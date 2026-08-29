"""Cursor IDE adapter (#2) — discover / load / normalize / archived."""

from __future__ import annotations

from pathlib import Path

from llmwiki.adapters.contrib.cursor import CursorAdapter
from llmwiki.adapters.contrib.cursor_slug import cursor_workspace_slug
from tests.fixtures_cursor_ide import make_cursor_ide_db

CID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
B1 = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
B2 = "cccccccc-cccc-cccc-cccc-cccccccccccc"
WS = "aabbccddeeff00112233445566778899"


def _adapter_with_db(tmp_path: Path, composers: list) -> CursorAdapter:
    db = make_cursor_ide_db(tmp_path / "state.vscdb", composers=composers)
    ad = CursorAdapter(config={"adapters": {"cursor": {"global_db": str(db)}}})
    return ad


def test_discover_session_refs_one_per_composer(tmp_path: Path):
    ad = _adapter_with_db(
        tmp_path,
        [
            {
                "composer_id": CID,
                "workspace_id": WS,
                "bubbles": [
                    {"bubble_id": B1, "type": 1, "text": "q"},
                    {"bubble_id": B2, "type": 2, "text": "a"},
                ],
            }
        ],
    )
    refs = ad.discover_session_refs()
    assert len(refs) == 1
    assert refs[0].key == f"composer/{CID}"
    assert refs[0].locator == f"cursor-ide:composer:{CID}"
    assert ad.discover_sessions() == []


def test_load_and_normalize_order_and_archived(tmp_path: Path):
    ad = _adapter_with_db(
        tmp_path,
        [
            {
                "composer_id": CID,
                "workspace_id": WS,
                "is_archived": True,
                "created_at": 1_700_000_000_000,
                "bubbles": [
                    {"bubble_id": B1, "type": 1, "text": "user says hi"},
                    {"bubble_id": B2, "type": 2, "text": "assistant replies"},
                ],
            }
        ],
    )
    ad.discover_session_refs()  # warm cache
    raw = ad.load_records(f"cursor-ide:composer:{CID}")
    assert raw[0]["type"] == "cursor_ide_meta"
    assert raw[0]["sessionId"] == CID
    assert raw[0].get("isArchived") is True
    assert raw[0].get("timestamp")
    norm = ad.normalize_records(raw)
    assert [r["type"] for r in norm] == ["cursor_ide_meta", "user", "assistant"]
    assert norm[1]["message"]["content"] == "user says hi"
    assert norm[2]["message"]["content"][0]["text"] == "assistant replies"


def test_archived_same_composer_identity(tmp_path: Path):
    ad = _adapter_with_db(
        tmp_path,
        [
            {
                "composer_id": CID,
                "is_archived": True,
                "bubbles": [{"bubble_id": B1, "type": 1, "text": "x"}],
            }
        ],
    )
    refs = ad.discover_session_refs()
    assert refs[0].key == f"composer/{CID}"


def test_slug_form_matches_cursor_cli_convention():
    assert cursor_workspace_slug(WS) == "cursor-aabbccddeeff"
    assert cursor_workspace_slug(WS) == f"cursor-{WS[:12]}"


def test_ide_derive_project_slug_uses_workspace_id(tmp_path: Path):
    ad = _adapter_with_db(
        tmp_path,
        [
            {
                "composer_id": CID,
                "workspace_id": WS,
                "bubbles": [{"bubble_id": B1, "type": 1, "text": "x"}],
            }
        ],
    )
    ad.discover_session_refs()
    assert ad.derive_project_slug(f"cursor-ide:composer:{CID}") == cursor_workspace_slug(WS)


def test_headless_subagent(tmp_path: Path):
    ad = _adapter_with_db(
        tmp_path,
        [
            {
                "composer_id": CID,
                "is_subagent": True,
                "bubbles": [{"bubble_id": B1, "type": 1, "text": "spawned"}],
            }
        ],
    )
    ad.discover_session_refs()
    raw = ad.load_records(f"cursor-ide:composer:{CID}")
    assert ad.is_headless_session(raw) is True
    assert ad.is_headless_session([{"type": "user"}]) is False
