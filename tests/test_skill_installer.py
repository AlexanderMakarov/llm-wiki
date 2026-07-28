"""Tests for multi-agent skill installer (v1.0, #160)."""

from __future__ import annotations

from pathlib import Path

from llmwiki.skill_installer import (
    AGENT_TARGETS,
    install_all,
    install_skill,
    list_installed,
    list_targets,
)


def _seed_source(tmp_path: Path) -> Path:
    """Create a fake .claude/skills/ source with 2 skills."""
    src = tmp_path / ".claude" / "skills"
    src.mkdir(parents=True)
    (src / "skill1").mkdir()
    (src / "skill1" / "SKILL.md").write_text(
        "---\nname: skill1\ndescription: test\n---\n", encoding="utf-8"
    )
    (src / "skill2").mkdir()
    (src / "skill2" / "SKILL.md").write_text(
        "---\nname: skill2\ndescription: test\n---\n", encoding="utf-8"
    )
    # Non-skill (no SKILL.md) — should be skipped
    (src / "not-a-skill").mkdir()
    (src / "not-a-skill" / "README.md").write_text("not a skill\n", encoding="utf-8")
    return src


# ─── Target listing ──────────────────────────────────────────────────


def test_agent_targets_has_codex_and_agents():
    assert ".codex/skills" in AGENT_TARGETS
    assert ".agents/skills" in AGENT_TARGETS


def test_list_targets_returns_paths(tmp_path: Path):
    targets = list_targets(tmp_path)
    assert len(targets) == len(AGENT_TARGETS)
    assert all(isinstance(t, Path) for t in targets)


# ─── Install single skill ────────────────────────────────────────────


def test_install_skill_creates_copies(tmp_path: Path):
    src = _seed_source(tmp_path)
    count = install_skill("skill1", source=src, repo_root=tmp_path)
    assert count == len(AGENT_TARGETS)
    for target in list_targets(tmp_path):
        assert (target / "skill1" / "SKILL.md").is_file()


def test_install_skill_missing_source(tmp_path: Path):
    src = tmp_path / ".claude" / "skills"
    src.mkdir(parents=True)
    count = install_skill("nonexistent", source=src, repo_root=tmp_path)
    assert count == 0


def test_install_skill_overwrites_existing(tmp_path: Path):
    src = _seed_source(tmp_path)
    # Pre-create a stale skill
    target = tmp_path / ".codex" / "skills" / "skill1"
    target.mkdir(parents=True)
    (target / "stale.md").write_text("stale content\n", encoding="utf-8")

    install_skill("skill1", source=src, repo_root=tmp_path)

    # Stale file gone, real SKILL.md present
    assert not (target / "stale.md").exists()
    assert (target / "SKILL.md").is_file()


# ─── Install all ─────────────────────────────────────────────────────


def test_install_all_installs_every_skill(tmp_path: Path):
    src = _seed_source(tmp_path)
    count = install_all(source=src, repo_root=tmp_path)
    # 2 skills × 2 targets = 4
    assert count == 4


def test_install_all_skips_non_skills(tmp_path: Path):
    src = _seed_source(tmp_path)
    install_all(source=src, repo_root=tmp_path)
    for target in list_targets(tmp_path):
        # not-a-skill should NOT have been copied
        assert not (target / "not-a-skill").exists()
        # skill1 and skill2 should be there
        assert (target / "skill1").exists()
        assert (target / "skill2").exists()


def test_install_all_missing_source(tmp_path: Path):
    count = install_all(source=tmp_path / "nonexistent", repo_root=tmp_path)
    assert count == 0


def test_install_all_empty_source(tmp_path: Path):
    src = tmp_path / "empty"
    src.mkdir()
    count = install_all(source=src, repo_root=tmp_path)
    assert count == 0


# ─── list_installed ──────────────────────────────────────────────────


def test_list_installed_empty_before_install(tmp_path: Path):
    result = list_installed(repo_root=tmp_path)
    for _target, skills in result.items():
        assert skills == []


def test_list_installed_after_install(tmp_path: Path):
    src = _seed_source(tmp_path)
    install_all(source=src, repo_root=tmp_path)
    result = list_installed(repo_root=tmp_path)
    for _target, skills in result.items():
        assert set(skills) == {"skill1", "skill2"}


def test_list_installed_ignores_non_skills(tmp_path: Path):
    src = _seed_source(tmp_path)
    install_all(source=src, repo_root=tmp_path)
    # Manually create a non-skill dir in a target
    stray = tmp_path / ".codex" / "skills" / "stray"
    stray.mkdir()
    (stray / "README.md").write_text("no SKILL.md\n", encoding="utf-8")

    result = list_installed(repo_root=tmp_path)
    codex_target = str(tmp_path / ".codex" / "skills")
    # stray isn't listed because it has no SKILL.md
    assert "stray" not in result[codex_target]


# ─── Real-repo smoke test ────────────────────────────────────────────


def test_real_skills_have_SKILL_md():
    """Verify the canonical .claude/skills/ in the actual repo has SKILL.md."""
    from llmwiki import REPO_ROOT
    canonical = REPO_ROOT / ".claude" / "skills"
    assert canonical.is_dir()
    for skill_dir in canonical.iterdir():
        if skill_dir.is_dir():
            assert (skill_dir / "SKILL.md").is_file(), \
                f"skill {skill_dir.name!r} is missing SKILL.md"
