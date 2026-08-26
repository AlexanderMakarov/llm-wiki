"""Regression guard for #170: wiki-all skill must mirror ``PIPELINE_STAGES``.

# @layer: unit
# @spec: 170-wiki-all-skill-pipeline
# @regression
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from llmwiki.pipeline import PIPELINE_STAGES, run_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
WIKI_ALL_SKILL = REPO_ROOT / "llmwiki" / "agent_kit" / "skills" / "wiki-all" / "SKILL.md"
WIKI_ALL_CMD = REPO_ROOT / "llmwiki" / "agent_kit" / "commands" / "wiki-all.md"

STALE_OBSIDIAN_PATH = "Documents/Obsidian Vault/Temp/Graph"
NUMBERED_INIT_RE = re.compile(r"^\d+\.\s+\*\*init\*\*", re.MULTILINE | re.IGNORECASE)
FIRST_LLMWIKI_INVOCATION_RE = re.compile(
    r"python3\s+-m\s+llmwiki\s+([a-z][a-z0-9_-]*)"
)


def _numbered_stage_positions(text: str, stages: tuple[str, ...]) -> list[int]:
    positions: list[int] = []
    for stage in stages:
        pattern = re.compile(
            rf"^\d+\.\s+\*\*{re.escape(stage)}\*\*",
            re.MULTILINE,
        )
        match = pattern.search(text)
        if match is None:
            pytest.fail(f"numbered pipeline stage {stage!r} not found")
        positions.append(match.start())
    return positions


def _assert_stages_in_order(text: str, *, label: str) -> None:
    positions = _numbered_stage_positions(text, PIPELINE_STAGES)
    assert positions == sorted(positions), (
        f"{label}: stages must appear in {PIPELINE_STAGES!r} order; "
        f"positions={dict(zip(PIPELINE_STAGES, positions, strict=True))}"
    )


def _assert_no_numbered_init_stage(text: str, *, label: str) -> None:
    assert not NUMBERED_INIT_RE.search(text), (
        f"{label}: must not list init as a numbered pipeline stage"
    )


def _assert_no_stale_obsidian_path(text: str, *, label: str) -> None:
    assert STALE_OBSIDIAN_PATH not in text, (
        f"{label}: must not hardcode stale Obsidian export path"
    )


def _assert_first_invocation_is_all(text: str, *, label: str) -> None:
    match = FIRST_LLMWIKI_INVOCATION_RE.search(text)
    assert match is not None, f"{label}: missing python3 -m llmwiki invocation"
    assert match.group(1) == "all", (
        f"{label}: first llmwiki subcommand must be 'all', got {match.group(1)!r}"
    )


def test_wiki_all_skill_matches_pipeline_contract() -> None:
    text = WIKI_ALL_SKILL.read_text(encoding="utf-8")
    _assert_stages_in_order(text, label="wiki-all SKILL.md")
    _assert_no_numbered_init_stage(text, label="wiki-all SKILL.md")
    _assert_no_stale_obsidian_path(text, label="wiki-all SKILL.md")
    _assert_first_invocation_is_all(text, label="wiki-all SKILL.md")


def test_wiki_all_command_matches_pipeline_stages() -> None:
    text = WIKI_ALL_CMD.read_text(encoding="utf-8")
    _assert_stages_in_order(text, label="wiki-all.md command")
    _assert_no_numbered_init_stage(text, label="wiki-all.md command")
    _assert_no_stale_obsidian_path(text, label="wiki-all.md command")
    _assert_first_invocation_is_all(text, label="wiki-all.md command")


def test_pipeline_stages_match_run_pipeline_banners() -> None:
    """``PIPELINE_STAGES`` must track the banners ``run_pipeline`` actually prints.

    A reorder of the runtime steps without updating the constant would leave
    shipped agent-kit prose wrong while skill/command tests stayed green (#170 review).
    """
    source = inspect.getsource(run_pipeline)
    banners = re.findall(r"==> llmwiki (\w+)", source)
    assert tuple(banners) == PIPELINE_STAGES, (
        f"run_pipeline banners {banners!r} must match PIPELINE_STAGES {PIPELINE_STAGES!r}"
    )


def test_stage_order_helper_rejects_wrong_order() -> None:
    bad = "\n".join(
        f"{index}. **{stage}**"
        for index, stage in enumerate(("build", "sync", "synth", "graph", "lint"), start=1)
    )
    with pytest.raises(AssertionError, match="stages must appear"):
        _assert_stages_in_order(bad, label="synthetic")


def test_numbered_init_helper_rejects_init_stage_line() -> None:
    bad = "1. **init** — scaffold the vault\n2. **sync** — convert sessions\n"
    with pytest.raises(AssertionError, match="must not list init"):
        _assert_no_numbered_init_stage(bad, label="synthetic")
