"""Acceptance tests for whole-document storage (#311) — the feature as a whole, not per slice.

Each test walks a user journey across ``add`` → capped-backend ``synth`` → ``migrate`` → Wiki findability
and checks one cluster of ``functional-spec.md`` acceptance criteria. Slice-level mechanics (stitch rules,
every ambiguity kind, link rewriting, prompts) stay in ``test_add_doc.py``, ``test_whole_document_synth.py``
and ``test_migrate_whole_document_storage.py``; nothing here repeats them.

Every vault is synthetic and lives under ``tmp_path``. A legacy (pre-#311) vault is built the way it came to
exist: raw ``-NN`` pieces, each summarised on its own into a part page.

Spec: ``context/spec/324-whole-document-storage/functional-spec.md`` (GitHub #311).
"""

# @layer: integration
# @spec: 324-whole-document-storage

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.add_doc import add_sources, compute_content_hash, convert_path
from llmwiki.build import build_wiki_corpus_entries
from llmwiki.cli import build_parser
from llmwiki.migrate_whole_document_storage import RECOVERY_DIR_NAME, run_migration
from llmwiki.synth.pipeline import synthesize_new_sessions
from tests.test_add_doc import write_legacy_multipart_raw_doc
from tests.test_whole_document_synth import BUDGET, CappedBackend

TODAY = "2026-07-04"
RAW_PIECE = re.compile(r"-\d{2}\.md$")


def _long_markdown(title: str = "Big Doc", sections: int = 4) -> str:
    """A document well over both the old split threshold and the capped backend's budget."""
    slug = title.lower().replace(" ", "-")
    return f"# {title}\n\n" + "".join(
        f"## Sec{i}\n\nMARKER-{slug}-{i} " + "x" * 880 + "\n\n" for i in range(sections)
    )


def _vault(tmp_path: Path) -> dict:
    vault = tmp_path / "vault"
    docs = vault / "raw" / "docs"
    sessions = vault / "raw" / "sessions"
    sources = vault / "wiki" / "sources"
    for d in (docs, sessions, sources):
        d.mkdir(parents=True)
    (vault / "wiki" / "log.md").write_text("# Log\n", encoding="utf-8")
    return {
        "vault": vault,
        "docs": docs,
        "sessions": sessions,
        "sources": sources,
        "synth": dict(
            raw_dir=sessions,
            docs_dir=docs,
            wiki_sources_dir=sources,
            log_path=vault / "wiki" / "log.md",
            state_file=vault / "llmwiki-state.json",
        ),
    }


def _import_doc(v: dict, tmp_path: Path, markdown: str, name: str = "in.md") -> Path:
    src = tmp_path / name
    src.write_text(markdown, encoding="utf-8")
    result = add_sources([str(src)], v["docs"], today=TODAY)
    assert result["errors"] == [] and len(result["written"]) == 1
    return src


def _source_rows(vault: Path) -> list[str]:
    """Wiki (Ctrl+K) corpus rows that are source summaries."""
    return sorted(e["path"] for e in build_wiki_corpus_entries(vault / "wiki") if e["path"].startswith("wiki/sources/"))


def _legacy_vault(tmp_path: Path, *titles: str) -> dict:
    """A pre-#311 vault: each document stored as raw ``-NN`` pieces, each piece summarised separately."""
    v = _vault(tmp_path)
    v["srcs"] = {}
    for title in titles or ("Big Doc",):
        markdown = _long_markdown(title)
        src = tmp_path / f"{title.lower().replace(' ', '-')}.md"
        src.write_text(markdown, encoding="utf-8")
        converted = convert_path(str(src)).markdown        # what `add` hashes for this source
        write_legacy_multipart_raw_doc(
            v["docs"], markdown=converted, title=title, today=TODAY, chunk_max_chars=1000,
        )
        v["srcs"][title] = src
    summary = synthesize_new_sessions(backend=CappedBackend(budget=10_000), **v["synth"])
    assert summary["errors"] == [] and summary["synthesized"] > len(titles)
    return v


def _migrate(vault: Path, *flags: str) -> int:
    args = build_parser().parse_args(["migrate", "whole-document-storage", "--vault", str(vault), *flags])
    return args.func(args)


def _tree(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# ─── new import → one original → one summary → one Wiki row ─────────────


# @regression
def test_long_import_stays_one_original_and_summarises_to_one_page_with_full_coverage(tmp_path: Path):
    """A long import is one stored file whose capped-backend summary covers every section on one canonical page."""
    v = _vault(tmp_path)
    markdown = _long_markdown()
    src = _import_doc(v, tmp_path, markdown)

    raw_files = sorted(v["docs"].rglob("*.md"))
    assert [p.relative_to(v["docs"]).as_posix() for p in raw_files] == ["big-doc/big-doc.md"]
    raw_text = raw_files[0].read_text(encoding="utf-8")
    raw_meta, _ = parse_frontmatter(raw_text)
    assert raw_meta["slug"] == "big-doc" and raw_meta["content_sha256"] == compute_content_hash(convert_path(str(src)).markdown)
    assert "(part " not in raw_text and "> Part " not in raw_text
    assert len(raw_text) > BUDGET * 3, "fixture must be long enough to force several backend calls"

    backend = CappedBackend()
    summary = synthesize_new_sessions(backend=backend, **v["synth"])

    assert summary["errors"] == [] and summary["synthesized"] == 1
    assert len(backend.calls) > 2 and all(len(c) <= BUDGET for c in backend.calls)
    seen = "".join(backend.calls)
    assert all(f"MARKER-big-doc-{i} " in seen for i in range(4)), "a section never reached the backend"
    [page] = sorted(v["sources"].rglob("*.md"))
    page_meta, page_body = parse_frontmatter(page.read_text(encoding="utf-8"))
    assert page_meta["source_file"] == "raw/docs/big-doc/big-doc.md"
    assert all(f"Chunk {n} summary." in page_body for n in range(1, len(backend.calls) + 1))
    assert len(_source_rows(v["vault"])) == 1

    again = add_sources([str(src)], v["docs"], today=TODAY)
    assert again["written"] == [] and again["skipped"], "re-import must be recognised as the same whole document"


# @regression
def test_mid_document_failure_is_a_whole_document_failure_until_a_retry_succeeds(tmp_path: Path):
    """A failed internal piece leaves no page or Wiki row, keeps one pending document, and never clobbers a good page."""
    v = _vault(tmp_path)
    _import_doc(v, tmp_path, _long_markdown())

    failed = synthesize_new_sessions(backend=CappedBackend(fail_on=2), **v["synth"])

    assert failed["synthesized"] == 0 and len(failed["errors"]) == 1
    assert "big-doc" in failed["errors"][0] and "chunk 2/" in failed["errors"][0]
    assert list(v["sources"].rglob("*.md")) == [] and _source_rows(v["vault"]) == []
    dry = synthesize_new_sessions(backend=CappedBackend(), dry_run=True, **v["synth"])
    assert dry["new_files"] == 1, "the failed document must stay pending as one document"

    retry = synthesize_new_sessions(backend=CappedBackend(), **v["synth"])
    assert retry["synthesized"] == 1 and retry["errors"] == []
    [page] = sorted(v["sources"].rglob("*.md"))
    good = page.read_bytes()
    assert len(_source_rows(v["vault"])) == 1

    synthesize_new_sessions(backend=CappedBackend(fail_on=2), force=True, **v["synth"])
    assert page.read_bytes() == good, "a later failed run must not overwrite the complete page"


# ─── legacy vault before migrate ─────────────────────────────────────────


# @regression
def test_legacy_split_vault_still_builds_and_synthesises_before_migrating(tmp_path: Path):
    """Before migrating, a split vault builds, stays pending-free, and keeps its pieces untouched."""
    v = _legacy_vault(tmp_path)
    pieces = sorted(v["docs"].rglob("*.md"))
    assert len(pieces) > 1 and all(RAW_PIECE.search(p.name) for p in pieces)
    assert len(_source_rows(v["vault"])) == len(pieces), "legacy vault shows one summary row per piece"
    before = _tree(v["docs"])

    build_args = build_parser().parse_args(["build", "--vault", str(v["vault"]), "--out", str(tmp_path / "site")])
    assert build_args.func(build_args) == 0
    backend = CappedBackend()
    summary = synthesize_new_sessions(backend=backend, **v["synth"])

    assert summary["errors"] == [] and summary["new_files"] == 0 and backend.calls == []
    assert _tree(v["docs"]) == before
    assert (tmp_path / "site" / "index.html").is_file()


# ─── migrate: preview / block / apply / idempotent / findability ─────────


# @regression
def test_migrate_preview_changes_nothing_and_apply_leaves_one_original_one_page_one_row(tmp_path: Path):
    """Preview is read-only; apply yields one raw file, one summary, one Wiki row, recoverable pieces, and a no-op rerun."""
    v = _legacy_vault(tmp_path, "Big Doc", "Other Doc")
    vault = v["vault"]
    old_rows = _source_rows(vault)
    pieces = {p.relative_to(vault).as_posix(): p.read_bytes() for p in v["docs"].rglob("*.md")}
    before = _tree(vault)

    assert _migrate(vault, "--dry-run") == 0
    assert _tree(vault) == before and not (vault / RECOVERY_DIR_NAME).exists()

    assert _migrate(vault, "--keep-stitched") == 0

    assert sorted(p.relative_to(v["docs"]).as_posix() for p in v["docs"].rglob("*.md")) == [
        "big-doc/big-doc.md", "other-doc/other-doc.md",
    ]
    rows = _source_rows(vault)
    assert len(old_rows) > 2 and len(rows) == 2
    assert not [r for r in rows if RAW_PIECE.search(r)]
    for row in rows:
        page_meta, _ = parse_frontmatter((vault / row).read_text(encoding="utf-8"))
        assert page_meta["source_file"].startswith("raw/docs/") and not RAW_PIECE.search(page_meta["source_file"])
    recovered = {
        p.relative_to(next((vault / RECOVERY_DIR_NAME).iterdir())).as_posix(): p.read_bytes()
        for p in (vault / RECOVERY_DIR_NAME).rglob("*.md")
    }
    assert pieces.items() <= recovered.items(), "every original raw piece must be recoverable byte for byte"

    after_first = _tree(vault)
    assert _migrate(vault, "--keep-stitched") == 0
    assert _tree(vault) == after_first, "a second run must be a no-op"
    assert run_migration(vault=vault, dry_run=True)["groups"] == []


# @regression
def test_migrate_refuses_ambiguous_group_until_resolved_without_touching_clear_groups(tmp_path: Path, capsys):
    """An ambiguous group blocks the whole apply (exit 1, nothing changed) and apply succeeds once it is resolved."""
    v = _legacy_vault(tmp_path, "Big Doc", "Gap Doc")
    vault = v["vault"]
    missing = sorted(v["docs"].rglob("gap-doc-02.md"))[0]
    missing_text = missing.read_text(encoding="utf-8")
    missing.unlink()
    before = _tree(vault)

    assert _migrate(vault, "--dry-run") == 0
    assert "ambiguous" in capsys.readouterr().out
    assert _migrate(vault, "--keep-stitched") == 1
    assert _tree(vault) == before, "a blocked apply must change nothing, not even the clear group"

    missing.write_text(missing_text, encoding="utf-8")
    assert _migrate(vault, "--keep-stitched") == 0
    assert len(_source_rows(vault)) == 2


# @regression
def test_same_document_is_still_a_duplicate_before_and_after_migrating(tmp_path: Path):
    """Re-importing the same document is recognised as one whole document in both the legacy and migrated layout."""
    v = _legacy_vault(tmp_path)
    src = v["srcs"]["Big Doc"]
    before = _tree(v["docs"])

    pre = add_sources([str(src)], v["docs"], today=TODAY)
    assert pre["written"] == [] and pre["skipped"] and _tree(v["docs"]) == before

    assert _migrate(v["vault"], "--keep-stitched") == 0
    migrated = _tree(v["docs"])
    post = add_sources([str(src)], v["docs"], today=TODAY)

    assert post["written"] == [] and post["skipped"]
    assert _tree(v["docs"]) == migrated and list(migrated) == ["big-doc/big-doc.md"]


# ─── --mark-unsynth vs default keep-stitched ─────────────────────────────


# @regression
@pytest.mark.parametrize("flag, requeued", [("--keep-stitched", False), ("--mark-unsynth", True)])
def test_mark_unsynth_requeues_the_document_while_keeping_stitched_leaves_synth_idle(
    tmp_path: Path, flag: str, requeued: bool,
):
    """After migrate, --keep-stitched leaves the stitched page and synth idle, while --mark-unsynth re-summarises the whole doc once."""
    v = _legacy_vault(tmp_path)
    assert _migrate(v["vault"], flag) == 0
    [page] = sorted(v["sources"].rglob("*.md"))
    stitched = page.read_bytes()

    dry = synthesize_new_sessions(backend=CappedBackend(), dry_run=True, **v["synth"])
    assert dry["new_files"] == (1 if requeued else 0)

    backend = CappedBackend(budget=BUDGET)
    summary = synthesize_new_sessions(backend=backend, **v["synth"])

    assert summary["errors"] == []
    assert list(v["sources"].rglob("*.md")) == [page]
    assert len(_source_rows(v["vault"])) == 1
    if requeued:
        assert summary["synthesized"] == 1 and len(backend.calls) > 1
        assert page.read_bytes() != stitched
    else:
        assert backend.calls == [] and page.read_bytes() == stitched


# ─── sessions are out of scope ───────────────────────────────────────────


# @regression
def test_sessions_are_neither_chunked_nor_merged_by_synth_or_migrate(tmp_path: Path):
    """Numbered session files stay byte-identical through migrate and reach synth as one whole call each beside a chunked doc."""
    v = _legacy_vault(tmp_path)
    sess_dir = v["sessions"] / "proj"
    sess_dir.mkdir()
    for n in (1, 2):
        (sess_dir / f"2026-04-09-standup-{n:02d}.md").write_text(
            f"---\nslug: standup-{n:02d}\nproject: proj\ndate: 2026-04-09\n---\n# s\n\n"
            + "\n\n".join(f"turn {i} " + "x" * 200 for i in range(30)) + "\n",
            encoding="utf-8",
        )
    sessions_before = _tree(v["sessions"])

    assert _migrate(v["vault"], "--keep-stitched") == 0
    assert _tree(v["sessions"]) == sessions_before
    assert not [p for p in (v["vault"] / RECOVERY_DIR_NAME).rglob("*") if "standup" in p.name]

    _import_doc(v, tmp_path, _long_markdown("Fresh Doc"), name="fresh.md")
    backend = CappedBackend()
    summary = synthesize_new_sessions(backend=backend, **v["synth"])

    assert summary["errors"] == [] and summary["synthesized"] == 3
    session_calls = [c for c in backend.calls if len(c) > BUDGET]
    doc_calls = [c for c in backend.calls if len(c) <= BUDGET]
    assert len(session_calls) == 2 and all("turn 29" in c for c in session_calls), "each session is one whole call"
    assert len(doc_calls) > 2 and all(f"MARKER-fresh-doc-{i} " in "".join(doc_calls) for i in range(4))
    assert sorted(p.name for p in (v["sources"] / "proj").glob("*.md")) == [
        "2026-04-09-standup-01.md", "2026-04-09-standup-02.md",
    ]
    assert _tree(v["sessions"]).keys() == sessions_before.keys()
    assert run_migration(vault=v["vault"], dry_run=True)["groups"] == []
