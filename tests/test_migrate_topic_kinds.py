"""Offline topic-kind stamp migration (#174): library + CLI wiring.

# @spec: 174-migrate-topic-kinds
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from llmwiki.cli import build_parser
from llmwiki.migrate_topic_kinds import (
    STAMPED_LIST_FILENAME,
    build_kind_map,
    print_report,
    run_migration,
    stamp_connections_body,
)
from llmwiki.source_topics import source_page_needs_topics_rewrite
from llmwiki.synth.pipeline import _load_state, _save_state, source_synth_is_done


def _page(path: Path, body: str, **meta: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}: {v}" for k, v in meta.items()]
    front = "\n".join(lines)
    path.write_text(f"---\n{front}\n---\n\n{body}\n", encoding="utf-8")


def _entity(wiki: Path, name: str) -> None:
    _page(
        wiki / "entities" / f"{name}.md",
        f"# {name}\n\n## Connections\n- [[demo]]",
        title=f'"{name}"',
        type="entity",
        last_updated="2026-08-01",
    )


def _concept(wiki: Path, name: str) -> None:
    _page(
        wiki / "concepts" / f"{name}.md",
        f"# {name}\n\n## Connections\n- [[demo]]",
        title=f'"{name}"',
        type="concept",
        last_updated="2026-08-01",
    )


def _source(
    wiki: Path,
    slug: str,
    connections: str,
    *,
    extra_sections: str = "",
    source_file: str | None = "raw/sessions/demo.md",
) -> Path:
    body = (
        f"# {slug}\n\n"
        f"{extra_sections}"
        f"## Connections\n{connections}"
    )
    meta: dict[str, object] = {
        "title": f'"{slug}"',
        "type": "source",
        "date": "2026-08-01",
    }
    if source_file is not None:
        meta["source_file"] = source_file
    path = wiki / "sources" / f"{slug}.md"
    _page(path, body, **meta)
    return path


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# ─── kind map ──────────────────────────────────────────────────────────


def test_build_kind_map_from_live_and_candidate_folders(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI")
    _concept(wiki, "RAG")
    _page(
        wiki / "candidates" / "entities" / "Anthropic.md",
        "# Anthropic",
        title='"Anthropic"',
        type="entity",
    )
    _page(
        wiki / "candidates" / "concepts" / "Caching.md",
        "# Caching",
        title='"Caching"',
        type="concept",
    )
    _page(
        wiki / "entities" / "_context.md",
        "People and products.",
        title='"Entities"',
        type="context",
    )

    kind_map, ambiguous = build_kind_map(wiki)

    assert kind_map == {
        "openai": "entity",
        "rag": "concept",
        "anthropic": "entity",
        "caching": "concept",
    }
    assert ambiguous == []
    assert "_context" not in kind_map


def test_ambiguous_dual_filing_removed_from_map(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "Python")
    _concept(wiki, "Python")

    kind_map, ambiguous = build_kind_map(wiki)

    assert "python" not in kind_map
    assert ambiguous == ["Python"]


# ─── stamping ──────────────────────────────────────────────────────────


def test_stamp_inserts_kind_after_wikilink_preserves_description() -> None:
    body = (
        "## Key Claims\n"
        "- Claim about [[OpenAI]] stays\n\n"
        "## Connections\n"
        "- [[OpenAI]] — vendor used\n"
        "  - fact: nested stays\n"
        "- [[UnknownThing]] — left alone\n"
    )
    kind_map = {"openai": "entity"}
    new_body, counters = stamp_connections_body(body, kind_map, set())

    assert counters["bullets_stamped"] == 1
    assert counters["bullets_unresolved"] == 1
    assert "- [[OpenAI]] (entity) — vendor used\n" in new_body
    assert "  - fact: nested stays\n" in new_body
    assert "- [[UnknownThing]] — left alone\n" in new_body
    assert "## Key Claims\n- Claim about [[OpenAI]] stays\n" in new_body


def test_already_kinded_line_is_byte_identical() -> None:
    line = "- [[OpenAI]] (entity) — already labeled"
    body = f"## Connections\n{line}\n"
    new_body, counters = stamp_connections_body(
        body, {"openai": "entity"}, set()
    )
    assert counters["bullets_stamped"] == 0
    assert counters["bullets_unresolved"] == 0
    assert new_body == body
    assert line in new_body


def test_ambiguous_name_left_unchanged() -> None:
    body = "## Connections\n- [[Python]] — dual filed\n"
    new_body, counters = stamp_connections_body(body, {}, {"python"})
    assert new_body == body
    assert counters["bullets_stamped"] == 0
    assert counters["bullets_unresolved"] == 1


# ─── run_migration ─────────────────────────────────────────────────────


def test_stamping_flips_rewrite_predicate(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI")
    raw = tmp_path / "raw" / "sessions"
    raw.mkdir(parents=True)
    raw_path = raw / "2026-08-01-demo.md"
    raw_path.write_text(
        "---\ntitle: demo\nproject: demo\nslug: demo\ndate: 2026-08-01\n---\n\nbody\n",
        encoding="utf-8",
    )
    source = _source(
        wiki,
        "demo",
        "- [[OpenAI]] — vendor\n",
        source_file="raw/sessions/2026-08-01-demo.md",
    )
    # Put page where synth expects it
    dest = wiki / "sources" / "demo" / "2026-08-01-demo.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    source.unlink()
    before = dest.read_text(encoding="utf-8")
    assert source_page_needs_topics_rewrite(before) is True

    report = run_migration(vault=tmp_path)

    after = dest.read_text(encoding="utf-8")
    assert source_page_needs_topics_rewrite(after) is False
    assert report["pages_stamped"] == 1
    assert report["bullets_stamped"] == 1
    assert report["facts_derived"] == 0
    assert "[[OpenAI]] (entity) — vendor" in after
    assert report["state_entries_updated"] >= 1

    state = _load_state(tmp_path / "llmwiki-state.json")
    assert "2026-08-01-demo.md" in state


def test_key_claims_and_quotes_untouched(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _concept(wiki, "RAG")
    claims = (
        "## Key Claims\n"
        "- Important claim mentioning [[RAG]]\n\n"
        "## Key Quotes\n"
        '> "quote with [[RAG]]" — context\n\n'
    )
    source = _source(
        wiki,
        "demo",
        "- [[RAG]] — retrieval\n",
        extra_sections=claims,
    )
    before = source.read_text(encoding="utf-8")
    claims_idx = before.index("## Key Claims")
    quotes_idx = before.index("## Key Quotes")
    conn_idx = before.index("## Connections")
    claims_block = before[claims_idx:quotes_idx]
    quotes_block = before[quotes_idx:conn_idx]

    run_migration(vault=tmp_path)

    after = source.read_text(encoding="utf-8")
    assert after[after.index("## Key Claims") : after.index("## Key Quotes")] == (
        claims_block
    )
    assert after[after.index("## Key Quotes") : after.index("## Connections")] == (
        quotes_block
    )


def test_candidates_supply_kinds(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _page(
        wiki / "candidates" / "entities" / "Cursor.md",
        "# Cursor",
        title='"Cursor"',
        type="entity",
    )
    source = _source(wiki, "demo", "- [[Cursor]]\n")

    report = run_migration(vault=tmp_path)

    assert report["bullets_stamped"] == 1
    assert "(entity)" in source.read_text(encoding="utf-8")


def test_ambiguous_skipped_and_listed(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "Python")
    _concept(wiki, "Python")
    source = _source(wiki, "demo", "- [[Python]] — dual\n")
    before = source.read_text(encoding="utf-8")

    report = run_migration(vault=tmp_path)

    assert source.read_text(encoding="utf-8") == before
    assert "Python" in report["ambiguous"]
    assert report["bullets_stamped"] == 0
    assert report["bullets_unresolved"] == 1
    assert report["pages_pending_rewrite"] == 1


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI")
    _source(wiki, "demo", "- [[OpenAI]] — vendor\n")
    before = _snapshot(tmp_path)

    report = run_migration(vault=tmp_path, dry_run=True)

    assert report["changed"] is True
    assert report["pages_stamped"] == 1
    assert _snapshot(tmp_path) == before
    assert not (tmp_path / STAMPED_LIST_FILENAME).exists()


def test_stamped_json_written_only_on_successful_apply(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI")
    _source(
        wiki,
        "demo",
        "- [[OpenAI]] — vendor\n",
        source_file="raw/sessions/2026-08-01-demo.md",
    )

    report = run_migration(vault=tmp_path)

    stamped_path = tmp_path / STAMPED_LIST_FILENAME
    assert stamped_path.is_file()
    payload = json.loads(stamped_path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["command"] == "migrate-topic-kinds"
    assert payload["issue"] == 174
    assert payload["pages"] == [
        {
            "wiki_path": "wiki/sources/demo.md",
            "source_file": "raw/sessions/2026-08-01-demo.md",
        }
    ]
    assert report["stamped_pages"] == payload["pages"]


def test_nothing_to_migrate_message(tmp_path: Path, capsys) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI")
    raw = tmp_path / "raw" / "sessions"
    raw.mkdir(parents=True)
    raw_path = raw / "2026-08-01-demo.md"
    raw_path.write_text(
        "---\ntitle: demo\nproject: demo\nslug: demo\ndate: 2026-08-01\n---\n\nx\n",
        encoding="utf-8",
    )
    dest = wiki / "sources" / "demo" / "2026-08-01-demo.md"
    _page(
        dest,
        "# demo\n\n## Connections\n- [[OpenAI]] (entity) — already\n",
        title='"demo"',
        type="source",
        date="2026-08-01",
        source_file="raw/sessions/2026-08-01-demo.md",
    )
    # Prime state so backfill has nothing to do
    _save_state({raw_path.name: raw_path.stat().st_mtime}, tmp_path / "llmwiki-state.json")

    report = run_migration(vault=tmp_path)
    print_report(report)

    out = capsys.readouterr().out
    assert "nothing to migrate" in out
    assert report["changed"] is False
    assert report["state_entries_updated"] == 0
    assert not (tmp_path / STAMPED_LIST_FILENAME).exists()


def test_state_backfill_marks_shared_filename_raws_done(tmp_path: Path) -> None:
    """Many raw sessions → one rewrite-clear wiki page; all get state (#174)."""
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI")
    raw = tmp_path / "raw" / "sessions"
    raw.mkdir(parents=True)
    page = wiki / "sources" / "proj" / "2026-08-08-store.md"
    body = (
        "# store\n\n## Connections\n- [[OpenAI]] (entity) — already kinded\n"
    )
    _page(
        page,
        body,
        title='"store"',
        type="source",
        date="2026-08-08",
        source_file="raw/sessions/2026-08-08T10-00-proj-store.md",
        project="proj",
    )
    rels = []
    for hour in ("10-00", "11-00", "12-00"):
        rel = f"2026-08-08T{hour}-proj-store.md"
        rels.append(rel)
        (raw / rel).write_text(
            "---\n"
            'title: "store"\n'
            "project: proj\n"
            "slug: store\n"
            "date: 2026-08-08\n"
            "---\n\nbody\n",
            encoding="utf-8",
        )

    report = run_migration(vault=tmp_path)

    assert report["pages_stamped"] == 0  # already kinded
    assert report["state_entries_updated"] == 3

    state = _load_state(tmp_path / "llmwiki-state.json")
    for rel in rels:
        assert rel in state
        assert source_synth_is_done(
            rel, state, state[rel], page_is_pending=False
        )


def test_print_report_includes_facts_derived_zero(tmp_path: Path, capsys) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI")
    _source(wiki, "demo", "- [[OpenAI]] — vendor\n")

    report = run_migration(vault=tmp_path)
    print_report(report)

    out = capsys.readouterr().out
    assert "facts derived:          0" in out
    assert "no facts were derived" in out
    assert "synth --force" in out


def test_migration_module_has_no_synth_backend_imports() -> None:
    """Migration may use synth *state* helpers; must not pull HTTP backends."""
    source = Path("llmwiki/migrate_topic_kinds.py").read_text(encoding="utf-8")
    forbidden = (
        r"llmwiki\.synth\.ollama",
        r"llmwiki\.synth\.claude",
        r"llmwiki\.backends",
        r"\bhttpx\b",
        r"\burllib\b",
        r"\brequests\b",
        r"\bopenai\b",
        r"\banthropic\b",
    )
    for pattern in forbidden:
        assert not re.search(pattern, source), f"forbidden import pattern: {pattern}"
    # State backfill uses pipeline leaf helpers only.
    assert "from llmwiki.synth.pipeline import" in source


# ─── CLI wiring ────────────────────────────────────────────────────────


def test_cli_runs_the_migration(tmp_path: Path, capsys) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI")
    source = _source(wiki, "demo", "- [[OpenAI]] — vendor\n")
    args = build_parser().parse_args(
        ["migrate", "topic-kinds", "--vault", str(tmp_path)]
    )

    assert args.func(args) == 0
    capsys.readouterr()
    assert "(entity)" in source.read_text(encoding="utf-8")
    assert (tmp_path / STAMPED_LIST_FILENAME).is_file()


def test_cli_dry_run_writes_nothing(tmp_path: Path, capsys) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI")
    _source(wiki, "demo", "- [[OpenAI]] — vendor\n")
    before = _snapshot(tmp_path)
    args = build_parser().parse_args(
        ["migrate", "topic-kinds", "--vault", str(tmp_path), "--dry-run"]
    )

    assert args.func(args) == 0
    capsys.readouterr()
    assert _snapshot(tmp_path) == before
    assert not (tmp_path / STAMPED_LIST_FILENAME).exists()


def test_write_failure_omits_page_from_stamped_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR6: a failed write must not appear in the stamped JSON (B1)."""
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI")
    source = _source(wiki, "demo", "- [[OpenAI]] — vendor\n")
    before = source.read_text(encoding="utf-8")
    real_write = Path.write_text

    def _failing_write(self: Path, data: object, *args: object, **kwargs: object) -> None:
        if self == source:
            raise OSError("simulated write failure")
        return real_write(self, data, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "write_text", _failing_write)

    report = run_migration(vault=tmp_path)

    assert source.read_text(encoding="utf-8") == before
    assert report["errors"]
    assert report["pages_stamped"] == 0
    assert report["stamped_pages"] == []
    assert not (tmp_path / STAMPED_LIST_FILENAME).exists()
    assert report["pages_pending_rewrite"] == 1


def test_cli_requires_a_vault() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["migrate", "topic-kinds"])
