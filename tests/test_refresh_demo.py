"""Change selection and dry-run driver for ``scripts/refresh_demo.py`` (#109)."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load():
    script = REPO / "scripts" / "refresh_demo.py"
    spec = importlib.util.spec_from_file_location("refresh_demo", script)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


refresh = _load()


def test_added_file_plans_add() -> None:
    plan = refresh.plan_from_git("A\tdocs/guide.md\n", "")
    assert plan == [("add", "docs/guide.md", "guide")]


def test_modified_file_is_remove_then_add() -> None:
    plan = refresh.plan_from_git("M\tdocs/guide.md\n", "")
    assert plan == [
        ("remove", "docs/guide.md", "guide"),
        ("add", "docs/guide.md", "guide"),
    ]
    assert [action for action, _path, _slug in plan] == ["remove", "add"]


def test_deleted_file_plans_remove() -> None:
    plan = refresh.plan_from_git("D\tdocs/guide.md\n", "")
    assert plan == [("remove", "docs/guide.md", "guide")]


def test_renamed_file_is_remove_old_then_add_new() -> None:
    plan = refresh.plan_from_git("R100\tdocs/old.md\tdocs/new.md\n", "")
    assert plan == [
        ("remove", "docs/old.md", "old"),
        ("add", "docs/new.md", "new"),
    ]


def test_unchanged_and_empty_inputs_produce_empty_plan() -> None:
    assert refresh.plan_from_git("", "") == []
    assert refresh.plan_from_git("M\tllmwiki/cli.py\n", "") == []


def test_uncommitted_edit_plans_remove_then_add() -> None:
    plan = refresh.plan_from_git("", " M docs/guide.md\n")
    assert plan == [
        ("remove", "docs/guide.md", "guide"),
        ("add", "docs/guide.md", "guide"),
    ]


def test_committed_then_further_edited_is_one_remove_then_add() -> None:
    plan = refresh.plan_from_git("M\tdocs/guide.md\n", " M docs/guide.md\n")
    assert plan == [
        ("remove", "docs/guide.md", "guide"),
        ("add", "docs/guide.md", "guide"),
    ]


def test_no_change_run_produces_empty_plan() -> None:
    assert refresh.plan_from_git("", "") == []


def test_maintainer_docs_and_non_markdown_are_excluded() -> None:
    diff = (
        "M\tdocs/maintainers/README.md\n"
        "A\tdocs/maintainers/surfaces/home.md\n"
        "M\tdocs/demo.gif\n"
        "A\tdocs/getting-started.md\n"
    )
    plan = refresh.plan_from_git(diff, "")
    assert plan == [("add", "docs/getting-started.md", "getting-started")]


def test_nested_path_slug_is_unique() -> None:
    plan = refresh.plan_from_git(
        "A\tdocs/i18n/zh-CN/getting-started.md\nA\tdocs/getting-started.md\n",
        "",
    )
    slugs = {slug for _action, _path, slug in plan}
    assert slugs == {"i18n-zh-cn-getting-started", "getting-started"}


def test_untracked_product_doc_is_add() -> None:
    plan = refresh.plan_from_git("", "?? docs/tutorials/new.md\n")
    assert plan == [("add", "docs/tutorials/new.md", "tutorials-new")]


def test_porcelain_rename() -> None:
    plan = refresh.plan_from_git("", "R  docs/old.md -> docs/new.md\n")
    assert plan == [
        ("remove", "docs/old.md", "old"),
        ("add", "docs/new.md", "new"),
    ]


def test_added_then_deleted_in_working_tree_drops_out() -> None:
    plan = refresh.plan_from_git("A\tdocs/ephemeral.md\n", " D docs/ephemeral.md\n")
    assert plan == []


# ── git fixture / --dry-run ───────────────────────────────────────────────


def _git(repo: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=check,
    )


def _seed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, ["init", "-b", "main"])
    _git(repo, ["config", "user.name", "Test"])
    _git(repo, ["config", "user.email", "test@example.com"])
    _git(repo, ["config", "commit.gpgsign", "false"])
    (repo / "docs" / "maintainers").mkdir(parents=True)
    (repo / "docs" / "guide.md").write_text("# Guide\n\nbody\n", encoding="utf-8")
    (repo / "docs" / "keep.md").write_text("# Keep\n\nbody\n", encoding="utf-8")
    (repo / "docs" / "maintainers" / "note.md").write_text("# Maintainer\n", encoding="utf-8")
    (repo / "demo").mkdir()
    _git(repo, ["add", "docs"])
    _git(repo, ["commit", "-m", "seed"])
    sha = _git(repo, ["rev-parse", "HEAD"]).stdout.strip()
    (repo / "demo" / ".demo-source-rev").write_text(sha + "\n", encoding="utf-8")
    return repo


def _snapshot(repo: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in repo.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            files[path.relative_to(repo).as_posix()] = path.read_text(encoding="utf-8")
    return files


def test_dry_run_no_change_prints_empty_plan_and_writes_nothing(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    before = _snapshot(repo)
    rc = refresh.run_refresh(repo, dry_run=True)
    assert rc == 0
    assert _snapshot(repo) == before


def test_dry_run_added_prints_add(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _seed_repo(tmp_path)
    (repo / "docs" / "new.md").write_text("# New\n", encoding="utf-8")
    _git(repo, ["add", "docs/new.md"])
    _git(repo, ["commit", "-m", "add new"])
    before = _snapshot(repo)
    rc = refresh.run_refresh(repo, dry_run=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert "docs/new.md" in out
    assert "add" in out
    assert "remove" not in out
    assert _snapshot(repo) == before


def test_dry_run_modified_prints_remove_then_add(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _seed_repo(tmp_path)
    (repo / "docs" / "guide.md").write_text("# Guide\n\nedited\n", encoding="utf-8")
    _git(repo, ["add", "docs/guide.md"])
    _git(repo, ["commit", "-m", "edit guide"])
    before = _snapshot(repo)
    rc = refresh.run_refresh(repo, dry_run=True)
    out = capsys.readouterr().out
    assert rc == 0
    remove_at = out.index("remove")
    add_at = out.index("add")
    assert remove_at < add_at
    assert "docs/guide.md" in out
    assert _snapshot(repo) == before


def test_dry_run_deleted_prints_remove(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _seed_repo(tmp_path)
    _git(repo, ["rm", "docs/keep.md"])
    _git(repo, ["commit", "-m", "drop keep"])
    before = _snapshot(repo)
    rc = refresh.run_refresh(repo, dry_run=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert "remove" in out and "docs/keep.md" in out
    assert "add" not in out
    assert _snapshot(repo) == before


def test_dry_run_renamed_prints_remove_old_add_new(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _seed_repo(tmp_path)
    _git(repo, ["mv", "docs/guide.md", "docs/renamed.md"])
    _git(repo, ["commit", "-m", "rename guide"])
    before = _snapshot(repo)
    rc = refresh.run_refresh(repo, dry_run=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert "docs/guide.md" in out
    assert "docs/renamed.md" in out
    assert out.index("remove") < out.index("add")
    assert _snapshot(repo) == before


def test_dry_run_uncommitted_edit_is_picked_up(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _seed_repo(tmp_path)
    (repo / "docs" / "guide.md").write_text("# Guide\n\nworking tree\n", encoding="utf-8")
    before = _snapshot(repo)
    rc = refresh.run_refresh(repo, dry_run=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert "docs/guide.md" in out
    assert "remove" in out and "add" in out
    assert _snapshot(repo) == before


def test_dry_run_ignores_maintainer_docs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _seed_repo(tmp_path)
    (repo / "docs" / "maintainers" / "note.md").write_text("# Changed\n", encoding="utf-8")
    _git(repo, ["add", "docs/maintainers/note.md"])
    _git(repo, ["commit", "-m", "maintainer only"])
    rc = refresh.run_refresh(repo, dry_run=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert "docs/maintainers" not in out
    assert "no changes" in out or "0 action" in out or "(no changes)" in out


def test_dry_run_does_not_write_source_rev(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    recorded = (repo / "demo" / ".demo-source-rev").read_text(encoding="utf-8")
    (repo / "docs" / "guide.md").write_text("# Guide\n\nedited\n", encoding="utf-8")
    refresh.run_refresh(repo, dry_run=True)
    assert (repo / "demo" / ".demo-source-rev").read_text(encoding="utf-8") == recorded


def test_main_dry_run_from_fixture_cwd(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _seed_repo(tmp_path)
    rc = refresh.main(["--dry-run"], cwd=repo)
    out = capsys.readouterr().out
    assert rc == 0
    assert "dry-run" in out
    assert "(no changes)" in out or "0 action" in out or "no changes" in out


