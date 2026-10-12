"""``llmwiki migrate dismissal-ledger`` — rebuild dismissals.json (#326).

# @spec: 326-harvest-discard-reason-surface
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki.cli import _MIGRATIONS, build_parser
from llmwiki.dismissal_ledger import (
    LEDGER_FILENAME,
    archive_candidates_dir,
    ledger_path,
)
from llmwiki.migrate_dismissal_ledger import print_report, run_migration


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    return vault


def _write_stub(
    archive: Path,
    rel: str,
    *,
    title: str,
    reason: str | None = None,
    discarded_at: str = "2026-03-01T12:00:00+00:00",
) -> Path:
    path = archive / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{title}"\ntype: entity\n---\n\n# {title}\n',
        encoding="utf-8",
    )
    if reason is not None:
        path.with_suffix(".reason.txt").write_text(
            f"Discarded at: {discarded_at}\n"
            f"Reason: {reason}\n"
            f"Original path: candidates/entities/{title}.md\n",
            encoding="utf-8",
        )
    return path


def test_migrate_list_includes_dismissal_ledger(capsys) -> None:
    """Catalog lists the new migration name. # @layer: unit"""
    args = build_parser().parse_args(["migrate", "--list"])
    assert args.func(args) == 0
    assert "dismissal-ledger" in capsys.readouterr().out
    assert "dismissal-ledger" in {name for name, *_ in _MIGRATIONS}


def test_cli_requires_a_vault() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["migrate", "dismissal-ledger"])


def test_dry_run_imports_nothing(tmp_path: Path, capsys) -> None:
    """Dry-run reports dismissals/merges but leaves dismissals.json absent."""
    vault = _vault(tmp_path)
    wiki = vault / "wiki"
    archive = archive_candidates_dir(wiki)
    archive.mkdir(parents=True)
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

    args = build_parser().parse_args(
        ["migrate", "dismissal-ledger", "--vault", str(vault), "--dry-run"]
    )
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "dismissals:        1" in out
    assert "merges:            1" in out
    assert "dry run: nothing was written" in out
    assert not ledger_path(wiki).is_file()


def test_apply_writes_ledger_and_second_run_is_noop(tmp_path: Path, capsys) -> None:
    """Apply materialises dismissals.json; a second apply reports unchanged."""
    vault = _vault(tmp_path)
    wiki = vault / "wiki"
    archive = archive_candidates_dir(wiki)
    archive.mkdir(parents=True)
    _write_stub(
        archive,
        "stamp/Noise.md",
        title="Noise",
        reason="hosting detail, not subject matter",
    )

    args = build_parser().parse_args(
        ["migrate", "dismissal-ledger", "--vault", str(vault)]
    )
    assert args.func(args) == 0
    path = ledger_path(wiki)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert len(data["dismissals"]) == 1
    assert data["dismissals"][0]["name"] == "Noise"
    first = path.read_text(encoding="utf-8")
    capsys.readouterr()

    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "unchanged" in out
    assert path.read_text(encoding="utf-8") == first


def test_run_migration_module_dry_run_matches_cli(tmp_path: Path) -> None:
    """Module-level dry-run agrees with the apply payload without writing."""
    vault = _vault(tmp_path)
    wiki = vault / "wiki"
    archive = archive_candidates_dir(wiki)
    archive.mkdir(parents=True)
    _write_stub(archive, "s/Silent.md", title="Silent", reason=None)

    dry = run_migration(vault=vault, dry_run=True)
    assert dry["dismissals"] == 1
    assert dry["merges"] == 0
    assert dry["changed"] is True
    assert not ledger_path(wiki).is_file()

    applied = run_migration(vault=vault, dry_run=False)
    assert applied["changed"] is True
    assert ledger_path(wiki).name == LEDGER_FILENAME
    assert ledger_path(wiki).is_file()

    again = run_migration(vault=vault, dry_run=False)
    assert again["changed"] is False
    assert again["ledger_existed"] is True


def test_print_report_aborted(capsys) -> None:
    print_report({
        "vault": "/tmp/vault",
        "wiki_dir": "/tmp/vault/wiki",
        "ledger_path": "/tmp/vault/wiki/archive/candidates/dismissals.json",
        "dry_run": False,
        "dismissals": 0,
        "merges": 0,
        "ledger_existed": False,
        "changed": False,
        "errors": ["missing wiki dir: /tmp/vault/wiki"],
        "aborted": True,
    })
    out = capsys.readouterr().out
    assert "nothing was written" in out
    assert "missing wiki dir" in out
