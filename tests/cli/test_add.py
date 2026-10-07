"""CLI contract tests for ``llmwiki add`` (raw ingest, synth opt-in, rollback)."""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import llmwiki.add_pipeline as pipe
from llmwiki._frontmatter import parse_frontmatter
from tests.cli._add_helpers import add_vault, fake_claude, run_add, scratch_vault


def test_add_dry_run_local_md(tmp_path):
    """``add --dry-run`` must preview a local markdown file without writing the vault."""
    src = tmp_path / "sample.md"
    src.write_text("# Sample Doc\n\nsome content\n")
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "add", "--dry-run",
         "--vault", str(scratch_vault(tmp_path)), str(src)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "Sample Doc" in r.stdout
    assert "dry-run" in r.stdout


def test_add_requires_source():
    """``add`` without sources must exit with argparse error code 2."""
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "add"],
        capture_output=True, text=True,
    )
    assert r.returncode == 2


def test_add_title_with_multiple_sources_rejected(tmp_path):
    """``--title`` with more than one source path must be rejected at parse time."""
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text("# A\n")
    b.write_text("# B\n")
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "add", "--title", "T", "--dry-run",
         "--vault", str(scratch_vault(tmp_path)), str(a), str(b)],
        capture_output=True, text=True,
    )
    assert r.returncode == 2
    assert "--title" in r.stderr


def test_llm_wiki_add_entry_point(tmp_path):
    """``main_add`` entry point must accept the same argv as the ``add`` subcommand."""
    src = tmp_path / "sample.md"
    src.write_text("# Entry Point Doc\n\ncontent\n")
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; from llmwiki.cli import main_add; sys.exit(main_add())",
         "--dry-run", "--vault", str(scratch_vault(tmp_path)), str(src)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "Entry Point Doc" in r.stdout


def test_add_default_writes_raw_and_builds_without_synth(tmp_path, monkeypatch, capsys):
    """Bare ``add`` lands raw docs and rebuilds the site; no wiki/sources (#273)."""
    vault = add_vault(tmp_path)
    src = tmp_path / "doc.md"
    src.write_text("# Raw Default Doc\n\nbody\n")

    synth_called = {"n": 0}
    build_called = {"n": 0}
    monkeypatch.setattr(
        pipe,
        "synthesize_new_sessions",
        lambda **kw: (synth_called.__setitem__("n", synth_called["n"] + 1) or {
            "synthesized": 0, "skipped": 0, "errors": [],
        }),
    )
    monkeypatch.setattr(
        pipe,
        "build_site",
        lambda **kw: (build_called.__setitem__("n", build_called["n"] + 1) or 0),
    )

    rc = run_add(vault, str(src))
    out = capsys.readouterr()
    assert rc == 0, out.err
    assert synth_called["n"] == 0
    assert build_called["n"] == 1
    assert (vault / "raw" / "docs" / "raw-default-doc" / "raw-default-doc.md").exists()
    assert not list((vault / "wiki" / "sources").rglob("*.md"))


def test_add_configured_claude_backend_synthesizes_synchronously(tmp_path, monkeypatch, capsys):
    """With ``--synthesize``, ``add`` uses the configured backend and produces a wiki source page."""
    vault = add_vault(tmp_path)
    src = tmp_path / "doc.md"
    src.write_text("# Sync Doc\n\nbody\n")

    claude = fake_claude(tmp_path)
    monkeypatch.setattr(pipe, "_load_sessions_config", lambda: {
        "synthesis": {"backend": "claude", "claude_path": str(claude)},
    })
    monkeypatch.setattr(pipe, "build_site", lambda **kw: 0)

    rc = run_add(vault, "--synthesize", str(src))
    out = capsys.readouterr()
    assert rc == 0, out.err
    assert "claude-cli" in out.out
    pages = list((vault / "wiki" / "sources").rglob("*.md"))
    assert pages, "expected a synthesized wiki/sources page in the same run"
    assert "Synthesized synchronously" in pages[0].read_text()
    assert (vault / "raw" / "docs" / "sync-doc" / "sync-doc.md").exists()


# @layer: integration
# @spec: 307-doc-source-provenance
# @regression
def test_add_synthesize_page_claims_raw_doc_and_is_not_a_transcript(
    tmp_path, monkeypatch, capsys
):
    """``add --synthesize`` writes a page claiming its ``raw/docs/`` file and tagged as a document, not a session (#307)."""
    vault = add_vault(tmp_path)
    src = tmp_path / "doc.md"
    src.write_text("# Prov Doc\n\nbody\n")

    monkeypatch.setattr(pipe, "_load_sessions_config", lambda: {
        "synthesis": {"backend": "claude", "claude_path": str(fake_claude(tmp_path))},
    })
    monkeypatch.setattr(pipe, "build_site", lambda **kw: 0)

    rc = run_add(vault, "--synthesize", str(src))
    out = capsys.readouterr()
    assert rc == 0, out.err
    pages = list((vault / "wiki" / "sources").rglob("*.md"))
    assert len(pages) == 1, pages
    meta, _body = parse_frontmatter(pages[0].read_text(encoding="utf-8"))
    assert meta["source_file"] == "raw/docs/prov-doc/prov-doc.md"
    assert (vault / meta["source_file"]).is_file()
    assert "raw-doc" in meta["tags"] or "wiki-add" in meta["tags"]
    assert "session-transcript" not in meta["tags"]


def test_add_synthesizes_only_written_docs(tmp_path, monkeypatch, capsys):
    """``add --synthesize`` must not drain the unsynthesized backlog — only the docs it wrote."""
    vault = add_vault(tmp_path)
    backlog = vault / "raw" / "docs" / "old-backlog" / "old-backlog.md"
    backlog.parent.mkdir(parents=True)
    backlog.write_text("---\ntitle: Old\nproject: docs\nslug: old-backlog\n---\n\n# Old\n", encoding="utf-8")

    src = tmp_path / "new.md"
    src.write_text("# Brand New\n\nbody\n")

    captured: dict = {}

    def _fake_synth(**kwargs):
        captured.update(kwargs)
        return {
            "total_scanned": 1,
            "new_files": 1,
            "synthesized": 1,
            "skipped": 0,
            "errors": [],
            "backend": "dummy",
        }

    class _Ok:
        name = "dummy"
        def is_available(self):
            return True

    monkeypatch.setattr(pipe, "_load_sessions_config", lambda: {
        "synthesis": {"backend": "dummy"},
    })
    monkeypatch.setattr(pipe, "resolve_backend", lambda _cfg: _Ok())
    monkeypatch.setattr(pipe, "synthesize_new_sessions", _fake_synth)
    monkeypatch.setattr(pipe, "build_site", lambda **kw: 0)

    def _expected(raw_path, sources_dir):
        p = Path(sources_dir) / "docs" / "brand-new.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# Brand New\n", encoding="utf-8")
        return p
    monkeypatch.setattr(pipe, "expected_source_page", _expected)

    rc = run_add(vault, "--synthesize", str(src))
    assert rc == 0
    assert "only_paths" in captured
    only = {str(p) for p in captured["only_paths"]}
    assert any("brand-new" in p for p in only)
    assert not any("old-backlog" in p for p in only)


def test_add_readd_unchanged_skips_without_synth(tmp_path, monkeypatch, capsys):
    """Re-adding identical content exits 0 and does not synthesize/build (#22)."""
    vault = add_vault(tmp_path)
    src = tmp_path / "doc.md"
    src.write_text("# Repeat Doc\n\nsame body\n")

    synth_called = {"n": 0}
    build_called = {"n": 0}

    monkeypatch.setattr(pipe, "synthesize_new_sessions",
                        lambda **kw: (synth_called.__setitem__("n", synth_called["n"] + 1) or {}))
    monkeypatch.setattr(pipe, "build_site",
                        lambda **kw: (build_called.__setitem__("n", build_called["n"] + 1) or 0))

    rc1 = run_add(vault, "--no-build", str(src))
    assert rc1 == 0
    assert synth_called["n"] == 0
    assert build_called["n"] == 0

    rc2 = run_add(vault, str(src))
    out = capsys.readouterr()
    assert rc2 == 0, out.err
    assert synth_called["n"] == 0, "re-add must not trigger synthesis"
    assert build_called["n"] == 0, "re-add must not trigger build"
    assert "already present as repeat-doc" in out.out
    assert len(list((vault / "raw" / "docs").rglob("*.md"))) == 1


def test_add_unavailable_backend_rolls_back_raw_docs(tmp_path, monkeypatch, capsys):
    """With ``--synthesize``, an unavailable backend rolls back raw docs."""
    vault = add_vault(tmp_path)
    src = tmp_path / "doc.md"
    src.write_text("# Orphan Doc\n\nbody\n")

    class _Unavailable:
        name = "offline"
        def is_available(self):
            return False

    monkeypatch.setattr(pipe, "_load_sessions_config", lambda: {
        "synthesis": {"backend": "dummy"},
    })
    monkeypatch.setattr(pipe, "resolve_backend", lambda _cfg: _Unavailable())
    monkeypatch.setattr(pipe, "build_site", lambda **kw: 0)

    rc = run_add(vault, "--synthesize", str(src))
    out = capsys.readouterr()
    assert rc == 2
    assert "omit --synthesize" in out.err
    assert "olled back" in out.err
    assert not (vault / "raw" / "docs" / "orphan-doc").exists()
    log = vault / "wiki" / "log.md"
    assert not log.exists() or "Orphan Doc" not in log.read_text()


def test_add_failed_synthesis_rolls_back_raw_docs(tmp_path, monkeypatch, capsys):
    """A backend that errors per page leaves no wiki page — raw doc rolled back."""
    vault = add_vault(tmp_path)
    src = tmp_path / "doc.md"
    src.write_text("# Broken Doc\n\nbody\n")

    broken = tmp_path / "claude-broken"
    broken.write_text("#!/bin/sh\ncat > /dev/null\necho boom >&2\nexit 1\n")
    broken.chmod(0o755)
    monkeypatch.setattr(pipe, "_load_sessions_config", lambda: {
        "synthesis": {"backend": "claude", "claude_path": str(broken)},
    })
    monkeypatch.setattr(pipe, "build_site", lambda **kw: 0)

    rc = run_add(vault, "--synthesize", str(src))
    out = capsys.readouterr()
    assert rc == 2
    assert "olled back" in out.err
    assert not (vault / "raw" / "docs" / "broken-doc").exists()


def test_add_no_synthesize_warns_and_keeps_docs(tmp_path, monkeypatch, capsys):
    """``--no-synthesize`` is a warn+no-op alias; docs stay raw-only (#273)."""
    vault = add_vault(tmp_path)
    src = tmp_path / "doc.md"
    src.write_text("# Raw Only Doc\n\nbody\n")
    monkeypatch.setattr(pipe, "build_site", lambda **kw: 0)

    rc = run_add(vault, "--no-synthesize", str(src))
    out = capsys.readouterr()
    assert rc == 0
    assert "no-op" in out.err
    assert "already off by default" in out.err
    assert (vault / "raw" / "docs" / "raw-only-doc" / "raw-only-doc.md").exists()
    assert not list((vault / "wiki" / "sources").rglob("*.md"))


def test_add_stdin_sentinel_piped_provenance(tmp_path, monkeypatch, capsys):
    """``add -`` reads stdin and records ``source: piped`` (#273)."""
    vault = add_vault(tmp_path)
    monkeypatch.setattr(pipe, "build_site", lambda **kw: 0)
    monkeypatch.setattr(sys, "stdin", io.StringIO("# Piped CLI Doc\n\nhello from stdin\n"))

    rc = run_add(vault, "--no-build", "-")
    out = capsys.readouterr()
    assert rc == 0, out.err
    written = list((vault / "raw" / "docs").rglob("*.md"))
    assert written, out.out
    text = written[0].read_text(encoding="utf-8")
    assert 'source: "piped"' in text or "source: piped" in text
    assert "hello from stdin" in text
