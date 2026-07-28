"""Tests for ``llmwiki synthesize --path`` (#62)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.cli import (
    _resolve_synthesize_only_paths,
    build_parser,
    cmd_synthesize,
)
from llmwiki.synth.base import DummySynthesizer
from llmwiki.synth.pipeline import synthesize_new_sessions
import llmwiki.config_schedule as config_mod
import llmwiki.synth.pipeline as pipeline_mod



def _seed_vault(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Two unsynthesized sessions under a vault-shaped tree."""
    vault = tmp_path / "vault"
    raw = vault / "raw" / "sessions"
    docs = vault / "raw" / "docs"
    wiki = vault / "wiki" / "sources"
    raw.mkdir(parents=True)
    docs.mkdir(parents=True)
    wiki.mkdir(parents=True)
    (raw / "keep.md").write_text(
        "---\nslug: keep\nproject: p\ndate: 2026-07-01\n---\n# keep\n",
        encoding="utf-8",
    )
    (raw / "skip.md").write_text(
        "---\nslug: skip\nproject: p\ndate: 2026-07-01\n---\n# skip\n",
        encoding="utf-8",
    )
    (docs / "note.md").write_text(
        "---\ntitle: Note\nproject: docs\n---\n\ndoc body\n",
        encoding="utf-8",
    )
    return vault, raw, wiki


def test_resolve_relative_and_absolute_under_vault(tmp_path: Path):
    vault, raw, _wiki = _seed_vault(tmp_path)
    target = raw / "keep.md"
    out = _resolve_synthesize_only_paths(
        ["raw/sessions/keep.md", str(target)],
        vault,
    )
    assert out == {target.resolve()}


def test_resolve_missing_path_errors(tmp_path: Path):
    vault, _raw, _wiki = _seed_vault(tmp_path)
    with pytest.raises(ValueError, match="path not found"):
        _resolve_synthesize_only_paths(["raw/sessions/missing.md"], vault)


def test_resolve_outside_vault_errors(tmp_path: Path):
    vault, _raw, _wiki = _seed_vault(tmp_path)
    outsider = tmp_path / "elsewhere.md"
    outsider.write_text("nope\n", encoding="utf-8")
    with pytest.raises(ValueError, match="path outside vault"):
        _resolve_synthesize_only_paths([str(outsider)], vault)


def test_resolve_rejects_non_raw_path(tmp_path: Path):
    vault, _raw, wiki = _seed_vault(tmp_path)
    bad = wiki / "page.md"
    bad.write_text("# page\n", encoding="utf-8")
    with pytest.raises(ValueError, match="raw/sessions/ or raw/docs/"):
        _resolve_synthesize_only_paths(["wiki/sources/page.md"], vault)


def test_only_paths_synthesizes_named_session_only(tmp_path: Path):
    vault, raw, wiki = _seed_vault(tmp_path)
    keep = raw / "keep.md"
    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=raw,
        docs_dir=vault / "raw" / "docs",
        wiki_sources_dir=wiki,
        state_file=vault / "state.json",
        log_path=vault / "wiki" / "log.md",
        only_paths={keep},
        include_subagents="all",
        exclude_headless=False,
    )
    assert summary["synthesized"] == 1
    assert summary["errors"] == []
    written = {p.name for p in wiki.rglob("*.md")}
    assert any("keep" in n for n in written)
    assert not any("skip" in n for n in written)
    assert not any("note" in n or "openclaw" in n for n in written)


def test_only_paths_can_target_a_doc(tmp_path: Path):
    vault, raw, wiki = _seed_vault(tmp_path)
    note = vault / "raw" / "docs" / "note.md"
    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=raw,
        docs_dir=vault / "raw" / "docs",
        wiki_sources_dir=wiki,
        state_file=vault / "state.json",
        log_path=vault / "wiki" / "log.md",
        only_paths={note},
        include_subagents="all",
        exclude_headless=False,
    )
    assert summary["synthesized"] == 1
    written = {p.name for p in wiki.rglob("*.md")}
    assert any("note" in n for n in written)
    assert not any("keep" in n for n in written)


def test_parser_accepts_repeatable_path():
    parser = build_parser()
    args = parser.parse_args([
        "synthesize",
        "--path", "raw/sessions/a.md",
        "--path", "raw/docs/b.md",
    ])
    assert args.paths == ["raw/sessions/a.md", "raw/docs/b.md"]


def test_cmd_synthesize_path_passes_only_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
):
    vault, raw, _wiki = _seed_vault(tmp_path)
    keep = (raw / "keep.md").resolve()
    captured: dict = {}

    class _Ok:
        name = "dummy"

        def is_available(self) -> bool:
            return True

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


    monkeypatch.setattr(config_mod, "_load_sessions_config", lambda: {
        "synthesis": {"backend": "dummy"},
    })
    monkeypatch.setattr(pipeline_mod, "resolve_backend", lambda _cfg: _Ok())
    monkeypatch.setattr(pipeline_mod, "synthesize_new_sessions", _fake_synth)

    args = build_parser().parse_args([
        "synthesize",
        "--vault", str(vault),
        "--path", "raw/sessions/keep.md",
    ])
    rc = cmd_synthesize(args)
    assert rc == 0
    assert captured["only_paths"] == {keep}
    assert captured["raw_dir"] == vault / "raw" / "sessions"
    out = capsys.readouterr()
    assert "synthesized 1" in out.out


def test_cmd_synthesize_missing_path_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
):
    vault, _raw, _wiki = _seed_vault(tmp_path)

    class _Ok:
        name = "dummy"

        def is_available(self) -> bool:
            return True


    monkeypatch.setattr(config_mod, "_load_sessions_config", lambda: {
        "synthesis": {"backend": "dummy"},
    })
    monkeypatch.setattr(pipeline_mod, "resolve_backend", lambda _cfg: _Ok())

    args = build_parser().parse_args([
        "synthesize",
        "--vault", str(vault),
        "--path", "raw/sessions/missing.md",
    ])
    rc = cmd_synthesize(args)
    assert rc == 2
    err = capsys.readouterr().err
    assert "path not found" in err


def test_cmd_synthesize_path_rejects_estimate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
):
    vault, _raw, _wiki = _seed_vault(tmp_path)
    monkeypatch.setattr(
        "llmwiki.config_schedule._load_sessions_config",
        lambda: {"synthesis": {"backend": "dummy"}},
    )
    args = build_parser().parse_args([
        "synthesize",
        "--vault", str(vault),
        "--estimate",
        "--path", "raw/sessions/keep.md",
    ])
    rc = cmd_synthesize(args)
    assert rc == 2
    assert "--path cannot be combined with --estimate" in capsys.readouterr().err


def test_only_paths_still_skips_headless(tmp_path: Path):
    vault = tmp_path / "vault"
    raw = vault / "raw" / "sessions"
    wiki = vault / "wiki" / "sources"
    raw.mkdir(parents=True)
    wiki.mkdir(parents=True)
    headless = raw / "headless.md"
    headless.write_text(
        "---\nslug: headless\nproject: p\nis_headless: true\n"
        "entrypoint: sdk-cli\n---\n# headless\n",
        encoding="utf-8",
    )
    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=raw,
        wiki_sources_dir=wiki,
        state_file=vault / "state.json",
        log_path=vault / "wiki" / "log.md",
        only_paths={headless},
        include_docs=False,
        exclude_headless=True,
    )
    assert summary["synthesized"] == 0
    assert list(wiki.rglob("*.md")) == []


def test_include_sessions_false_skips_sessions(tmp_path: Path):
    vault, raw, wiki = _seed_vault(tmp_path)
    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=raw,
        docs_dir=vault / "raw" / "docs",
        wiki_sources_dir=wiki,
        state_file=vault / "state.json",
        log_path=vault / "wiki" / "log.md",
        include_sessions=False,
        include_docs=True,
        include_subagents="all",
        exclude_headless=False,
    )
    assert summary["synthesized"] == 1
    written = {p.name for p in wiki.rglob("*.md")}
    assert any("note" in n for n in written)
    assert not any("keep" in n for n in written)
    assert not any("skip" in n for n in written)


def test_include_docs_false_skips_docs(tmp_path: Path):
    vault, raw, wiki = _seed_vault(tmp_path)
    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=raw,
        docs_dir=vault / "raw" / "docs",
        wiki_sources_dir=wiki,
        state_file=vault / "state.json",
        log_path=vault / "wiki" / "log.md",
        include_sessions=True,
        include_docs=False,
        include_subagents="all",
        exclude_headless=False,
    )
    assert summary["synthesized"] == 2
    written = {p.name for p in wiki.rglob("*.md")}
    assert any("keep" in n for n in written)
    assert any("skip" in n for n in written)
    assert not any("note" in n for n in written)


def test_parser_sessions_only_and_docs_only_are_exclusive():
    parser = build_parser()
    args = parser.parse_args(["synthesize", "--sessions-only"])
    assert args.sessions_only is True
    assert args.docs_only is False
    with pytest.raises(SystemExit):
        parser.parse_args(["synthesize", "--sessions-only", "--docs-only"])


def test_cmd_synthesize_sessions_only_passes_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
):
    vault, _raw, _wiki = _seed_vault(tmp_path)
    captured: dict = {}

    class _Ok:
        name = "dummy"

        def is_available(self) -> bool:
            return True

    def _fake_synth(**kwargs):
        captured.update(kwargs)
        return {
            "total_scanned": 2,
            "new_files": 2,
            "synthesized": 2,
            "skipped": 0,
            "errors": [],
            "backend": "dummy",
        }


    monkeypatch.setattr(config_mod, "_load_sessions_config", lambda: {
        "synthesis": {"backend": "dummy"},
    })
    monkeypatch.setattr(pipeline_mod, "resolve_backend", lambda _cfg: _Ok())
    monkeypatch.setattr(pipeline_mod, "synthesize_new_sessions", _fake_synth)

    args = build_parser().parse_args([
        "synthesize",
        "--vault", str(vault),
        "--sessions-only",
    ])
    rc = cmd_synthesize(args)
    assert rc == 0
    assert captured["include_sessions"] is True
    assert captured["include_docs"] is False
    assert "synthesized 2" in capsys.readouterr().out


def test_cmd_synthesize_docs_only_passes_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    vault, _raw, _wiki = _seed_vault(tmp_path)
    captured: dict = {}

    class _Ok:
        name = "dummy"

        def is_available(self) -> bool:
            return True

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


    monkeypatch.setattr(config_mod, "_load_sessions_config", lambda: {
        "synthesis": {"backend": "dummy"},
    })
    monkeypatch.setattr(pipeline_mod, "resolve_backend", lambda _cfg: _Ok())
    monkeypatch.setattr(pipeline_mod, "synthesize_new_sessions", _fake_synth)

    args = build_parser().parse_args([
        "synthesize",
        "--vault", str(vault),
        "--docs-only",
    ])
    rc = cmd_synthesize(args)
    assert rc == 0
    assert captured["include_sessions"] is False
    assert captured["include_docs"] is True


def test_cmd_synthesize_sessions_only_rejects_doc_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
):
    vault, _raw, _wiki = _seed_vault(tmp_path)

    class _Ok:
        name = "dummy"

        def is_available(self) -> bool:
            return True


    monkeypatch.setattr(config_mod, "_load_sessions_config", lambda: {
        "synthesis": {"backend": "dummy"},
    })
    monkeypatch.setattr(pipeline_mod, "resolve_backend", lambda _cfg: _Ok())

    args = build_parser().parse_args([
        "synthesize",
        "--vault", str(vault),
        "--sessions-only",
        "--path", "raw/docs/note.md",
    ])
    rc = cmd_synthesize(args)
    assert rc == 2
    assert "--sessions-only cannot target a doc" in capsys.readouterr().err


def test_cmd_synthesize_docs_only_rejects_session_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
):
    vault, _raw, _wiki = _seed_vault(tmp_path)

    class _Ok:
        name = "dummy"

        def is_available(self) -> bool:
            return True


    monkeypatch.setattr(config_mod, "_load_sessions_config", lambda: {
        "synthesis": {"backend": "dummy"},
    })
    monkeypatch.setattr(pipeline_mod, "resolve_backend", lambda _cfg: _Ok())

    args = build_parser().parse_args([
        "synthesize",
        "--vault", str(vault),
        "--docs-only",
        "--path", "raw/sessions/keep.md",
    ])
    rc = cmd_synthesize(args)
    assert rc == 2
    assert "--docs-only cannot target a session" in capsys.readouterr().err


def test_cmd_synthesize_sessions_only_rejects_estimate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
):
    vault, _raw, _wiki = _seed_vault(tmp_path)
    monkeypatch.setattr(
        "llmwiki.config_schedule._load_sessions_config",
        lambda: {"synthesis": {"backend": "dummy"}},
    )
    args = build_parser().parse_args([
        "synthesize",
        "--vault", str(vault),
        "--estimate",
        "--sessions-only",
    ])
    rc = cmd_synthesize(args)
    assert rc == 2
    assert "cannot be combined with --estimate" in capsys.readouterr().err

