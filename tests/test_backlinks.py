"""Tests for ``llmwiki/backlinks.py`` + ``llmwiki backlinks`` CLI (#328).

Covers:
* Sentinel-bounded block insertion + idempotent replacement
* Reverse-index construction (dedup, self-link skip, anchor strip)
* Sort order (newest-first when date present, alphabetical fallback)
* Max-entries truncation + footer note
* Prune removes every block
* Archive subtree + ``_context.md`` stubs are skipped
* Injection preserves pre-existing content above the block
* CLI --dry-run never writes
* CLI --prune strips
* CLI --verbose prints top-N
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from llmwiki import backlinks as b

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "llmwiki", *args],
        capture_output=True,
        text=True,
        check=False,
    )


# ─── Sentinel handling ──────────────────────────────────────────────────


def test_inject_block_when_no_existing_section():
    text = "---\ntitle: X\n---\n\nBody content.\n"
    out = b.inject_block(text, "<!-- BACKLINKS:START -->\n## Referenced by\n- [[a]]\n<!-- BACKLINKS:END -->\n")
    assert "Body content." in out
    assert "## Referenced by" in out
    assert out.rstrip().endswith("<!-- BACKLINKS:END -->")


def test_inject_block_idempotent_replace():
    original = "Body\n\n<!-- BACKLINKS:START -->\n## Referenced by\n- [[old]]\n<!-- BACKLINKS:END -->\n"
    new_block = "<!-- BACKLINKS:START -->\n## Referenced by\n- [[new]]\n<!-- BACKLINKS:END -->\n"
    out = b.inject_block(original, new_block)
    assert "[[new]]" in out
    assert "[[old]]" not in out
    # Only one sentinel pair.
    assert out.count("<!-- BACKLINKS:START -->") == 1


def test_inject_preserves_content_above():
    text = "# Title\n\nPreserved prose.\n\n## Connections\n- [[Foo]]\n"
    block = "<!-- BACKLINKS:START -->\n## Referenced by\n- [[bar]]\n<!-- BACKLINKS:END -->\n"
    out = b.inject_block(text, block)
    assert "Preserved prose." in out
    assert "## Connections" in out
    assert "[[Foo]]" in out
    assert "[[bar]]" in out


def test_remove_block_strips_sentinels():
    text = "Body\n\n<!-- BACKLINKS:START -->\n## Referenced by\n- [[a]]\n<!-- BACKLINKS:END -->\n"
    out = b.remove_block(text)
    assert "BACKLINKS" not in out
    assert "Body" in out


def test_remove_block_is_noop_when_absent():
    text = "Just body\n"
    assert b.remove_block(text) == text


# ─── Reverse-index ──────────────────────────────────────────────────────


def _page(title, body, date=""):
    fm = f"title: {title}\n"
    if date:
        fm += f"date: {date}\n"
    return {"meta": {"title": title, "date": date},
            "body": body,
            "text": f"---\n{fm}---\n{body}"}


def test_build_reverse_index_basic():
    pages = {
        "a": _page("A", "Links to [[b]]."),
        "b": _page("B", ""),
    }
    rev = b.build_reverse_index(pages)
    assert "b" in rev
    assert len(rev["b"]) == 1
    assert rev["b"][0].slug == "a"


def test_build_reverse_index_skips_self_links():
    pages = {"a": _page("A", "Self [[a]]")}
    rev = b.build_reverse_index(pages)
    assert rev.get("a") is None or rev["a"] == []


def test_build_reverse_index_dedupes_multiple_hits():
    pages = {
        "a": _page("A", "[[b]] and [[b]] again"),
        "b": _page("B", ""),
    }
    rev = b.build_reverse_index(pages)
    assert len(rev["b"]) == 1


def test_build_reverse_index_strips_anchor_suffix():
    pages = {
        "a": _page("A", "[[b#section]]"),
        "b": _page("B", ""),
    }
    rev = b.build_reverse_index(pages)
    assert "b" in rev


def test_build_reverse_index_counts_multiple_referrers():
    pages = {
        "a": _page("A", "[[b]]"),
        "c": _page("C", "[[b]]"),
        "b": _page("B", ""),
    }
    rev = b.build_reverse_index(pages)
    assert len(rev["b"]) == 2


def test_build_reverse_index_resolves_merged_alias() -> None:  # @regression
    """#139: [[Tailnet]] inbound links attribute to canonical Tailscale."""
    # @layer: unit  # @spec: 139-candidates-merge-aliases
    pages = {
        "Tailscale": _page(
            "Tailscale",
            "## Aliases\n\n- Tailnet — merged 2026-08-27 (2 source pages)\n",
        ),
        "older": _page("Older", "Still cites [[Tailnet]]."),
    }
    rev = b.build_reverse_index(pages)
    assert "Tailnet" not in rev
    assert len(rev["Tailscale"]) == 1
    assert rev["Tailscale"][0].slug == "older"


# ─── Render + sort ──────────────────────────────────────────────────────


def test_render_block_sorts_newest_first_by_date():
    entries = [
        b.BacklinkEntry(slug="old", title="Old", date="2026-01-01"),
        b.BacklinkEntry(slug="new", title="New", date="2026-04-01"),
    ]
    block = b._render_block(entries, max_entries=50)
    new_idx = block.index("[[new]]")
    old_idx = block.index("[[old]]")
    assert new_idx < old_idx


def test_render_block_truncates_and_adds_footer():
    entries = [
        b.BacklinkEntry(slug=f"s{i}", title=f"S{i}", date=f"2026-04-{i:02d}")
        for i in range(1, 11)
    ]
    block = b._render_block(entries, max_entries=3)
    assert block.count("[[s") == 3
    assert "and 7 more referrer" in block
    assert "llmwiki references" in block


def test_render_block_no_footer_when_under_cap():
    entries = [b.BacklinkEntry(slug="a", title="A", date="")]
    block = b._render_block(entries, max_entries=50)
    assert "more referrer" not in block


def test_render_block_has_sentinels():
    block = b._render_block([b.BacklinkEntry("a", "A", "")], max_entries=50)
    assert block.startswith("<!-- BACKLINKS:START -->")
    assert "<!-- BACKLINKS:END -->" in block


def test_render_block_includes_title_and_date_when_present():
    block = b._render_block(
        [b.BacklinkEntry("slug", "A session", "2026-04-01")],
        max_entries=50,
    )
    assert "A session" in block
    assert "2026-04-01" in block


# ─── inject_all / prune_all file-system integration ─────────────────────


def _mk_wiki(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "sources").mkdir(parents=True)
    (wiki / "entities" / "X.md").write_text(
        "---\ntitle: X\n---\n\n# X\n\nBody.\n",
        encoding="utf-8",
    )
    (wiki / "sources" / "s1.md").write_text(
        "---\ntitle: S1\ndate: 2026-04-17\n---\n\nReferences [[X]]\n",
        encoding="utf-8",
    )
    (wiki / "sources" / "s2.md").write_text(
        "---\ntitle: S2\ndate: 2026-04-19\n---\n\nAlso links [[X]]\n",
        encoding="utf-8",
    )
    return wiki


def test_inject_all_writes_to_target(tmp_path):
    wiki = _mk_wiki(tmp_path)
    results = b.inject_all(wiki)
    assert results == {"X": 2}
    text = (wiki / "entities" / "X.md").read_text(encoding="utf-8")
    assert "<!-- BACKLINKS:START -->" in text
    assert "[[s1]]" in text
    assert "[[s2]]" in text
    # Sort by date desc: s2 (2026-04-19) before s1 (2026-04-17).
    assert text.index("[[s2]]") < text.index("[[s1]]")


def test_inject_all_is_idempotent(tmp_path):
    wiki = _mk_wiki(tmp_path)
    b.inject_all(wiki)
    b.inject_all(wiki)
    text = (wiki / "entities" / "X.md").read_text(encoding="utf-8")
    assert text.count("<!-- BACKLINKS:START -->") == 1


def test_inject_all_dry_run_doesnt_write(tmp_path):
    wiki = _mk_wiki(tmp_path)
    before = (wiki / "entities" / "X.md").read_text(encoding="utf-8")
    b.inject_all(wiki, dry_run=True)
    after = (wiki / "entities" / "X.md").read_text(encoding="utf-8")
    assert before == after


def test_inject_all_skips_archive(tmp_path):
    wiki = _mk_wiki(tmp_path)
    arch = wiki / "archive" / "candidates"
    arch.mkdir(parents=True)
    (arch / "old.md").write_text(
        "---\ntitle: Old\n---\nLinks to [[X]]\n", encoding="utf-8"
    )
    results = b.inject_all(wiki)
    # Archive's out-link doesn't count.
    assert results.get("X") == 2
    assert "[[old]]" not in (wiki / "entities" / "X.md").read_text(encoding="utf-8")


def test_inject_all_skips_context_stubs(tmp_path):
    wiki = _mk_wiki(tmp_path)
    (wiki / "sources" / "_context.md").write_text(
        "---\ntitle: Sources context\n---\n[[X]]\n",
        encoding="utf-8",
    )
    results = b.inject_all(wiki)
    assert results["X"] == 2  # _context's link not counted


def test_inject_all_handles_broken_wikilinks(tmp_path):
    wiki = _mk_wiki(tmp_path)
    # Add a page linking to a nonexistent target.
    (wiki / "sources" / "s3.md").write_text(
        "---\ntitle: S3\n---\nBroken [[DoesNotExist]]\n",
        encoding="utf-8",
    )
    b.inject_all(wiki)
    # Broken link isn't promoted into a page; nothing crashes.
    assert (wiki / "sources" / "s3.md").is_file()


def test_prune_all_removes_blocks(tmp_path):
    wiki = _mk_wiki(tmp_path)
    b.inject_all(wiki)
    text = (wiki / "entities" / "X.md").read_text(encoding="utf-8")
    assert "BACKLINKS" in text
    n = b.prune_all(wiki)
    assert n >= 1
    text_after = (wiki / "entities" / "X.md").read_text(encoding="utf-8")
    assert "BACKLINKS" not in text_after


def test_prune_all_dry_run_keeps_blocks(tmp_path):
    wiki = _mk_wiki(tmp_path)
    b.inject_all(wiki)
    b.prune_all(wiki, dry_run=True)
    text = (wiki / "entities" / "X.md").read_text(encoding="utf-8")
    assert "BACKLINKS" in text


# ─── CLI (subcommand removed — skip) ────────────────────────────────────


@pytest.mark.skip(reason="backlinks CLI subcommand removed")
def test_cli_backlinks_dry_run(tmp_path):
    wiki = _mk_wiki(tmp_path)
    before = (wiki / "entities" / "X.md").read_text(encoding="utf-8")
    cp = _run("backlinks", "--wiki-dir", str(wiki), "--dry-run")
    assert cp.returncode == 0
    assert "[dry-run]" in cp.stdout
    after = (wiki / "entities" / "X.md").read_text(encoding="utf-8")
    assert before == after


@pytest.mark.skip(reason="backlinks CLI subcommand removed")
def test_cli_backlinks_prune(tmp_path):
    wiki = _mk_wiki(tmp_path)
    b.inject_all(wiki)
    cp = _run("backlinks", "--wiki-dir", str(wiki), "--prune")
    assert cp.returncode == 0
    assert "removed backlink blocks" in cp.stdout
    text = (wiki / "entities" / "X.md").read_text(encoding="utf-8")
    assert "BACKLINKS" not in text


@pytest.mark.skip(reason="backlinks CLI subcommand removed")
def test_cli_backlinks_verbose_prints_top(tmp_path):
    wiki = _mk_wiki(tmp_path)
    cp = _run("backlinks", "--wiki-dir", str(wiki), "--verbose")
    assert cp.returncode == 0
    assert "X: 2 referrer" in cp.stdout


@pytest.mark.skip(reason="backlinks CLI subcommand removed")
def test_cli_backlinks_missing_wiki_errors(tmp_path):
    cp = _run("backlinks", "--wiki-dir", str(tmp_path / "nope"))
    assert cp.returncode == 2


@pytest.mark.skip(reason="backlinks CLI subcommand removed")
def test_cli_backlinks_help_shows_flags():
    cp = _run("backlinks", "--help")
    assert cp.returncode == 0
    for flag in ("--dry-run", "--prune", "--max-entries", "--verbose"):
        assert flag in cp.stdout


@pytest.mark.skip(reason="backlinks CLI subcommand removed")
def test_cli_backlinks_max_entries_respected(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "sources").mkdir(parents=True)
    (wiki / "entities" / "Hot.md").write_text(
        "---\ntitle: Hot\n---\nBody.\n", encoding="utf-8"
    )
    for i in range(5):
        (wiki / "sources" / f"s{i}.md").write_text(
            f"---\ntitle: S{i}\ndate: 2026-04-{i + 1:02d}\n---\n[[Hot]]\n",
            encoding="utf-8",
        )
    cp = _run("backlinks", "--wiki-dir", str(wiki), "--max-entries", "2")
    assert cp.returncode == 0
    text = (wiki / "entities" / "Hot.md").read_text(encoding="utf-8")
    assert text.count("[[s") == 2
    assert "and 3 more referrer" in text
