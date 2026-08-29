"""SessionRef discovery contract (#2) — file wrap + non-file mtime/state."""

from __future__ import annotations

from pathlib import Path

import llmwiki.adapters as adapters_mod
from llmwiki.adapters.base import BaseAdapter, SessionRef, portable_session_key_fragment
from llmwiki.convert import convert_all


class _FileAdapter(BaseAdapter):
    name = "test_file_sess"

    def __init__(self, config=None, *, root: Path | None = None):
        super().__init__(config)
        self._root = root

    @property
    def session_store_path(self):  # type: ignore[override]
        return self._root or Path("/dev/null")

    def discover_sessions(self) -> list[Path]:
        if self._root is None or not self._root.exists():
            return []
        return sorted(self._root.glob("*.jsonl"))


def test_portable_session_key_fragment_under_home(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    f = home / "store" / "a.jsonl"
    f.parent.mkdir()
    f.write_text("{}\n")
    assert portable_session_key_fragment(f) == "store/a.jsonl"


def test_default_discover_session_refs_wraps_files(tmp_path: Path):
    root = tmp_path / "sessions"
    root.mkdir()
    f = root / "one.jsonl"
    f.write_text('{"type":"user","message":{"role":"user","content":"x"}}\n')
    ad = _FileAdapter(root=root)
    refs = ad.discover_session_refs()
    assert len(refs) == 1
    assert refs[0].locator == str(f)
    assert refs[0].mtime == f.stat().st_mtime
    assert refs[0].key  # non-empty portable fragment


def test_convert_non_file_session_ref_without_stat(tmp_path: Path, monkeypatch):
    """DB-row locator must not require path.stat() on a missing file."""
    out = tmp_path / "raw" / "sessions"
    out.mkdir(parents=True)
    state = tmp_path / ".llmwiki-state.json"
    locator = "db://composer/abc-not-a-real-file"
    assert not Path(locator).exists()
    ref = SessionRef(
        key="composer/abc-not-a-real-file",
        mtime=1_700_000_000.0,
        locator=locator,
    )

    class _Bound(BaseAdapter):
        name = "test_db_sess"

        def discover_sessions(self) -> list[Path]:
            return []

        def discover_session_refs(self) -> list[SessionRef]:
            return [ref]

        def derive_project_slug(self, path: Path | str) -> str:
            return "db-proj"

        def load_records(self, path: Path | str) -> list[dict]:
            return [
                {
                    "type": "user",
                    "timestamp": "2026-01-15T12:00:00.000Z",
                    "sessionId": "sess-db-1",
                    "message": {"role": "user", "content": "hello from db row"},
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-01-15T12:00:01.000Z",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "hi"}],
                    },
                },
            ]

    monkeypatch.setitem(adapters_mod.REGISTRY, "test_db_sess", _Bound)

    rc = convert_all(
        out_dir=out,
        state_file=state,
        adapters=["test_db_sess"],
        config_file=tmp_path / "nonexistent.json",
        include_current=True,
    )
    assert rc == 0
    written = list(out.glob("*.md"))
    assert len(written) == 1
    assert "hello from db row" in written[0].read_text()

    rc2 = convert_all(
        out_dir=out,
        state_file=state,
        adapters=["test_db_sess"],
        config_file=tmp_path / "nonexistent.json",
        include_current=True,
    )
    assert rc2 == 0
    text = state.read_text()
    assert "test_db_sess::composer/abc-not-a-real-file" in text
