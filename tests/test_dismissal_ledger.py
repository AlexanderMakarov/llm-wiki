"""Unit tests for ``llmwiki.dismissal_ledger`` — dismissals.json SoT (#326).

# @spec: 326-harvest-discard-reason-surface
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki.dismissal_ledger import (
    LEDGER_FILENAME,
    archive_candidates_dir,
    empty_ledger,
    iter_dismissals,
    iter_merges,
    ledger_path,
    load_ledger,
    rebuild_ledger_from_archive,
    save_ledger,
    upsert_dismissal,
    upsert_merge,
)
from llmwiki.wikilinks import norm_page_key


def _archive_root(wiki: Path) -> Path:
    root = archive_candidates_dir(wiki)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_stub(
    archive: Path,
    rel: str,
    *,
    title: str,
    reason: str | None = None,
    discarded_at: str = "2026-03-01T12:00:00+00:00",
) -> Path:
    """Write an archived candidate stub and optional sibling reason file."""
    path = archive / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{title}"\ntype: entity\n---\n\n# {title}\n',
        encoding="utf-8",
    )
    if reason is not None:
        reason_path = path.with_suffix(".reason.txt")
        reason_path.write_text(
            f"Discarded at: {discarded_at}\n"
            f"Reason: {reason}\n"
            f"Original path: candidates/entities/{title}.md\n",
            encoding="utf-8",
        )
    return path


def test_ledger_path_is_under_archive_candidates(tmp_path: Path):
    """Ledger lives at wiki/archive/candidates/dismissals.json."""
    wiki = tmp_path / "wiki"
    assert ledger_path(wiki) == wiki / "archive" / "candidates" / LEDGER_FILENAME


def test_upsert_dismissal_creates_and_round_trips(tmp_path: Path):
    """Upserting a dismissal writes a versioned ledger that load_ledger reads back."""
    wiki = tmp_path / "wiki"
    _archive_root(wiki)
    rec = upsert_dismissal(
        wiki,
        name="FooBar",
        reason="hosting detail, not subject matter",
        stub="2026-03-01T12-00-00/FooBar.md",
        discarded_at="2026-03-01T12:00:00+00:00",
    )
    assert rec["key"] == norm_page_key("FooBar")
    path = ledger_path(wiki)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert len(data["dismissals"]) == 1
    assert data["dismissals"][0]["reason"] == "hosting detail, not subject matter"
    assert data["merges"] == []
    loaded = list(iter_dismissals(wiki))
    assert loaded == [rec]


def test_upsert_dismissal_replaces_same_key(tmp_path: Path):
    """A second upsert for the same folded key replaces the prior dismissal row."""
    wiki = tmp_path / "wiki"
    _archive_root(wiki)
    upsert_dismissal(wiki, name="ApiClient", reason="old", stub="a/ApiClient.md")
    upsert_dismissal(wiki, name="API Client", reason="new reason", stub="b/ApiClient.md")
    rows = list(iter_dismissals(wiki))
    assert len(rows) == 1
    assert rows[0]["reason"] == "new reason"
    assert rows[0]["name"] == "API Client"


def test_upsert_merge_round_trips(tmp_path: Path):
    """Upserting a merge records into/merged_at/stub without touching dismissals."""
    wiki = tmp_path / "wiki"
    _archive_root(wiki)
    rec = upsert_merge(
        wiki,
        name="OldName",
        into="Survivor",
        stub="2026-04-01T00-00-00/OldName.md",
        merged_at="2026-04-01T00:00:00+00:00",
    )
    assert list(iter_merges(wiki)) == [rec]
    assert list(iter_dismissals(wiki)) == []


def test_upsert_merge_replaces_same_key(tmp_path: Path):
    """A second merge upsert for the same folded key replaces the prior merge row."""
    wiki = tmp_path / "wiki"
    _archive_root(wiki)
    upsert_merge(wiki, name="OldName", into="A", stub="a/OldName.md")
    upsert_merge(wiki, name="old name", into="B", stub="b/OldName.md")
    rows = list(iter_merges(wiki))
    assert len(rows) == 1
    assert rows[0]["into"] == "B"
    assert rows[0]["name"] == "old name"


def test_rebuild_from_fixtures_is_idempotent(tmp_path: Path):
    """rebuild_ledger_from_archive twice yields the same dismissals.json payload."""
    wiki = tmp_path / "wiki"
    archive = _archive_root(wiki)
    _write_stub(
        archive,
        "2026-03-01T12-00-00/Noise.md",
        title="Noise",
        reason="hosting detail, not subject matter",
    )
    _write_stub(
        archive,
        "2026-03-02T12-00-00/Alias.md",
        title="Alias",
        reason="merged into Main",
    )
    first = rebuild_ledger_from_archive(wiki)
    second = rebuild_ledger_from_archive(wiki)
    assert first == second
    assert ledger_path(wiki).read_text(encoding="utf-8") == (
        json.dumps(second, indent=2, ensure_ascii=False) + "\n"
    )


def test_load_missing_ledger_rebuilds_from_reason_files(tmp_path: Path):
    """When dismissals.json is absent, load_ledger imports legacy *.reason.txt stubs."""
    wiki = tmp_path / "wiki"
    archive = _archive_root(wiki)
    _write_stub(
        archive,
        "2026-03-01T12-00-00/Noise.md",
        title="Noise",
        reason="hosting detail, not subject matter",
    )
    _write_stub(
        archive,
        "2026-03-02T12-00-00/Alias.md",
        title="Alias",
        reason="merged into Main",
    )
    assert not ledger_path(wiki).is_file()
    ledger = load_ledger(wiki)
    assert ledger_path(wiki).is_file()
    assert len(ledger["dismissals"]) == 1
    assert ledger["dismissals"][0]["name"] == "Noise"
    assert ledger["dismissals"][0]["reason"] == "hosting detail, not subject matter"
    assert len(ledger["merges"]) == 1
    assert ledger["merges"][0]["into"] == "Main"
    assert ledger["merges"][0]["name"] == "Alias"


def test_load_without_an_archive_writes_nothing(tmp_path: Path):
    """A wiki with no archive has nothing to rebuild, so reading leaves it untouched (#363)."""
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))

    assert load_ledger(wiki) == empty_ledger()
    assert sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*")) == before

    missing = tmp_path / "no-such-vault" / "wiki"
    assert load_ledger(missing) == empty_ledger()
    assert not (tmp_path / "no-such-vault").exists()


def test_rebuild_treats_stub_without_reason_as_empty_dismissal(tmp_path: Path):
    """Archived stubs lacking a sibling reason file become dismissals with empty reason."""
    wiki = tmp_path / "wiki"
    archive = _archive_root(wiki)
    _write_stub(archive, "stamp/Silent.md", title="Silent", reason=None)
    ledger = rebuild_ledger_from_archive(wiki)
    assert len(ledger["dismissals"]) == 1
    assert ledger["dismissals"][0]["reason"] == ""
    assert ledger["merges"] == []


def test_save_ledger_is_atomic_replace(tmp_path: Path):
    """save_ledger replaces dismissals.json without leaving a truncated file behind."""
    wiki = tmp_path / "wiki"
    _archive_root(wiki)
    save_ledger(wiki, empty_ledger())
    path = ledger_path(wiki)
    assert path.read_text(encoding="utf-8").endswith("\n")
    upsert_dismissal(wiki, name="X", stub="s/X.md", reason="r")
    leftovers = list(path.parent.glob(".dismissals-*.tmp"))
    assert leftovers == []


def test_corrupt_ledger_fails_loud(tmp_path: Path):
    """A present but invalid dismissals.json raises instead of silently rebuilding."""
    wiki = tmp_path / "wiki"
    path = ledger_path(wiki)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_ledger(wiki)
