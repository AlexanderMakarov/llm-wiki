"""Unit tests for ``llmwiki.dismissal_ledger`` — dismissals.json SoT (#326 / #418).

# @spec: 326-harvest-discard-reason-surface
# @spec: 418-duplicate-page-review
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki.dismissal_ledger import (
    LEDGER_FILENAME,
    archive_candidates_dir,
    empty_ledger,
    is_keep_distinct_pair,
    iter_dismissals,
    iter_keep_distinct,
    iter_merges,
    ledger_path,
    load_ledger,
    rebuild_ledger_from_archive,
    save_ledger,
    upsert_dismissal,
    upsert_keep_distinct,
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


# ─── keep_distinct (#418) ───────────────────────────────────────────────


def test_empty_ledger_includes_keep_distinct_array():
    """Fresh ledgers carry keep_distinct so coerce/load never invent a missing key."""
    assert empty_ledger()["keep_distinct"] == []


def test_upsert_keep_distinct_creates_and_round_trips(tmp_path: Path):
    """Upserting a keep-distinct pair writes an unordered key and reads back."""
    wiki = tmp_path / "wiki"
    _archive_root(wiki)
    rec = upsert_keep_distinct(
        wiki,
        a="Widget CLI",
        b="wgctl",
        why="different tools",
        decided_at="2026-03-01T12:00:00+00:00",
    )
    lo, hi = sorted((norm_page_key("Widget CLI"), norm_page_key("wgctl")))
    assert rec["key"] == f"{lo}|{hi}"
    assert {rec["a"], rec["b"]} == {"Widget CLI", "wgctl"}
    assert rec["why"] == "different tools"
    assert list(iter_keep_distinct(wiki)) == [rec]
    data = json.loads(ledger_path(wiki).read_text(encoding="utf-8"))
    assert data["keep_distinct"] == [rec]


def test_upsert_keep_distinct_is_idempotent_on_unordered_pair(tmp_path: Path):
    """(a,b) and (b,a) share one key; a second upsert replaces why/decided_at."""
    wiki = tmp_path / "wiki"
    _archive_root(wiki)
    first = upsert_keep_distinct(
        wiki,
        a="AlphaTool",
        b="BetaTool",
        why="old",
        decided_at="2026-01-01T00:00:00+00:00",
    )
    second = upsert_keep_distinct(
        wiki,
        a="BetaTool",
        b="AlphaTool",
        why="new reason",
        decided_at="2026-02-01T00:00:00+00:00",
    )
    rows = list(iter_keep_distinct(wiki))
    assert len(rows) == 1
    assert rows[0]["key"] == first["key"] == second["key"]
    assert rows[0]["why"] == "new reason"
    assert rows[0]["decided_at"] == "2026-02-01T00:00:00+00:00"
    assert is_keep_distinct_pair(wiki, "AlphaTool", "BetaTool")
    assert is_keep_distinct_pair(wiki, "BetaTool", "AlphaTool")


def test_is_keep_distinct_pair_false_for_unknown_or_same_identity(tmp_path: Path):
    """Unknown pairs and same-folded names are never keep-distinct."""
    wiki = tmp_path / "wiki"
    _archive_root(wiki)
    upsert_keep_distinct(wiki, a="Alpha", b="Beta", why="")
    assert not is_keep_distinct_pair(wiki, "Alpha", "Gamma")
    assert not is_keep_distinct_pair(wiki, "Alpha", "alpha")
    assert not is_keep_distinct_pair(wiki, "", "Beta")


def test_upsert_keep_distinct_rejects_same_folded_identity(tmp_path: Path):
    """Cannot record keep-distinct when both sides fold to one page key."""
    wiki = tmp_path / "wiki"
    _archive_root(wiki)
    with pytest.raises(ValueError, match="distinct page identities"):
        upsert_keep_distinct(wiki, a="OpenClaw", b="open-claw")


def test_load_ledger_coerces_missing_keep_distinct_to_empty(tmp_path: Path):
    """Pre-#418 dismissals.json without keep_distinct still loads cleanly."""
    wiki = tmp_path / "wiki"
    path = ledger_path(wiki)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 1, "dismissals": [], "merges": []}) + "\n",
        encoding="utf-8",
    )
    ledger = load_ledger(wiki)
    assert ledger["keep_distinct"] == []


def test_load_ledger_coerces_keep_distinct_key_from_names(tmp_path: Path):
    """A keep_distinct row with empty key derives the stable unordered pair key."""
    wiki = tmp_path / "wiki"
    path = ledger_path(wiki)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "dismissals": [],
                "merges": [],
                "keep_distinct": [
                    {
                        "key": "",
                        "a": "BetaTool",
                        "b": "AlphaTool",
                        "decided_at": "2026-03-01T00:00:00+00:00",
                        "why": "distinct",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    rows = list(iter_keep_distinct(wiki))
    assert len(rows) == 1
    lo, hi = sorted((norm_page_key("AlphaTool"), norm_page_key("BetaTool")))
    assert rows[0]["key"] == f"{lo}|{hi}"
    assert rows[0]["a"] == "AlphaTool"
    assert rows[0]["b"] == "BetaTool"
    # Folded spellings of the same pair still match the derived key.
    assert is_keep_distinct_pair(wiki, "AlphaTool", "BetaTool")
    assert is_keep_distinct_pair(wiki, "beta-tool", "alpha tool")


def test_load_ledger_rejects_non_array_keep_distinct(tmp_path: Path):
    """Malformed keep_distinct (not a list) fails loud like other ledger arrays."""
    wiki = tmp_path / "wiki"
    path = ledger_path(wiki)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "dismissals": [],
                "merges": [],
                "keep_distinct": {"a": "X", "b": "Y"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="keep_distinct must be arrays"):
        load_ledger(wiki)


def test_rebuild_preserves_existing_keep_distinct_rows(tmp_path: Path):
    """Archive rebuild never invents keep_distinct but keeps operator rows."""
    wiki = tmp_path / "wiki"
    archive = _archive_root(wiki)
    _write_stub(
        archive,
        "2026-03-01T12-00-00/Noise.md",
        title="Noise",
        reason="hosting detail, not subject matter",
    )
    upsert_keep_distinct(
        wiki,
        a="Alpha",
        b="Beta",
        why="operator decision",
        decided_at="2026-03-01T12:00:00+00:00",
    )
    before = list(iter_keep_distinct(wiki))
    assert len(before) == 1

    rebuilt = rebuild_ledger_from_archive(wiki)
    assert rebuilt["keep_distinct"] == before
    assert list(iter_keep_distinct(wiki)) == before
    assert len(rebuilt["dismissals"]) == 1
