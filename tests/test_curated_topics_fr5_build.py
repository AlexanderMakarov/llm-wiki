"""FR5 + synth-path guards through real ``build_site()`` (#248).

# @layer: integration
# @spec: 248-wiki-site-search-corpus
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki.topics_consolidate import build_candidates
from tests.support.curated_topics_demo import run_build


def _raw_session(stem: str) -> str:
    return (
        f'---\ntitle: "{stem}"\ntype: source\nproject: demo\n'
        f"slug: {stem}\ndate: 2026-07-01\n"
        f"source_file: raw/sessions/demo/{stem}.md\n"
        "tools_used: [Bash]\n"
        'token_totals: {"input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}\n'
        "---\n\n# demo\n"
    )


def _wiki_source(stem: str, links: list[str]) -> str:
    body = "\n".join(f"- [[{t}]]" for t in links)
    return (
        f'---\ntitle: "{stem}"\ntype: source\nproject: demo\n'
        f"date: 2026-07-01\nsource_file: raw/sessions/demo/{stem}.md\n"
        f"---\n\n## Connections\n\n{body}\n"
    )


def _curated_page(name: str) -> str:
    return (
        f'---\ntitle: "{name}"\ntype: entity\ntags: []\n'
        "last_updated: 2026-07-01\n---\n\n"
        f"# {name}\n\n## Key Facts\n\n- A reviewed page.\n"
    )


def _scaffold_fr5_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    raw = vault / "raw" / "sessions" / "demo"
    wiki_src = vault / "wiki" / "sources" / "demo"
    raw.mkdir(parents=True)
    wiki_src.mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)

    (raw / "2026-07-01T10-00-demo-a.md").write_text(_raw_session("a"), encoding="utf-8")
    (wiki_src / "a.md").write_text(_wiki_source("a", ["OneOff"]), encoding="utf-8")

    entities = vault / "wiki" / "entities"
    entities.mkdir(parents=True)
    (entities / "Hazel.md").write_text(_curated_page("Hazel"), encoding="utf-8")
    (entities / "_context.md").write_text(
        '---\ntitle: "Entities"\ntype: context\n---\n\nStub for assistants.\n',
        encoding="utf-8",
    )
    archive = vault / "wiki" / "archive" / "entities"
    archive.mkdir(parents=True)
    (archive / "Dismissed.md").write_text(_curated_page("Dismissed"), encoding="utf-8")
    return vault


def test_archived_and_context_stubs_stay_out_of_site(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    vault = _scaffold_fr5_vault(tmp_path)
    out = tmp_path / "site"
    assert run_build(vault, out, monkeypatch) == 0

    assert (out / "topics" / "hazel.html").is_file()
    assert not (out / "topics" / "dismissed.html").exists()
    assert not (out / "topics" / "oneoff.html").exists()

    idx = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
    topic_titles = {e["title"] for e in idx["entries"] if e.get("type") == "topic"}
    assert "Hazel" in topic_titles
    assert "Dismissed" not in topic_titles
    assert "OneOff" not in topic_titles


def test_curated_bypass_does_not_leak_into_synth_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    vault = _scaffold_fr5_vault(tmp_path)
    out = tmp_path / "site"
    assert run_build(vault, out, monkeypatch) == 0
    assert (out / "topics" / "hazel.html").is_file()

    candidate_names = {c["name"] for c in build_candidates(vault / "wiki")}
    assert "Hazel" not in candidate_names
    assert "Dismissed" not in candidate_names
