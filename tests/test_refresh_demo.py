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


def test_synth_argv_scopes_to_added_raw_docs(tmp_path: Path) -> None:
    vault = tmp_path / "demo"
    (vault / "raw" / "docs" / "guide").mkdir(parents=True)
    (vault / "raw" / "docs" / "guide" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (vault / "raw" / "docs" / "other").mkdir(parents=True)
    (vault / "raw" / "docs" / "other" / "other.md").write_text("# Other\n", encoding="utf-8")
    plan = [
        ("remove", "docs/guide.md", "guide"),
        ("add", "docs/guide.md", "guide"),
    ]
    argv = refresh.synth_argv_for_added_docs(vault, plan)
    assert argv is not None
    assert argv[:4] == ["synth", "--vault", str(vault), "--docs-only"]
    assert argv.count("--path") == 1
    assert "raw/docs/guide/guide.md" in argv
    assert "raw/docs/other/other.md" not in argv


def test_synth_argv_none_when_plan_is_remove_only(tmp_path: Path) -> None:
    vault = tmp_path / "demo"
    (vault / "raw" / "docs" / "keep").mkdir(parents=True)
    (vault / "raw" / "docs" / "keep" / "keep.md").write_text("# Keep\n", encoding="utf-8")
    plan = [("remove", "docs/keep.md", "keep")]
    assert refresh.synth_argv_for_added_docs(vault, plan) is None


def test_synth_argv_none_when_added_slug_has_no_raw_yet(tmp_path: Path) -> None:
    vault = tmp_path / "demo"
    vault.mkdir()
    plan = [("add", "docs/guide.md", "guide")]
    assert refresh.synth_argv_for_added_docs(vault, plan) is None


def test_missing_wiki_for_doc_slugs_reports_uncovered_raw(tmp_path: Path) -> None:
    vault = tmp_path / "demo"
    raw_dir = vault / "raw" / "docs" / "guide"
    raw_dir.mkdir(parents=True)
    (raw_dir / "guide.md").write_text("# Guide\n", encoding="utf-8")
    gaps = refresh.missing_wiki_for_doc_slugs(vault, ["guide"])
    assert gaps == ["raw/docs/guide/guide.md"]


def test_missing_wiki_for_doc_slugs_accepts_dated_wiki_stem(tmp_path: Path) -> None:
    vault = tmp_path / "demo"
    raw_dir = vault / "raw" / "docs" / "guide"
    wiki_dir = vault / "wiki" / "sources" / "guide"
    raw_dir.mkdir(parents=True)
    wiki_dir.mkdir(parents=True)
    (raw_dir / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (wiki_dir / "2026-09-07-guide.md").write_text("# Guide\n", encoding="utf-8")
    assert refresh.missing_wiki_for_doc_slugs(vault, ["guide"]) == []


def test_run_refresh_fails_when_synth_leaves_wiki_gaps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Incomplete synth must not advance the pin (lint alone is not enough)."""
    repo = _seed_repo(tmp_path)
    (repo / "docs" / "guide.md").write_text("# Guide\n\nedited\n", encoding="utf-8")
    _git(repo, ["add", "docs/guide.md"])
    _git(repo, ["commit", "-m", "edit guide"])
    pin_before = (repo / "demo" / ".demo-source-rev").read_text(encoding="utf-8")

    def fake_run(_exe: str, _repo: Path, argv: list[str]):
        if argv and argv[0] == "add":
            slug = argv[argv.index("--project") + 1]
            dest = repo / "demo" / "raw" / "docs" / slug
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "guide.md").write_text("# Guide\n", encoding="utf-8")
        # synth succeeds but writes no wiki pages — the coverage gate must catch it
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(refresh, "_run_llmwiki", fake_run)
    assert refresh.run_refresh(repo, dry_run=False) == 1
    assert (repo / "demo" / ".demo-source-rev").read_text(encoding="utf-8") == pin_before


def test_run_refresh_passes_path_scoped_synth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real refresh must not call vault-wide ``synth --docs-only`` without ``--path``."""
    repo = _seed_repo(tmp_path)
    (repo / "docs" / "guide.md").write_text("# Guide\n\nedited\n", encoding="utf-8")
    _git(repo, ["add", "docs/guide.md"])
    _git(repo, ["commit", "-m", "edit guide"])

    calls: list[list[str]] = []

    def fake_run_seeded(_exe: str, _repo: Path, argv: list[str]):
        calls.append(list(argv))
        if argv and argv[0] == "add":
            # `--project <slug>` is the last flag pair in refresh_demo's add argv.
            slug = argv[argv.index("--project") + 1]
            dest = repo / "demo" / "raw" / "docs" / slug
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "guide.md").write_text("# Guide\n", encoding="utf-8")
        if argv and argv[0] == "synth" and "--check" not in argv:
            # Coverage gate after synth needs a wiki page per added raw doc.
            slug = "guide"
            raw = repo / "demo" / "raw" / "docs" / slug / "guide.md"
            wiki_dir = repo / "demo" / "wiki" / "sources" / slug
            wiki_dir.mkdir(parents=True, exist_ok=True)
            rel = raw.relative_to(repo / "demo").as_posix()
            (wiki_dir / "2026-09-07-guide.md").write_text(
                f"---\nsource_file: {rel}\n---\n# Guide\n",
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(refresh, "_run_llmwiki", fake_run_seeded)
    rc = refresh.run_refresh(repo, dry_run=False)
    assert rc == 0
    synth_calls = [c for c in calls if c[:1] == ["synth"] and "--check" not in c]
    assert len(synth_calls) == 1
    synth = synth_calls[0]
    assert "--docs-only" in synth
    assert "--path" in synth
    assert "raw/docs/guide/guide.md" in synth
    # Must not be the old vault-wide form: synth --vault … --docs-only with no --path.
    assert synth != ["synth", "--vault", str(repo / "demo"), "--docs-only"]


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


