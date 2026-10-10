"""``llmwiki migrate whole-document-storage`` — offline merge of split documents (#311).

Every fixture is synthetic. Each vault lives under ``tmp_path``; the log and
state files are the vault's own, so nothing leaks into the repository's
``wiki/``. The migration must never reach a synthesis backend.

Spec: ``context/spec/324-whole-document-storage`` (Slice 4).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.add_doc import compute_content_hash
from llmwiki.build import build_wiki_corpus_entries
from llmwiki.cli import build_parser
from llmwiki.migrate_whole_document_storage import (
    RECOVERY_DIR_NAME,
    _joined_body,
    _plan,
    _rewrite_sources_field,
    print_report,
    run_migration,
)
from llmwiki.state_store import read_state
from llmwiki.synth import base as synth_base
from llmwiki.synth.base import DummySynthesizer
from llmwiki.synth.pipeline import _save_state
from llmwiki.wikilinks import parse_page_aliases, wikilink_targets

DATE = "2026-07-04"
NOW = datetime(2026, 10, 9, 12, 0, 0, tzinfo=UTC)
STAMP = "20261009T120000Z"

RAW_PART = """---
title: "{title} (part {i}/{n}: {sub})"
slug: {slug}-{i:02d}
project: {project}
type: source
tags: [wiki-add, raw-doc{extra_tags}]
date: {date}
source: "docs/{slug}.md"
content_sha256: {sha}
---

> Part {i} of {n} of **{title}** — {sub}.

## {sub}

Body of section {sub} for {slug}.
"""

WIKI_PART = """---
title: "{title} (part {i}/{n}: {sub})"
type: source
tags: [wiki-add, raw-doc, session-transcript, topic-{i}]
date: {date}
source_file: {claim}
project: {project}
model: test-model
last_updated: {date}
---
## Summary

Summary of {sub}.

## Key Claims

- Shared claim about {slug}
- Claim only in part {i}

## Connections

- [[Pytest]] (entity) — the runner, part {i}
- [[Concept{i}]] (concept) — only part {i}
"""

STUB_PAGE = """---
title: "{title} (part {i}/{n}: {sub})"
type: source
tags: [wiki-add, raw-doc]
date: {date}
source_file: {claim}
project: {project}
---
<!-- llmwiki-pending: stub -->
"""


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _legacy_doc(
    vault: Path,
    slug: str = "big-doc",
    *,
    n: int = 3,
    sha: str | None = None,
    project: str | None = None,
    wiki: str = "real",          # real | stub | none
    blank_claims: bool = False,
    skip: tuple[int, ...] = (),
    state: bool = True,
) -> dict[str, list[Path]]:
    """Lay out a pre-#311 split document: raw ``-NN`` pieces, one wiki page each."""
    project = project or slug
    sha = sha or (slug.encode().hex() * 8)[:64]
    title = slug.replace("-", " ").title()
    raw_paths: list[Path] = []
    wiki_paths: list[Path] = []
    files: dict[str, float] = {}
    for i in range(1, n + 1):
        if i in skip:
            continue
        sub = f"Sec{i}"
        extra = ", alpha" if i == 1 else ""
        raw = _write(
            vault / "raw" / "docs" / project / f"{slug}-{i:02d}.md",
            RAW_PART.format(
                title=title, i=i, n=n, sub=sub, slug=slug, project=project,
                date=DATE, sha=sha, extra_tags=extra,
            ),
        )
        raw_paths.append(raw)
        files[f"docs::{project}/{slug}-{i:02d}.md"] = raw.stat().st_mtime
        if wiki == "none":
            continue
        claim = "" if blank_claims else f"raw/docs/{project}/{slug}-{i:02d}.md"
        tpl = WIKI_PART if wiki == "real" else STUB_PAGE
        wiki_paths.append(_write(
            vault / "wiki" / "sources" / project / f"{DATE}-{slug}-{i:02d}.md",
            tpl.format(
                title=title, i=i, n=n, sub=sub, slug=slug, project=project,
                date=DATE, claim=claim,
            ),
        ))
    if state:
        _save_state(files, vault / "llmwiki-state.json")
    return {"raw": raw_paths, "wiki": wiki_paths}


def _referrers(vault: Path, slug: str = "big-doc", n: int = 3) -> None:
    stems = [f"{DATE}-{slug}-{i:02d}" for i in range(1, n + 1)]
    _write(
        vault / "wiki" / "entities" / "Pytest.md",
        "---\ntitle: \"Pytest\"\ntype: entity\ntags: []\n"
        f"sources: [{', '.join(stems)}, 2026-06-30-other]\nlast_updated: {DATE}\n---\n\n"
        "# Pytest\n\n## Connections\n\n"
        f"- [[{stems[0]}]]\n- [[{stems[1]}|second part]]\n"
        f"- [[sources/{slug}/{stems[0]}]]\n",
    )
    _write(
        vault / "wiki" / "projects" / f"{slug}.md",
        f"---\ntitle: \"{slug}\"\ntype: project\ntags: []\n"
        "sources:\n" + "".join(f"  - {s}\n" for s in stems) +
        f"last_updated: {DATE}\n---\n\n# {slug}\n\n## Sessions\n\n- [[{stems[-1]}]]\n",
    )
    _write(
        vault / "wiki" / "index.md",
        f"# Wiki Index\n\n## Sources ({n})\n\n"
        + "".join(f"- [{s}](sources/{slug}/{s}.md) — part\n" for s in stems),
    )
    _write(vault / "wiki" / "log.md", "# Wiki Log\n")


@pytest.fixture(autouse=True)
def _no_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """The migration never reaches a synthesis backend."""

    def _boom(*_a, **_k):
        raise AssertionError("migration must not call a synthesis backend")

    monkeypatch.setattr(synth_base.BaseSynthesizer, "synthesize_source_page", _boom)
    monkeypatch.setattr(DummySynthesizer, "synthesize_source_page", _boom)


def _apply(vault: Path) -> dict:
    return run_migration(vault=vault, now=NOW)


def _unified_state_files(vault: Path) -> dict:
    return read_state(vault / "llmwiki-state.json")["synth"]["files"]


# ─── preview ─────────────────────────────────────────────────────────────


def test_preview_lists_groups_and_writes_nothing(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault)
    _referrers(vault)
    before = _snapshot(vault)

    report = run_migration(vault=vault, dry_run=True, now=NOW)

    assert _snapshot(vault) == before
    assert not (vault / RECOVERY_DIR_NAME).exists()
    assert report["dry_run"] and report["changed"] and not report["blocked"]
    [group] = report["groups"]
    assert group["status"] == "clear"
    assert group["parts"] == [f"big-doc/big-doc-0{i}.md" for i in (1, 2, 3)]
    assert group["whole_raw"] == "raw/docs/big-doc/big-doc.md"
    assert group["canonical_page"] == f"sources/big-doc/{DATE}-big-doc.md"
    assert len(group["wiki_pages"]) == 3
    print_report(report)
    out = capsys.readouterr().out
    assert "preview (no changes made)" in out and "big-doc/big-doc" in out


def test_preview_with_ambiguous_group_lists_it_and_exits_zero(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault, "gappy", skip=(2,))
    args = build_parser().parse_args(
        ["migrate", "whole-document-storage", "--vault", str(vault), "--dry-run"]
    )
    before = _snapshot(vault)

    assert args.func(args) == 0
    report = run_migration(vault=vault, dry_run=True)
    assert [g["status"] for g in report["groups"]] == ["ambiguous"]
    assert any("gap" in r for r in report["groups"][0]["reasons"])
    assert _snapshot(vault) == before


# ─── blocked: ambiguous groups change nothing ────────────────────────────


def _vault_with_clear_and_ambiguous(tmp_path: Path, make_ambiguous) -> Path:
    vault = tmp_path / "vault"
    _legacy_doc(vault, "clear-doc")
    _referrers(vault, "clear-doc")
    make_ambiguous(vault)
    return vault


def _gap(vault: Path) -> None:
    _legacy_doc(vault, "gappy", skip=(2,))


def _hash_conflict(vault: Path) -> None:
    _legacy_doc(vault, "conflicted")
    p = vault / "raw" / "docs" / "conflicted" / "conflicted-02.md"
    p.write_text(
        p.read_text(encoding="utf-8").replace(
            "content_sha256: ", "content_sha256: ffff", 1
        ),
        encoding="utf-8",
    )


def _whole_clash(vault: Path) -> None:
    _legacy_doc(vault, "clashing")
    _write(
        vault / "raw" / "docs" / "clashing" / "clashing.md",
        '---\ntitle: "Other"\nslug: clashing\nproject: clashing\ncontent_sha256: abc123\n---\n\nunrelated\n',
    )


def _partly_summarised(vault: Path) -> None:
    docs = _legacy_doc(vault, "partial")
    docs["wiki"][1].unlink()


def _page_claims_elsewhere(vault: Path) -> None:
    docs = _legacy_doc(vault, "misclaimed")
    page = docs["wiki"][0]
    page.write_text(
        page.read_text(encoding="utf-8").replace(
            "source_file: raw/docs/misclaimed/misclaimed-01.md",
            "source_file: raw/docs/somewhere/else-01.md",
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("make_ambiguous", "needle"),
    [
        (_gap, "gap"),
        (_hash_conflict, "content_sha256"),
        (_whole_clash, "different content_sha256"),
        (_partly_summarised, "cover only some pieces"),
        (_page_claims_elsewhere, "claims raw/docs/somewhere/else-01.md"),
    ],
    ids=["gap", "hash-conflict", "whole-file-clash", "partly-summarised", "wiki-claim"],
)
def test_apply_blocked_by_ambiguous_group_changes_nothing(
    tmp_path: Path, make_ambiguous, needle: str, capsys
) -> None:
    vault = _vault_with_clear_and_ambiguous(tmp_path, make_ambiguous)
    before = _snapshot(vault)

    report = _apply(vault)

    assert report["blocked"] and not report["changed"]
    assert _snapshot(vault) == before          # not even the clear group moved
    reasons = [r for g in report["ambiguous"] for r in g["reasons"]]
    assert any(needle in r for r in reasons), reasons
    assert {g["key"] for g in report["groups"] if g["status"] == "clear"} == {"clear-doc/clear-doc"}
    print_report(report)
    out = capsys.readouterr().out
    assert "blocked: nothing was changed (including clear groups)" in out
    assert "What to do:" in out


def test_cli_apply_exits_non_zero_when_blocked(tmp_path: Path) -> None:
    vault = _vault_with_clear_and_ambiguous(tmp_path, _gap)
    before = _snapshot(vault)
    args = build_parser().parse_args(
        ["migrate", "whole-document-storage", "--vault", str(vault)]
    )

    assert args.func(args) == 1
    assert _snapshot(vault) == before


def test_numbered_files_without_part_markers_are_separate_documents(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    for i in (1, 2):
        _write(
            vault / "raw" / "docs" / "book" / f"chapter-{i:02d}.md",
            f'---\ntitle: "Chapter {i:02d}"\nslug: chapter-{i:02d}\nproject: book\n'
            f"content_sha256: {i}abc\n---\n\ntext {i}\n",
        )
    before = _snapshot(vault)

    report = _apply(vault)

    assert report["groups"] == [] and not report["blocked"] and not report["changed"]
    assert _snapshot(vault) == before


# ─── pre-hash part groups (all content_sha256 empty) ─────────────────────


def _strip_content_hashes(vault: Path, slug: str) -> None:
    """Drop content_sha256 from every raw piece (pre-hash import shape)."""
    for path in (vault / "raw" / "docs" / slug).glob(f"{slug}-*.md"):
        text = path.read_text(encoding="utf-8")
        path.write_text(
            "\n".join(line for line in text.splitlines() if not line.startswith("content_sha256:"))
            + "\n",
            encoding="utf-8",
        )


def test_pre_hash_part_group_applies_and_fills_content_hash(tmp_path: Path) -> None:
    """All-empty content_sha256 with clear (part i/N) markers is clear, not ambiguous."""
    vault = tmp_path / "vault"
    _legacy_doc(vault, "legacy-cv", n=2)
    _strip_content_hashes(vault, "legacy-cv")
    for path in (vault / "raw" / "docs" / "legacy-cv").glob("*.md"):
        assert "content_sha256" not in path.read_text(encoding="utf-8")
    [group] = _plan(vault, [])
    assert not group.ambiguous
    expected_hash = compute_content_hash(_joined_body(group))

    report = _apply(vault)

    assert not report["blocked"] and report["applied"] == ["legacy-cv/legacy-cv"]
    whole = vault / "raw" / "docs" / "legacy-cv" / "legacy-cv.md"
    meta, body = parse_frontmatter(whole.read_text(encoding="utf-8"))
    assert meta["content_sha256"] == expected_hash
    assert "Body of section Sec1" in body and "Body of section Sec2" in body


def test_mixed_empty_and_nonempty_hashes_still_ambiguous(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault, "mixed-hash")
    p = vault / "raw" / "docs" / "mixed-hash" / "mixed-hash-02.md"
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if not ln.startswith("content_sha256:")]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = _apply(vault)

    assert report["blocked"]
    reasons = [r for g in report["ambiguous"] for r in g["reasons"]]
    assert any("content_sha256" in r and "<none>" in r for r in reasons), reasons


def test_whole_file_without_hash_matching_body_is_clear(tmp_path: Path) -> None:
    """Empty vs empty is not a clash when the whole body's hash matches the joined parts."""
    vault = tmp_path / "vault"
    _legacy_doc(vault, "prehash-whole", n=2)
    _strip_content_hashes(vault, "prehash-whole")
    [group] = _plan(vault, [])
    joined = _joined_body(group)
    whole_text = (
        '---\ntitle: "Prehash Whole"\nslug: prehash-whole\nproject: prehash-whole\n'
        "---\n\n" + joined + "\n"
    )
    _write(vault / "raw" / "docs" / "prehash-whole" / "prehash-whole.md", whole_text)

    report = _apply(vault)

    assert not report["blocked"] and report["applied"] == ["prehash-whole/prehash-whole"]
    assert not (vault / "raw/docs/prehash-whole/prehash-whole-01.md").exists()
    assert (vault / "raw/docs/prehash-whole/prehash-whole.md").read_text(encoding="utf-8") == whole_text


# ─── happy path ──────────────────────────────────────────────────────────


def test_happy_path_merges_raw_and_wiki(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    docs = _legacy_doc(vault)
    _referrers(vault)
    originals = {p.relative_to(vault).as_posix(): p.read_bytes() for p in docs["raw"] + docs["wiki"]}
    sha = parse_frontmatter(docs["raw"][0].read_text(encoding="utf-8"))[0]["content_sha256"]

    report = _apply(vault)

    assert report["applied"] == ["big-doc/big-doc"] and not report["errors"]

    # raw: one whole file, same hash, no part chrome, every piece's text kept
    raw_dir = vault / "raw" / "docs" / "big-doc"
    assert sorted(p.name for p in raw_dir.iterdir()) == ["big-doc.md"]
    meta, body = parse_frontmatter((raw_dir / "big-doc.md").read_text(encoding="utf-8"))
    assert meta["content_sha256"] == sha
    assert meta["slug"] == "big-doc" and meta["title"] == "Big Doc"
    assert meta["tags"] == ["wiki-add", "raw-doc", "alpha"]
    assert "> Part " not in body and "(part " not in str(meta["title"])
    for i in (1, 2, 3):
        assert f"Body of section Sec{i} for big-doc." in body
    assert body.index("Sec1") < body.index("Sec2") < body.index("Sec3")

    # wiki: exactly one real page with the stitched prose and unioned tags
    pages = sorted((vault / "wiki" / "sources" / "big-doc").glob("*.md"))
    assert [p.name for p in pages] == [f"{DATE}-big-doc.md"]
    page_meta, page_body = parse_frontmatter(pages[0].read_text(encoding="utf-8"))
    assert page_meta["source_file"] == "raw/docs/big-doc/big-doc.md"
    assert page_meta["title"] == "Big Doc" and page_meta["project"] == "big-doc"
    assert page_meta["tags"] == [
        "wiki-add", "raw-doc", "session-transcript", "topic-1", "topic-2", "topic-3",
    ]
    for i in (1, 2, 3):
        assert f"Summary of Sec{i}." in page_body
    assert page_body.count("Shared claim about big-doc") == 1          # exact-string dedupe
    assert all(f"Claim only in part {i}" in page_body for i in (1, 2, 3))
    assert page_body.count("[[Pytest]]") == 1                          # connections by target
    assert all(f"[[Concept{i}]]" in page_body for i in (1, 2, 3))
    assert parse_page_aliases(page_body) == [f"{DATE}-big-doc-0{i}" for i in (1, 2, 3)]

    # links and sources: follow to the canonical page; no part name stays live
    canonical = f"{DATE}-big-doc"
    entity = (vault / "wiki" / "entities" / "Pytest.md").read_text(encoding="utf-8")
    assert f"sources: [{canonical}, 2026-06-30-other]" in entity
    assert f"[[{canonical}|{DATE}-big-doc-01]]" in entity
    assert f"[[{canonical}|second part]]" in entity
    assert wikilink_targets(entity) == {canonical}
    project = (vault / "wiki" / "projects" / "big-doc.md").read_text(encoding="utf-8")
    assert project.count(f"  - {canonical}\n") == 1        # block list deduped to one entry
    assert wikilink_targets(project) == {canonical}
    assert report["links_rewritten"] >= 4 and report["pages_rewritten"] >= 2

    # index: one entry for the document
    index = (vault / "wiki" / "index.md").read_text(encoding="utf-8")
    assert index.count(f"sources/big-doc/{canonical}.md") == 1
    assert "-01.md" not in index

    # state: part keys gone, whole key present, nothing pending for this doc
    files = _unified_state_files(vault)
    assert [k for k in files if k.startswith("docs::big-doc/")] == ["docs::big-doc/big-doc.md"]
    pending = read_state(vault / "llmwiki-state.json")["synth"]["pending"]
    assert not [p for p in pending if "big-doc" in p["rel"]]
    assert "migrate | whole-document storage" in (vault / "wiki" / "log.md").read_text(encoding="utf-8")

    # recovery: originals are all still there, byte for byte
    recovery = vault / RECOVERY_DIR_NAME / STAMP
    assert report["recovery_dir"] == f"{RECOVERY_DIR_NAME}/{STAMP}"
    for rel, data in originals.items():
        assert (recovery / rel).read_bytes() == data
        assert not (vault / rel).exists()
    manifest = json.loads((recovery / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["migration"] == "whole-document-storage"
    assert {m["from"] for m in manifest["moves"]} == set(originals)
    assert set(manifest["state_removed"]) == {f"docs::big-doc/big-doc-0{i}.md" for i in (1, 2, 3)}


def test_blank_source_file_claims_are_found_by_derived_page_name(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault, blank_claims=True)

    report = _apply(vault)

    assert report["applied"] == ["big-doc/big-doc"]
    [page] = (vault / "wiki" / "sources" / "big-doc").glob("*.md")
    assert "Summary of Sec2." in page.read_text(encoding="utf-8")


def test_stub_only_pages_are_relocated_and_the_whole_file_stays_pending(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault, wiki="stub")
    _write(vault / "wiki" / "log.md", "# Wiki Log\n")

    report = _apply(vault)

    assert report["applied"] == ["big-doc/big-doc"]
    assert list((vault / "wiki" / "sources" / "big-doc").glob("*.md")) == []
    assert "docs::big-doc/big-doc.md" not in _unified_state_files(vault)
    pending = read_state(vault / "llmwiki-state.json")["synth"]["pending"]
    assert [p["rel"] for p in pending] == ["docs::big-doc/big-doc.md"]


def test_no_wiki_pages_still_merges_the_raw_pieces(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault, wiki="none", state=False)

    report = _apply(vault)

    assert report["applied"] == ["big-doc/big-doc"]
    assert (vault / "raw" / "docs" / "big-doc" / "big-doc.md").is_file()
    assert not (vault / "raw" / "docs" / "big-doc" / "big-doc-01.md").exists()


def test_real_canonical_page_is_kept_and_only_aliased(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault)
    canonical = _write(
        vault / "wiki" / "sources" / "big-doc" / f"{DATE}-big-doc.md",
        '---\ntitle: "Big Doc"\ntype: source\ntags: [curated]\n'
        f"date: {DATE}\nsource_file: raw/docs/big-doc/big-doc.md\nproject: big-doc\n---\n"
        "## Summary\n\nHand-curated whole-document summary.\n",
    )
    _write(
        vault / "raw" / "docs" / "big-doc" / "big-doc.md",
        '---\ntitle: "Big Doc"\nslug: big-doc\nproject: big-doc\n'
        f"content_sha256: {parse_frontmatter((vault / 'raw/docs/big-doc/big-doc-01.md').read_text())[0]['content_sha256']}\n"
        "---\n\nwhole\n",
    )

    report = _apply(vault)

    assert report["applied"] == ["big-doc/big-doc"]
    text = canonical.read_text(encoding="utf-8")
    assert "Hand-curated whole-document summary." in text and "tags: [curated]" in text
    assert parse_page_aliases(text) == [f"{DATE}-big-doc-0{i}" for i in (1, 2, 3)]
    assert "docs::big-doc/big-doc.md" in _unified_state_files(vault)
    # an existing whole raw file with the same hash is not rewritten
    assert (vault / "raw/docs/big-doc/big-doc.md").read_text(encoding="utf-8").endswith("whole\n")


# ─── recovery + safety ───────────────────────────────────────────────────


def test_whole_file_with_other_hash_is_never_clobbered(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault)
    whole = _write(
        vault / "raw" / "docs" / "big-doc" / "big-doc.md",
        '---\ntitle: "Mine"\nslug: big-doc\ncontent_sha256: 0000\n---\n\nprecious\n',
    )

    report = _apply(vault)

    assert report["blocked"]
    assert whole.read_text(encoding="utf-8").endswith("precious\n")
    assert (vault / "raw/docs/big-doc/big-doc-01.md").is_file()
    assert not (vault / RECOVERY_DIR_NAME).exists()


def test_recovery_folder_per_run_never_reuses_a_stamp(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault, "first-doc")
    _apply(vault)
    _legacy_doc(vault, "second-doc")

    report = _apply(vault)        # same ``now`` — a second folder, not a merge into the first

    assert report["recovery_dir"] == f"{RECOVERY_DIR_NAME}/{STAMP}-2"
    assert (vault / RECOVERY_DIR_NAME / STAMP).is_dir()


def test_interrupted_run_resumes(tmp_path: Path) -> None:
    """Whole raw file already written (same hash), pieces still present → finish the move."""
    vault = tmp_path / "vault"
    docs = _legacy_doc(vault)
    sha = parse_frontmatter(docs["raw"][0].read_text(encoding="utf-8"))[0]["content_sha256"]
    _write(
        vault / "raw" / "docs" / "big-doc" / "big-doc.md",
        f'---\ntitle: "Big Doc"\nslug: big-doc\nproject: big-doc\ncontent_sha256: {sha}\n---\n\nbody\n',
    )

    preview = run_migration(vault=vault, dry_run=True)
    assert preview["groups"][0]["whole_raw_exists"] and preview["groups"][0]["status"] == "clear"

    report = _apply(vault)

    assert report["applied"] == ["big-doc/big-doc"]
    assert sorted(p.name for p in (vault / "raw/docs/big-doc").iterdir()) == ["big-doc.md"]
    assert len(list((vault / "wiki/sources/big-doc").glob("*.md"))) == 1


# ─── idempotence ─────────────────────────────────────────────────────────


def test_second_run_is_a_no_op(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault)
    _referrers(vault)
    first = _apply(vault)
    assert first["changed"]
    after_first = _snapshot(vault)
    canonical = (vault / "wiki/sources/big-doc" / f"{DATE}-big-doc.md").read_text(encoding="utf-8")

    second = _apply(vault)

    assert not second["changed"] and second["groups"] == [] and not second["errors"]
    assert _snapshot(vault) == after_first
    assert (vault / "wiki/sources/big-doc" / f"{DATE}-big-doc.md").read_text(encoding="utf-8") == canonical
    print_report(second)
    assert "nothing to migrate" in capsys.readouterr().out


# ─── Wiki findability ────────────────────────────────────────────────────


def test_wiki_corpus_has_one_source_row_per_logical_document(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault)
    _referrers(vault)
    _legacy_doc(vault, "other-doc", n=2)

    def _rows() -> list[str]:
        entries = build_wiki_corpus_entries(vault / "wiki")
        return sorted(e["path"] for e in entries if e["path"].startswith("wiki/sources/"))

    assert len(_rows()) == 5                      # 3 + 2 part pages before the migration

    _apply(vault)

    assert _rows() == [
        f"wiki/sources/big-doc/{DATE}-big-doc.md",
        f"wiki/sources/other-doc/{DATE}-other-doc.md",
    ]
    assert not [r for r in _rows() if "--part-" in r or r[-5:-3].isdigit()]


# ─── CLI wiring ──────────────────────────────────────────────────────────


def test_migrate_list_and_help_describe_the_migration(capsys) -> None:
    args = build_parser().parse_args(["migrate", "--list"])

    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "whole-document-storage" in out
    assert ".llmwiki-whole-doc-recovery" in out and "ambiguous" in out


def test_cli_requires_a_vault() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["migrate", "whole-document-storage"])


def test_cli_apply_merges_and_exits_zero(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault)
    args = build_parser().parse_args(
        ["migrate", "whole-document-storage", "--vault", str(vault)]
    )

    assert args.func(args) == 0
    assert "merged:  1 document(s)" in capsys.readouterr().out
    assert (vault / "raw/docs/big-doc/big-doc.md").is_file()


# ─── optional re-synth queue (mark-unsynth) ──────────────────────────────

WHOLE_KEY = "docs::big-doc/big-doc.md"


def _pending_rels(vault: Path) -> list[str]:
    return [str(it.get("rel")) for it in read_state(vault / "llmwiki-state.json")["synth"].get("pending", [])]


def _migrate_args(vault: Path, *extra: str):
    return build_parser().parse_args(["migrate", "whole-document-storage", "--vault", str(vault), *extra])


def _tty(monkeypatch: pytest.MonkeyPatch, *answers: str) -> list[str]:
    """Pretend stdin is a terminal and feed ``answers`` (EOF once exhausted)."""
    queue = list(answers)
    prompts: list[str] = []

    def _input(prompt: str = "") -> str:
        prompts.append(prompt)
        if not queue:
            raise EOFError
        return queue.pop(0)

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", _input)
    return prompts


def test_non_tty_default_keeps_synth_done_state(tmp_path: Path, monkeypatch, capsys) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    args = _migrate_args(vault)
    assert args.func(args) == 0

    assert WHOLE_KEY in _unified_state_files(vault)
    assert _pending_rels(vault) == []
    assert "--mark-unsynth" in capsys.readouterr().out


def test_mark_unsynth_flag_clears_whole_keys_without_prompt(tmp_path: Path, monkeypatch, capsys) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault)
    _legacy_doc(vault, "other-doc")
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    args = _migrate_args(vault, "--mark-unsynth")
    assert args.func(args) == 0

    files = _unified_state_files(vault)
    assert WHOLE_KEY not in files and "docs::other-doc/other-doc.md" not in files
    assert not [k for k in files if k.startswith("docs::") and "-0" in k]
    assert sorted(_pending_rels(vault)) == ["docs::big-doc/big-doc.md", "docs::other-doc/other-doc.md"]
    out = capsys.readouterr().out
    assert "raw/docs/big-doc/big-doc.md" in out and "marked 2 document(s)" in out
    # migrate result itself is untouched: one stitched page, no part pages
    assert [p.name for p in (vault / "wiki/sources/big-doc").glob("*.md")] == [f"{DATE}-big-doc.md"]


def test_tty_yes_marks_all_unsynth(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault)
    prompts = _tty(monkeypatch, "y")

    args = _migrate_args(vault)
    assert args.func(args) == 0

    assert len(prompts) == 1
    assert WHOLE_KEY not in _unified_state_files(vault)
    assert _pending_rels(vault) == [WHOLE_KEY]


@pytest.mark.parametrize("answers", [("n",), ("",), ()], ids=["no", "empty", "eof"])
def test_tty_no_empty_or_eof_keeps_state(tmp_path: Path, monkeypatch, answers: tuple[str, ...]) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault)
    prompts = _tty(monkeypatch, *answers)

    args = _migrate_args(vault)
    assert args.func(args) == 0

    assert len(prompts) == 1
    assert WHOLE_KEY in _unified_state_files(vault)


def test_keep_stitched_flag_never_prompts(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault)
    prompts = _tty(monkeypatch, "y")

    args = _migrate_args(vault, "--keep-stitched")
    assert args.func(args) == 0

    assert prompts == [] and WHOLE_KEY in _unified_state_files(vault)


def test_dry_run_and_blocked_never_prompt_or_mark(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault)
    _legacy_doc(vault, "gap-doc", skip=(2,))  # ambiguous: a gap in the parts
    prompts = _tty(monkeypatch, "y")
    before = _snapshot(vault)

    for extra in (("--dry-run", "--mark-unsynth"), ("--mark-unsynth",)):
        args = _migrate_args(vault, *extra)
        assert args.func(args) == (0 if "--dry-run" in extra else 1)

    assert prompts == [] and _snapshot(vault) == before


def test_mark_unsynth_and_keep_stitched_are_exclusive(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        _migrate_args(tmp_path, "--mark-unsynth", "--keep-stitched")


# ─── path safety + raw overwrite guard (review B1 / B2) ──────────────────


def _rewrite_part_frontmatter(vault: Path, old: str, new: str) -> None:
    for raw in (vault / "raw" / "docs" / "big-doc").glob("big-doc-0*.md"):
        raw.write_text(raw.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")


@pytest.mark.parametrize(
    ("old", "new", "needle"),
    [
        ("project: big-doc", "project: ../escape", "project '../escape' is not a safe path segment"),
        ("project: big-doc", "project: ..", "project '..' is not a safe path segment"),
        ("project: big-doc", "project: a/b", "project 'a/b' is not a safe path segment"),
        (f"date: {DATE}", "date: ../x", "date '../x' is not a safe path segment"),
    ],
    ids=["dotdot-escape", "dotdot", "slash", "date-escape"],
)
def test_unsafe_project_or_date_is_ambiguous_and_nothing_is_written(
    tmp_path: Path, old: str, new: str, needle: str
) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault)
    _referrers(vault)
    _rewrite_part_frontmatter(vault, old, new)
    before = _snapshot(tmp_path)

    preview = run_migration(vault=vault, dry_run=True, now=NOW)
    report = _apply(vault)

    reasons = [r for g in preview["ambiguous"] for r in g["reasons"]]
    assert any(needle in r for r in reasons), reasons
    assert report["blocked"] and not report["changed"]
    assert _snapshot(tmp_path) == before          # nothing written, anywhere, not even a sibling dir
    assert not (vault / "wiki" / "escape").exists()


def test_containment_check_rejects_a_target_that_resolves_outside_the_vault_roots(
    tmp_path: Path,
) -> None:
    """A symlinked project dir under wiki/sources must not let the canonical page land elsewhere."""
    vault = tmp_path / "vault"
    _legacy_doc(vault, wiki="none")
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (vault / "wiki" / "sources").mkdir(parents=True)
    (vault / "wiki" / "sources" / "big-doc").symlink_to(outside, target_is_directory=True)

    report = _apply(vault)

    assert report["blocked"]
    assert any("outside wiki/sources" in r for g in report["ambiguous"] for r in g["reasons"])
    assert list(outside.iterdir()) == []


def test_undecodable_whole_file_is_ambiguous_and_never_overwritten(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _legacy_doc(vault)
    whole = vault / "raw" / "docs" / "big-doc" / "big-doc.md"
    whole.write_bytes(b"\xff\xfe\x00 not utf-8 \x80")
    before = _snapshot(vault)

    preview = run_migration(vault=vault, dry_run=True, now=NOW)
    report = _apply(vault)

    reasons = [r for g in preview["ambiguous"] for r in g["reasons"]]
    assert any("cannot be read as UTF-8 Markdown" in r for r in reasons), reasons
    assert report["blocked"] and not report["changed"]
    assert whole.read_bytes() == b"\xff\xfe\x00 not utf-8 \x80"
    assert _snapshot(vault) == before
    assert not (vault / RECOVERY_DIR_NAME).exists()


def test_whole_file_that_appears_after_planning_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exclusive create: a whole file the plan did not see is left byte-for-byte alone."""
    vault = tmp_path / "vault"
    _legacy_doc(vault)
    whole = _write(vault / "raw" / "docs" / "big-doc" / "big-doc.md", "late arrival\n")
    real_lexists = os.path.lexists
    monkeypatch.setattr(
        os.path, "lexists", lambda p: False if str(p).endswith("big-doc.md") else real_lexists(p)
    )

    report = _apply(vault)

    assert whole.read_text(encoding="utf-8") == "late arrival\n"
    assert any("appeared during apply" in e for e in report["errors"]), report["errors"]
    assert report["applied"] == []
    assert (vault / "raw/docs/big-doc/big-doc-01.md").is_file()      # pieces untouched


def test_shared_sources_rewriter_collapses_part_stems_in_block_and_inline_lists() -> None:
    mapping = {"s-01": "s", "s-02": "s", "s-03": "s"}
    inline = "---\nsources: [s-01, 's-02', other, s-03]\n---\nbody\n"
    block = "---\nsources:\n  - s-01\n  - s-02\n  - other\nx: 1\n---\n"

    assert _rewrite_sources_field(inline, mapping) == "---\nsources: [s, other]\n---\nbody\n"
    assert _rewrite_sources_field(block, mapping) == "---\nsources:\n  - s\n  - other\nx: 1\n---\n"
