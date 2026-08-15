"""install-agent-kit copies packaged commands and skills into --dest (#109).

# @layer: unit
# @spec: 008-make-product-explain-itself
# @regression
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from llmwiki import PACKAGE_ROOT, REPO_ROOT
from llmwiki.agent_kit import COMMANDS_DIR, SKILLS_DIR
from llmwiki.cli import build_parser
from llmwiki.install_agent_kit import kit_files, run_install

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
