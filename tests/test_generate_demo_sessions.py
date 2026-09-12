"""Smoke checks for ``scripts/generate_demo_sessions.py`` (#197).

# @layer: unit
# @spec: 197-search-quality-eval
"""

from __future__ import annotations

import importlib.util
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "generate_demo_sessions.py"


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("generate_demo_sessions", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # dataclasses need the module registered before exec
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_render_matches_convert_shape_and_counts(gen, tmp_path: Path):
    s = gen._apply_title_plants(gen.SESSIONS[0])
    when = datetime(2026, 5, 11, tzinfo=UTC)
    dest = tmp_path / f"{when:%Y-%m-%dT%H-%M}-{s.project}-{s.slug}.md"
    text = gen.render_session(s, when, 0, dest=dest)
    assert "**Project:**" in text and "**Stats:**" in text
    assert "### Turn 1 — User" in text and "### Turn 1 — Assistant" in text
    assert "## Subjects" not in text
    assert re.search(r"### Turn \d+ — Tool", text) is None
    um = int(re.search(r"^user_messages: (\d+)", text, re.M).group(1))
    tc = int(re.search(r"^tool_calls: (\d+)", text, re.M).group(1))
    assert um == len(re.findall(r"^### Turn \d+ — User$", text, re.M))
    assert tc == len(re.findall(r"^- `[^`]+`:", text, re.M))


def test_resolve_dest_keeps_existing_slug_path(gen, tmp_path: Path):
    existing_path = tmp_path / "old-name-my-slug.md"
    existing_path.write_text("---\nslug: my-slug\n---\n", encoding="utf-8")
    s = gen.Session(
        project="p",
        slug="my-slug",
        adapter="claude_code",
        model="m",
        branch="b",
        title="t",
        summary="s",
        subjects=(),
        turns=(("user", "hi"), ("assistant", "yo")),
    )
    when = datetime(2026, 10, 1, tzinfo=UTC)
    got = gen.resolve_dest(s, when, {"my-slug": existing_path})
    assert got == existing_path


def test_activity_profiles_are_not_all_two_users(gen):
    counts = {gen._activity_for_index(i)[1] for i in range(len(gen._ACTIVITY_PROFILES))}
    assert counts != {2}
    assert 1 in counts and max(counts) >= 11


def test_plant_tables_reference_existing_sessions(gen):
    slugs = {s.slug for s in gen.SESSIONS}
    for plant in gen.PLANTED_PRESENT:
        assert plant.session in slugs, plant
    for session, _placement, _word in gen.PHRASE_WORD_SEEDS:
        assert session in slugs, session
