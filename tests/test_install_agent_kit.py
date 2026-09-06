"""install-agent-kit copies packaged commands and skills into --dest (#109).

# @layer: unit
# @spec: 008-make-product-explain-itself
# @regression
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from llmwiki import PACKAGE_ROOT, REPO_ROOT, __version__, install_agent_kit
from llmwiki.agent_kit import COMMANDS_DIR, RETIRED_PATHS, SKILLS_DIR
from llmwiki.cli import build_parser
from llmwiki.install_agent_kit import MANIFEST_NAME, kit_files, run_install

KIT_COMMAND = "wiki-sync.md"
KIT_SKILL = Path("llmwiki-sync") / "SKILL.md"


def _snapshot(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# ─── Kit on disk ──────────────────────────────────────────────────────


def test_kit_ships_slash_commands_and_skills() -> None:
    assert COMMANDS_DIR.is_dir()
    assert (COMMANDS_DIR / KIT_COMMAND).is_file()
    assert not (COMMANDS_DIR / "wiki-serve.md").exists()
    assert (SKILLS_DIR / KIT_SKILL).is_file()
    assert (SKILLS_DIR / "wiki-all" / "SKILL.md").is_file()
    assert not (SKILLS_DIR / "wiki-add").exists()
    names = {rel for rel, _src in kit_files()}
    assert f"commands/{KIT_COMMAND}" in names
    assert f"skills/{KIT_SKILL.as_posix()}" in names
    assert not any(rel.startswith("skills/docs-that-work") for rel in names)


def test_contributor_commands_stay_in_dot_claude() -> None:
    contrib = REPO_ROOT / ".claude" / "commands"
    assert (contrib / "fix-bug.md").is_file()
    assert (contrib / "maintainer.md").is_file()
    assert not (contrib / "wiki-sync.md").exists()
    skills = REPO_ROOT / ".claude" / "skills"
    assert (skills / "docs-that-work" / "SKILL.md").is_file()
    assert not (skills / "llmwiki-sync").exists()


# ─── Writes ───────────────────────────────────────────────────────────


def test_install_writes_commands_and_skills(tmp_path: Path) -> None:
    dest = tmp_path / "agent"
    report = run_install(dest=dest)

    assert report["errors"] == []
    assert report["changed"] is True
    assert report["backed_up"] == []
    assert report["unchanged"] == []
    written = set(report["written"])
    assert f"commands/{KIT_COMMAND}" in written
    assert f"skills/{KIT_SKILL.as_posix()}" in written
    assert (dest / "commands" / KIT_COMMAND).is_file()
    assert (dest / "skills" / KIT_SKILL).is_file()
    assert (dest / "commands" / KIT_COMMAND).read_bytes() == (
        COMMANDS_DIR / KIT_COMMAND
    ).read_bytes()


def test_cli_writes_to_dest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    dest = tmp_path / "claude"
    args = build_parser().parse_args(
        ["install-agent-kit", "--dest", str(dest)]
    )

    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert f"commands/{KIT_COMMAND}" in out
    assert "wrote" in out
    assert (dest / "commands" / KIT_COMMAND).is_file()
    assert (dest / "skills" / "wiki-all" / "SKILL.md").is_file()


def test_cli_requires_dest() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["install-agent-kit"])


# ─── Conflict / identical / dry-run ───────────────────────────────────


def test_conflicting_file_writes_bak_and_report(tmp_path: Path) -> None:
    dest = tmp_path / "agent"
    target = dest / "commands" / KIT_COMMAND
    target.parent.mkdir(parents=True)
    target.write_text("user customisation\n", encoding="utf-8")

    report = run_install(dest=dest)

    assert f"commands/{KIT_COMMAND}.bak" in report["backed_up"]
    assert f"commands/{KIT_COMMAND}" in report["written"]
    bak = dest / "commands" / f"{KIT_COMMAND}.bak"
    assert bak.is_file()
    assert bak.read_text(encoding="utf-8") == "user customisation\n"
    assert target.read_bytes() == (COMMANDS_DIR / KIT_COMMAND).read_bytes()


def test_cli_conflict_reports_bak(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "agent"
    target = dest / "commands" / KIT_COMMAND
    target.parent.mkdir(parents=True)
    target.write_text("custom\n", encoding="utf-8")
    args = build_parser().parse_args(
        ["install-agent-kit", "--dest", str(dest)]
    )

    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "backup" in out
    assert f"commands/{KIT_COMMAND}.bak" in out
    assert (dest / "commands" / f"{KIT_COMMAND}.bak").is_file()


def test_identical_file_is_a_noop(tmp_path: Path) -> None:
    dest = tmp_path / "agent"
    first = run_install(dest=dest)
    assert first["written"]
    before = _snapshot(dest)

    report = run_install(dest=dest)

    assert report["written"] == []
    assert report["backed_up"] == []
    assert report["changed"] is False
    assert f"commands/{KIT_COMMAND}" in report["unchanged"]
    assert _snapshot(dest) == before
    assert not list(dest.rglob("*.bak"))


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    dest = tmp_path / "agent"
    report = run_install(dest=dest, dry_run=True)

    assert report["dry_run"] is True
    assert report["written"]
    assert not dest.exists()
    assert report["errors"] == []


def test_cli_dry_run_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "agent"
    args = build_parser().parse_args(
        ["install-agent-kit", "--dest", str(dest), "--dry-run"]
    )

    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "[dry-run]" in out
    assert f"commands/{KIT_COMMAND}" in out
    assert not dest.exists()


def test_dry_run_still_reports_a_conflict(tmp_path: Path) -> None:
    dest = tmp_path / "agent"
    target = dest / "commands" / KIT_COMMAND
    target.parent.mkdir(parents=True)
    original = b"keep me\n"
    target.write_bytes(original)

    report = run_install(dest=dest, dry_run=True)

    assert f"commands/{KIT_COMMAND}.bak" in report["backed_up"]
    assert f"commands/{KIT_COMMAND}" in report["written"]
    assert target.read_bytes() == original
    assert not (dest / "commands" / f"{KIT_COMMAND}.bak").exists()


# ─── Distribution content ─────────────────────────────────────────────


def _build_wheel(dist_dir: Path) -> Path:
    """Build a wheel of this checkout. Prefer ``python -m build``.

    The pip fallback must use build isolation: CI's pytest env does not
    install setuptools, so ``--no-build-isolation`` fails with
    ``Cannot import 'setuptools.build_meta'``. Isolation lets pip fetch
    the backend named in ``pyproject.toml``.
    """
    dist_dir.mkdir(parents=True, exist_ok=True)
    build_cmd = [
        sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir),
    ]
    pip_cmd = [
        sys.executable, "-m", "pip", "wheel", "--no-deps",
        "-w", str(dist_dir), str(REPO_ROOT),
    ]
    proc = subprocess.run(
        build_cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        proc = subprocess.run(
            pip_cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        )
    assert proc.returncode == 0, (
        "wheel build failed:\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    wheels = sorted(dist_dir.glob("*.whl"))
    assert wheels, f"no wheel produced under {dist_dir}"
    return wheels[-1]


def test_wheel_contains_agent_kit_commands_and_skills(tmp_path: Path) -> None:
    # @regression
    """A built wheel must carry the kit — pyproject.toml inspection is not enough."""
    wheel = _build_wheel(tmp_path / "dist")
    with zipfile.ZipFile(wheel) as zf:
        names = set(zf.namelist())
    assert "llmwiki/agent_kit/commands/wiki-sync.md" in names
    assert "llmwiki/agent_kit/commands/wiki-ingest.md" in names
    assert "llmwiki/agent_kit/commands/wiki-query.md" in names
    assert "llmwiki/agent_kit/commands/wiki-all.md" in names
    assert "llmwiki/agent_kit/skills/llmwiki-sync/SKILL.md" in names
    assert "llmwiki/agent_kit/skills/llmwiki-ingest/SKILL.md" in names
    assert "llmwiki/agent_kit/skills/llmwiki-query/SKILL.md" in names
    assert "llmwiki/agent_kit/skills/wiki-all/SKILL.md" in names
    assert "llmwiki/agent_kit/commands/wiki-serve.md" not in names
    assert not any("docs-that-work" in n for n in names)
    assert not any(n.startswith("llmwiki/agent_kit/") and n.endswith("wiki-add/SKILL.md") for n in names)


def test_package_data_declares_agent_kit_glob() -> None:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "agent_kit/**/*.md" in text
    assert (PACKAGE_ROOT / "agent_kit" / "commands" / KIT_COMMAND).is_file()


# ─── Pruning retired and dropped paths (#214) ─────────────────────────


RETIRED_COMMAND = "commands/wiki-export-marp.md"
KIT_RELIC = b"# /wiki-export-marp\n\nA revision the kit once shipped.\n"


def _read_manifest(dest: Path) -> dict[str, object]:
    return json.loads((dest / MANIFEST_NAME).read_text(encoding="utf-8"))


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@pytest.fixture
def shipped_relic(monkeypatch: pytest.MonkeyPatch) -> bytes:
    """Treat ``KIT_RELIC`` as a revision the package shipped at RETIRED_COMMAND."""
    monkeypatch.setattr(
        install_agent_kit,
        "RETIRED_PATHS",
        {RETIRED_COMMAND: frozenset({_digest(KIT_RELIC)})},
    )
    return KIT_RELIC


def test_retired_paths_are_not_shipped_by_the_kit() -> None:
    names = {rel for rel, _src in kit_files()}
    assert RETIRED_PATHS
    assert not (names & set(RETIRED_PATHS))


def test_every_retired_path_carries_hex_digests() -> None:
    """The retired list is provenance, so each entry must name real content."""
    for rel, digests in RETIRED_PATHS.items():
        assert rel.startswith(("commands/", "skills/")), rel
        assert digests, rel
        for value in digests:
            assert len(value) == 64, (rel, value)
            assert set(value) <= set("0123456789abcdef"), (rel, value)


def test_retired_command_we_wrote_is_pruned_without_a_backup(
    tmp_path: Path, shipped_relic: bytes
) -> None:
    dest = tmp_path / "agent"
    run_install(dest=dest)
    stale = dest / RETIRED_COMMAND
    stale.write_bytes(shipped_relic)

    report = run_install(dest=dest)

    assert report["errors"] == []
    assert report["pruned"] == [RETIRED_COMMAND]
    assert report["kept"] == []
    assert report["changed"] is True
    assert not stale.exists()
    assert not (dest / f"{RETIRED_COMMAND}.bak").exists()
    assert not list(dest.rglob("*.bak"))


def test_users_own_file_at_a_retired_name_survives_and_is_reported(
    tmp_path: Path,
) -> None:
    """B2: name collision is not provenance — an unknown digest is left alone."""
    dest = tmp_path / "agent"
    mine = dest / RETIRED_COMMAND
    mine.parent.mkdir(parents=True)
    mine.write_text("MY OWN COMMAND, never installed by llmwiki\n", encoding="utf-8")

    report = run_install(dest=dest)

    assert report["pruned"] == []
    assert mine.is_file()
    assert mine.read_text(encoding="utf-8").startswith("MY OWN COMMAND")
    assert report["kept"] == [
        f"{RETIRED_COMMAND}: retired, but modified — left in place"
    ]
    assert not list(dest.rglob("*.bak"))


def test_customised_retired_command_is_kept(
    tmp_path: Path, shipped_relic: bytes
) -> None:
    dest = tmp_path / "agent"
    run_install(dest=dest)
    stale = dest / RETIRED_COMMAND
    stale.write_bytes(shipped_relic + b"\nmy own extra step\n")

    report = run_install(dest=dest)

    assert report["pruned"] == []
    assert stale.is_file()
    assert any("left in place" in note for note in report["kept"])


def test_user_own_command_is_never_touched(tmp_path: Path) -> None:
    dest = tmp_path / "agent"
    run_install(dest=dest)
    mine = dest / "commands" / "my-custom.md"
    mine.write_text("mine\n", encoding="utf-8")

    report = run_install(dest=dest)

    assert report["pruned"] == []
    assert report["kept"] == []
    assert mine.read_text(encoding="utf-8") == "mine\n"
    assert not (dest / "commands" / "my-custom.md.bak").exists()


def _record(dest: Path, rel: str, payload: bytes) -> None:
    """Add ``rel`` to the manifest with the digest of ``payload``."""
    manifest = _read_manifest(dest)
    manifest["paths"] = {**manifest["paths"], rel: _digest(payload)}
    (dest / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")


def test_manifest_path_dropped_from_kit_is_pruned(tmp_path: Path) -> None:
    dest = tmp_path / "agent"
    run_install(dest=dest)
    dropped = dest / "commands" / "wiki-gone.md"
    payload = b"dropped\n"
    dropped.write_bytes(payload)
    _record(dest, "commands/wiki-gone.md", payload)

    report = run_install(dest=dest)

    assert report["pruned"] == ["commands/wiki-gone.md"]
    assert not dropped.exists()
    assert not (dest / "commands" / "wiki-gone.md.bak").exists()
    assert "commands/wiki-gone.md" not in _read_manifest(dest)["paths"]


def test_manifest_path_modified_since_install_is_not_pruned(tmp_path: Path) -> None:
    dest = tmp_path / "agent"
    run_install(dest=dest)
    dropped = dest / "commands" / "wiki-gone.md"
    dropped.write_bytes(b"as installed\n")
    _record(dest, "commands/wiki-gone.md", b"as installed\n")
    dropped.write_bytes(b"as installed\nplus my edit\n")

    report = run_install(dest=dest)

    assert report["pruned"] == []
    assert dropped.read_bytes() == b"as installed\nplus my edit\n"
    assert report["kept"] == [
        "commands/wiki-gone.md: no longer shipped, but modified — left in place"
    ]


def test_old_list_shape_manifest_prunes_nothing(tmp_path: Path) -> None:
    """A pre-digest manifest records no provenance, so it authorises no delete."""
    dest = tmp_path / "agent"
    run_install(dest=dest)
    dropped = dest / "commands" / "wiki-gone.md"
    dropped.write_bytes(b"dropped\n")
    legacy = {"version": "1.0.0", "paths": ["commands/wiki-gone.md"]}
    (dest / MANIFEST_NAME).write_text(json.dumps(legacy), encoding="utf-8")

    report = run_install(dest=dest)

    assert report["errors"] == []
    assert report["pruned"] == []
    assert report["kept"] == []
    assert dropped.is_file()


def test_dry_run_reports_prune_but_deletes_nothing(
    tmp_path: Path, shipped_relic: bytes
) -> None:
    dest = tmp_path / "agent"
    run_install(dest=dest)
    stale = dest / RETIRED_COMMAND
    stale.write_bytes(shipped_relic)
    before = _snapshot(dest)

    report = run_install(dest=dest, dry_run=True)

    assert report["pruned"] == [RETIRED_COMMAND]
    assert stale.read_bytes() == shipped_relic
    assert not (dest / f"{RETIRED_COMMAND}.bak").exists()
    assert _snapshot(dest) == before


def test_cli_reports_pruned_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], shipped_relic: bytes
) -> None:
    dest = tmp_path / "agent"
    run_install(dest=dest)
    (dest / RETIRED_COMMAND).write_bytes(shipped_relic)
    capsys.readouterr()
    args = build_parser().parse_args(["install-agent-kit", "--dest", str(dest)])

    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert f"pruned    {RETIRED_COMMAND}" in out
    assert "pruned:    1" in out


def test_cli_reports_kept_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "agent"
    mine = dest / RETIRED_COMMAND
    mine.parent.mkdir(parents=True)
    mine.write_text("mine\n", encoding="utf-8")
    capsys.readouterr()
    args = build_parser().parse_args(["install-agent-kit", "--dest", str(dest)])

    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "kept      " in out
    assert "left in place" in out
    assert mine.is_file()


def test_second_install_prunes_and_writes_nothing(tmp_path: Path) -> None:
    dest = tmp_path / "agent"
    run_install(dest=dest)
    before = _snapshot(dest)

    report = run_install(dest=dest)

    assert report["written"] == []
    assert report["pruned"] == []
    assert report["backed_up"] == []
    assert report["changed"] is False
    assert _snapshot(dest) == before


@pytest.mark.parametrize(
    "body",
    [
        "",
        "not json at all",
        "[]",
        '{"paths": "commands/x.md"}',
        '{"paths": [7]}',
        '{"paths": ["commands/wiki-gone.md"]}',
        '{"paths": {"commands/a\u0000b.md": "0"}}',
        '{"paths": {"commands/wiki-gone.md": 7}}',
    ],
)
def test_broken_manifest_does_not_crash_or_over_prune(
    tmp_path: Path, body: str, shipped_relic: bytes
) -> None:
    dest = tmp_path / "agent"
    run_install(dest=dest)
    keep = dest / "commands" / "my-custom.md"
    keep.write_text("mine\n", encoding="utf-8")
    (dest / RETIRED_COMMAND).write_bytes(shipped_relic)
    (dest / MANIFEST_NAME).write_text(body, encoding="utf-8")

    report = run_install(dest=dest)

    assert report["errors"] == []
    assert report["pruned"] == [RETIRED_COMMAND]
    assert keep.is_file()


def test_missing_manifest_prunes_only_retired_paths(
    tmp_path: Path, shipped_relic: bytes
) -> None:
    dest = tmp_path / "agent"
    run_install(dest=dest)
    (dest / MANIFEST_NAME).unlink()
    keep = dest / "commands" / "my-custom.md"
    keep.write_text("mine\n", encoding="utf-8")
    (dest / RETIRED_COMMAND).write_bytes(shipped_relic)

    report = run_install(dest=dest)

    assert report["errors"] == []
    assert report["pruned"] == [RETIRED_COMMAND]
    assert keep.is_file()


def test_manifest_path_traversal_entries_delete_nothing(tmp_path: Path) -> None:
    dest = tmp_path / "agent"
    outside = tmp_path / "evil.md"
    payload = b"outside the dest\n"
    outside.write_bytes(payload)
    run_install(dest=dest)
    manifest = _read_manifest(dest)
    manifest["paths"] = {
        rel: _digest(payload)
        for rel in (
            "commands/../../evil.md",
            "../evil.md",
            str(outside),
            "/etc/passwd",
            "notes/elsewhere.md",
            "..",
        )
    }
    (dest / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")

    report = run_install(dest=dest)

    assert report["pruned"] == []
    assert report["errors"] == []
    assert outside.read_bytes() == payload
    assert not list(tmp_path.glob("*.bak"))


def test_manifest_records_a_digest_per_installed_path(tmp_path: Path) -> None:
    dest = tmp_path / "agent"
    run_install(dest=dest)

    manifest = _read_manifest(dest)
    assert manifest["version"] == __version__
    paths = manifest["paths"]
    assert isinstance(paths, dict)
    assert sorted(paths) == sorted(rel for rel, _src in kit_files())
    assert f"commands/{KIT_COMMAND}" in paths
    for rel, src in kit_files():
        assert paths[rel] == _digest(src.read_bytes())
    assert MANIFEST_NAME not in {rel for rel, _src in kit_files()}
    assert not (dest / "commands" / MANIFEST_NAME).exists()


def test_manifest_records_only_what_landed(tmp_path: Path) -> None:
    """A file that could not be written is neither manifested nor prunable later."""
    dest = tmp_path / "agent"
    blocked = dest / "commands" / KIT_COMMAND
    blocked.mkdir(parents=True)

    report = run_install(dest=dest)

    assert any(rel.startswith(f"commands/{KIT_COMMAND}") for rel in report["errors"])
    paths = _read_manifest(dest)["paths"]
    assert f"commands/{KIT_COMMAND}" not in paths
    assert f"skills/{KIT_SKILL.as_posix()}" in paths


def test_dry_run_writes_no_manifest(tmp_path: Path) -> None:
    dest = tmp_path / "agent"

    run_install(dest=dest, dry_run=True)

    assert not (dest / MANIFEST_NAME).exists()
