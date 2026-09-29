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


def _seed_dated_vault(gen, root: Path, monkeypatch) -> tuple[Path, Path]:
    """A demo-shaped vault whose one session page is named for an old date."""
    raw_rel = "llm-wiki/2026-09-07T23-12-llm-wiki-wikilink-resolution.md"
    raw = root / "raw" / "sessions" / raw_rel
    raw.parent.mkdir(parents=True)
    raw.write_text("---\nslug: wikilink-resolution\n---\n", encoding="utf-8")
    page = root / "wiki" / "sources" / "llm-wiki" / "2026-09-07-wikilink-resolution.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "---\n"
        'title: "Session: wikilink-resolution — 2026-09-07"\n'
        "type: source\n"
        "date: 2026-09-07\n"
        f"source_file: raw/sessions/{raw_rel}\n"
        "project: llm-wiki\n"
        "---\n\n## Summary\n\nA real synthesized summary.\n",
        encoding="utf-8",
    )
    linker = root / "wiki" / "concepts" / "Wikilinks.md"
    linker.parent.mkdir(parents=True)
    linker.write_text(
        "---\ntitle: Wikilinks\ntype: concept\n---\n\n"
        "## Connections\n\n- [[2026-09-07-wikilink-resolution]]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gen, "DEMO_VAULT", root)
    monkeypatch.setattr(gen, "DEMO_SESSIONS", root / "raw" / "sessions")
    monkeypatch.setattr(gen, "emit_search_terms_fixture", lambda *a, **k: None)
    return raw, linker


def test_release_day_write_rehomes_source_pages(gen, tmp_path: Path, monkeypatch):
    """--today moves a session's date, so its source page moves with it.

    Without the re-home pass, the next session synth skips every re-dated
    source as "already claimed by a real page under another name".
    """
    raw, linker = _seed_dated_vault(gen, tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "argv", ["generate_demo_sessions.py", "--today", "2026-09-28"])

    assert gen.main() == 0

    new_date = re.search(r"^date: (\S+)$", raw.read_text(encoding="utf-8"), re.M).group(1)
    assert new_date != "2026-09-07"
    sources = tmp_path / "wiki" / "sources" / "llm-wiki"
    assert not (sources / "2026-09-07-wikilink-resolution.md").exists()
    assert (sources / f"{new_date}-wikilink-resolution.md").is_file()
    assert f"[[{new_date}-wikilink-resolution]]" in linker.read_text(encoding="utf-8")
    # The release demo gate reads the date back as the cut's release day.
    assert (tmp_path / gen.SESSIONS_DATE_FILE).read_text(encoding="utf-8") == "2026-09-28\n"


def test_dry_run_leaves_source_pages_in_place(gen, tmp_path: Path, monkeypatch):
    _seed_dated_vault(gen, tmp_path, monkeypatch)
    monkeypatch.setattr(
        sys, "argv", ["generate_demo_sessions.py", "--dry-run", "--today", "2026-09-28"]
    )

    assert gen.main() == 0

    assert (tmp_path / "wiki" / "sources" / "llm-wiki" / "2026-09-07-wikilink-resolution.md").is_file()
