"""`llmwiki remove` cascade — a matched raw doc drags every derived
artifact out with it (raw file, synth-state key, wiki source page), so a
naive `rm raw/docs/...` can never leave the wiki holding orphan pages or
dangling state keys (B2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki.add_doc import add_sources, expected_source_page
from llmwiki.remove_doc import build_remove_plan, execute_remove_plan
from llmwiki.synth.pipeline import synthesize_new_sessions


def _read_synth_keys(state_file: Path) -> set[str]:
    return set(json.loads(state_file.read_text())["synth"]["files"])


def _build_vault(tmp_path: Path) -> tuple[Path, list[Path], Path]:
    """A real vault: one added raw doc, its synth-state key, its wiki page.

    Built through the real add + synthesize path so the layout matches
    exactly what production writes (empty ``source_file`` on doc pages
    included), not a hand-faked stand-in.
    """
    vault = tmp_path / "vault"
    docs = vault / "raw" / "docs"
    docs.mkdir(parents=True)
    sessions = vault / "raw" / "sessions"
    sessions.mkdir(parents=True)
    wiki_sources = vault / "wiki" / "sources"
    wiki_sources.mkdir(parents=True)
    (vault / "wiki" / "log.md").write_text("# Log\n", encoding="utf-8")
    (vault / "wiki" / "index.md").write_text(
        "# Wiki Index\n\n## Sources\n*(none yet)*\n\n## Entities\n- keep me\n",
        encoding="utf-8",
    )

    src = tmp_path / "note.md"
    src.write_text("# Ip v Armenii\n\nProperty rules in Armenia. " * 30, encoding="utf-8")
    res = add_sources([str(src)], docs, project="ip-v-armenii")

    state_file = vault / "llmwiki-state.json"
    synthesize_new_sessions(
        raw_dir=sessions, wiki_sources_dir=wiki_sources, docs_dir=docs,
        state_file=state_file, log_path=vault / "wiki" / "log.md",
    )
    return vault, res["written"], state_file


def test_plan_lists_the_full_cascade(tmp_path: Path) -> None:
    vault, written, state_file = _build_vault(tmp_path)
    raw_doc = written[0]
    page = expected_source_page(raw_doc, vault / "wiki" / "sources")
    assert raw_doc.exists() and page.exists()

    plan = build_remove_plan(vault, "ip-v-armenii*", state_file=state_file)

    assert raw_doc in plan.raw_docs
    assert page in plan.source_pages
    assert "docs::ip-v-armenii/ip-v-armenii.md" in plan.state_keys
    assert not plan.is_empty


def test_dry_run_mutates_nothing(tmp_path: Path) -> None:
    vault, written, state_file = _build_vault(tmp_path)
    raw_doc = written[0]
    page = expected_source_page(raw_doc, vault / "wiki" / "sources")
    log_before = (vault / "wiki" / "log.md").read_text()
    keys_before = _read_synth_keys(state_file)

    # Planning is read-only; a dry-run is exactly "plan, then don't execute".
    plan = build_remove_plan(vault, "ip-v-armenii*", state_file=state_file)
    assert not plan.is_empty

    assert raw_doc.exists()
    assert page.exists()
    assert _read_synth_keys(state_file) == keys_before
    assert (vault / "wiki" / "log.md").read_text() == log_before
    assert "remove" not in log_before


def test_execute_removes_the_whole_cascade_orphan_free(tmp_path: Path) -> None:
    vault, written, state_file = _build_vault(tmp_path)
    raw_doc = written[0]
    wiki_sources = vault / "wiki" / "sources"
    page = expected_source_page(raw_doc, wiki_sources)

    plan = build_remove_plan(vault, "ip-v-armenii*", state_file=state_file)
    result = execute_remove_plan(plan, state_file=state_file)

    # Raw doc + its wiki page + its state key are all gone.
    assert not raw_doc.exists()
    assert not page.exists()
    assert "docs::ip-v-armenii/ip-v-armenii.md" not in _read_synth_keys(state_file)
    assert result["raw_docs"] == 1
    assert result["source_pages"] == 1

    # No orphan page anywhere still pointing at a deleted raw doc.
    from llmwiki._frontmatter import parse_frontmatter
    for p in wiki_sources.rglob("*.md"):
        meta, _ = parse_frontmatter(p.read_text())
        assert "ip-v-armenii" not in str(meta.get("source_file", ""))

    # A remove entry landed in the log, unrelated index sections survived.
    log = (vault / "wiki" / "log.md").read_text()
    assert "remove | 1 docs (ip-v-armenii*)" in log
    assert "keep me" in (vault / "wiki" / "index.md").read_text()


def test_source_file_frontmatter_page_is_caught(tmp_path: Path) -> None:
    """A manually-placed page (arbitrary folder/name) is still cascaded
    when its ``source_file`` points at a removed raw doc."""
    vault, written, state_file = _build_vault(tmp_path)
    manual = vault / "wiki" / "sources" / "hand-written.md"
    manual.write_text(
        "---\ntitle: manual\ntype: source\n"
        "source_file: raw/docs/ip-v-armenii/ip-v-armenii.md\n---\n\nbody\n",
        encoding="utf-8",
    )

    plan = build_remove_plan(vault, "ip-v-armenii*", state_file=state_file)
    assert manual in plan.source_pages
    execute_remove_plan(plan, state_file=state_file)
    assert not manual.exists()


def test_glob_scopes_to_matching_docs(tmp_path: Path) -> None:
    vault, _written, state_file = _build_vault(tmp_path)
    docs = vault / "raw" / "docs"
    other = tmp_path / "other.md"
    other.write_text("# Taxes\n\nUnrelated content. " * 30, encoding="utf-8")
    add_sources([str(other)], docs, project="taxes")
    synthesize_new_sessions(
        raw_dir=vault / "raw" / "sessions",
        wiki_sources_dir=vault / "wiki" / "sources",
        docs_dir=docs, state_file=state_file,
        log_path=vault / "wiki" / "log.md",
    )

    plan = build_remove_plan(vault, "ip-v-armenii*", state_file=state_file)
    execute_remove_plan(plan, state_file=state_file)

    assert not (docs / "ip-v-armenii").exists()
    assert (docs / "taxes" / "taxes.md").exists()
    assert "docs::taxes/taxes.md" in _read_synth_keys(state_file)


def test_empty_match_is_a_clean_noop(tmp_path: Path) -> None:
    vault, written, state_file = _build_vault(tmp_path)
    keys_before = _read_synth_keys(state_file)

    plan = build_remove_plan(vault, "does-not-exist*", state_file=state_file)
    assert plan.is_empty
    assert plan.raw_docs == []

    result = execute_remove_plan(plan, state_file=state_file)
    assert result["raw_docs"] == 0
    assert written[0].exists()
    assert _read_synth_keys(state_file) == keys_before


def test_cli_remove_requires_confirmation(tmp_path: Path, monkeypatch) -> None:
    vault, written, _state_file = _build_vault(tmp_path)
    from llmwiki.cli import main

    # No --yes and no TTY → refuse to cascade, exit non-zero, touch nothing.
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    rc = main(["remove", "ip-v-armenii*", "--vault", str(vault)])
    assert rc != 0
    assert written[0].exists()


def test_cli_remove_yes_executes(tmp_path: Path) -> None:
    vault, written, state_file = _build_vault(tmp_path)
    page = expected_source_page(written[0], vault / "wiki" / "sources")
    from llmwiki.cli import main

    rc = main(["remove", "ip-v-armenii*", "--yes", "--vault", str(vault)])
    assert rc == 0
    assert not written[0].exists()
    assert not page.exists()
    assert "docs::ip-v-armenii/ip-v-armenii.md" not in _read_synth_keys(state_file)


def test_cli_remove_dry_run_reports_without_deleting(tmp_path: Path, capsys) -> None:
    vault, written, state_file = _build_vault(tmp_path)
    from llmwiki.cli import main

    rc = main(["remove", "ip-v-armenii*", "--dry-run", "--vault", str(vault)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ip-v-armenii" in out
    assert "docs::ip-v-armenii/ip-v-armenii.md" in out
    assert written[0].exists()


def test_pending_backlog_entry_is_dropped(tmp_path: Path) -> None:
    """A doc removed before it was ever synthesized has no ``synth.files``
    key — only a ``synth.pending`` entry. Dropping just the files dict would
    strand the backlog pointing at a file that no longer exists."""
    vault, written, state_file = _build_vault(tmp_path)
    raw_doc = written[0]
    rel = raw_doc.relative_to(vault / "raw" / "docs").as_posix()
    source = f"raw/docs/{rel}"

    state = json.loads(state_file.read_text())
    synth = state["synth"]
    synth["pending"] = [
        {"is_doc": True, "project": "ip-v-armenii", "rel": rel,
         "source": source, "mtime": "2026-07-07T00:00:00Z"},
        {"is_doc": False, "project": "other", "rel": "s.md",
         "source": "raw/sessions/s.md", "mtime": "2026-07-07T00:00:00Z"},
    ]
    synth["pending_total"] = 2
    state_file.write_text(json.dumps(state), encoding="utf-8")

    plan = build_remove_plan(vault, "ip-v-armenii*", state_file=state_file)
    assert source in plan.pending_sources

    result = execute_remove_plan(plan, state_file=state_file)
    assert result["pending_entries"] == 1

    after = json.loads(state_file.read_text())["synth"]
    remaining = [e["source"] for e in after["pending"]]
    assert source not in remaining
    assert "raw/sessions/s.md" in remaining  # unrelated backlog survives
    assert after["pending_total"] == 1
