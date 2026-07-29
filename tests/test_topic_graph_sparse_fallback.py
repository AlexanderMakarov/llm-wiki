"""Sparse topic graphs must fall back to the page graph (#69 demo).

Seeding a few Claude-synthesized wiki sources can flip the site into
topic-graph mode while ``min_sessions=2`` keeps only 1–2 topics — which
looks broken on graph.html. Prefer the page graph until the vocabulary
is rich enough.
"""

from __future__ import annotations

from pathlib import Path

import llmwiki.build as build_mod
from llmwiki.build import build_site


def _raw_session(project: str, stem: str) -> str:
    return (
        f'---\ntitle: "{stem}"\ntype: source\nproject: {project}\n'
        f"slug: {stem}\ndate: 2026-07-01\n"
        f"source_file: raw/sessions/{project}/{stem}.md\n"
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


def test_sparse_topic_graph_falls_back_to_page_graph(tmp_path: Path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    raw = vault / "raw" / "sessions" / "demo"
    wiki_src = vault / "wiki" / "sources" / "demo"
    raw.mkdir(parents=True)
    wiki_src.mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "site").mkdir()

    # Two source pages that share only Claude + llm-wiki → topic graph
    # keeps 2 nodes after min_sessions=2 (same failure mode as the Pages demo).
    (raw / "2026-07-01T10-00-demo-a.md").write_text(
        _raw_session("demo", "a"), encoding="utf-8"
    )
    (wiki_src / "a.md").write_text(
        _wiki_source("a", ["Claude", "llm-wiki"]), encoding="utf-8"
    )
    (wiki_src / "b.md").write_text(
        _wiki_source("b", ["Claude", "llm-wiki"]), encoding="utf-8"
    )

    monkeypatch.setattr(build_mod, "REPO_ROOT", vault)
    monkeypatch.setattr(build_mod, "SOURCE_ROOT", vault)
    monkeypatch.setattr(build_mod, "RAW_DIR", vault / "raw")
    monkeypatch.setattr(build_mod, "RAW_SESSIONS", vault / "raw" / "sessions")
    monkeypatch.setattr(build_mod, "DEFAULT_OUT_DIR", vault / "site")
    monkeypatch.setattr(build_mod, "compile_docs_site", lambda *a, **k: [])

    rc = build_site(
        out_dir=vault / "site",
        raw_sessions=vault / "raw" / "sessions",
        raw_dir=vault / "raw",
        wiki_dir=vault / "wiki",
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "topic graph too sparse" in out
    assert "interactive graph viewer" in out
    html = (vault / "site" / "graph.html").read_text(encoding="utf-8")
    # Page-graph payload has no mode:"topic"; topic graph embeds '"mode": "topic"'.
    assert '"mode": "topic"' not in html
