"""CLI surface for candidate harvesting (#90 / #147).

``--candidates-only`` must work on a vault whose sources are already
synthesized — that is precisely the vault with the largest candidate
backlog — without re-synthesizing a single source.

Harvest is offline (#147): kinds come from source topic bullets. A missing
or unreachable backend must not block writing stubs.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from llmwiki.cli import build_parser, cmd_synthesize


def _mk_vault(
    tmp_path: Path, links: dict[str, list[str]], *, kind: str = "entity"
) -> Path:
    """Build a vault whose wiki/sources pages carry the given wikilinks."""
    vault = tmp_path / "vault"
    (vault / "raw" / "sessions").mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    sources = vault / "wiki" / "sources"
    sources.mkdir(parents=True)
    for slug, names in links.items():
        body = "\n".join(
            f"- [[{n}]] ({kind}) — a harvested topic\n"
            f"  - fact: cited from {slug}."
            for n in names
        )
        (sources / f"{slug}.md").write_text(
            f"---\ntitle: {slug}\ntype: source\n---\n\n## Connections\n{body}\n",
            encoding="utf-8",
        )
    return vault


def _args(**overrides) -> argparse.Namespace:
    base = {
        "check": False,
        "estimate": False,
        "force": False,
        "paths": None,
        "sessions_only": False,
        "docs_only": False,
        "candidates_only": False,
        "min_refs": 3,
        "vault": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


# ─── Parser defaults ───────────────────────────────────────────────────


def test_min_refs_defaults_to_three() -> None:
    """Agrees with the lint rule defining a missing entity as 3+ mentions."""
    args = build_parser().parse_args(["synth", "--candidates-only"])

    assert args.min_refs == 3
    assert args.candidates_only is True


def test_no_bypass_flag_for_unclassified_targets() -> None:
    """#102: proceeding on a guess is withdrawn — the flag must be gone."""
    parser = build_parser()

    assert "--allow-unclassified" not in parser.format_help()
    with pytest.raises(SystemExit):
        parser.parse_args(["synth", "--candidates-only", "--allow-unclassified"])


# ─── Backends ──────────────────────────────────────────────────────────


class _UnavailableBackend:
    """A backend that is configured but unreachable."""

    name = "offline"

    def is_available(self) -> bool:
        return False

    def synthesize_source_page(self, raw_body, meta, prompt_template):
        raise AssertionError("must not call an unavailable backend")


class _ClassifyingBackend:
    """A reachable backend that labels every name it is asked about."""

    name = "stub"

    def __init__(self, kind: str = "entity", *, omit: tuple[str, ...] = ()) -> None:
        self.kind = kind
        self.omit = set(omit)

    def is_available(self) -> bool:
        return True

    def synthesize_source_page(self, raw_body, meta, prompt_template) -> str:
        return "".join(
            f"{name}: {self.kind}\n"
            for name in raw_body.splitlines()
            if name not in self.omit
        )


# ─── A fully classified run ────────────────────────────────────────────


def test_candidates_only_writes_stubs_from_synthesized_sources(
    tmp_path: Path, monkeypatch
) -> None:
    """The whole point: a caught-up vault whose sources are already
    synthesized is exactly the vault with the largest candidate backlog."""
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _ClassifyingBackend()
    )

    rc = cmd_synthesize(_args(candidates_only=True, vault=vault))

    assert rc == 0
    stub = vault / "wiki" / "candidates" / "entities" / "Recurring.md"
    assert "status: candidate" in stub.read_text(encoding="utf-8")


def test_written_stub_carries_no_entity_type(tmp_path: Path, monkeypatch) -> None:
    """#102 R2: nothing creates the taxonomy field any more."""
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _ClassifyingBackend()
    )

    cmd_synthesize(_args(candidates_only=True, vault=vault))

    stub = vault / "wiki" / "candidates" / "entities" / "Recurring.md"
    assert "entity_type" not in stub.read_text(encoding="utf-8")


def test_fully_classified_run_reports_no_unknown_warning(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """#102 R5: a clean run says nothing about unknown or unclassified pages."""
    vault = _mk_vault(tmp_path, {s: ["Compounding"] for s in ("a", "b", "c")})
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _ClassifyingBackend("concept")
    )

    assert cmd_synthesize(_args(candidates_only=True, vault=vault)) == 0

    err = capsys.readouterr().err
    assert "unknown" not in err
    assert "unclassified" not in err


def test_candidates_only_honours_min_refs(tmp_path: Path, monkeypatch) -> None:
    vault = _mk_vault(
        tmp_path,
        {"a": ["Pair"], "b": ["Pair"], "c": ["Trio"], "d": ["Trio"], "e": ["Trio"]},
    )
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _ClassifyingBackend()
    )

    cmd_synthesize(_args(candidates_only=True, vault=vault, min_refs=3))

    written = {p.stem for p in (vault / "wiki" / "candidates").rglob("*.md")}
    assert written == {"Trio"}


def test_candidates_only_makes_no_per_source_synthesis_calls(
    tmp_path: Path, monkeypatch
) -> None:
    """Cost must scale with the candidate count, not the corpus.

    Classification is one batched call; synthesizing sources is what this
    mode exists to avoid.
    """
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})

    def _explode(*a, **kw):  # pragma: no cover - must never run
        raise AssertionError("candidates-only must not synthesize sources")

    monkeypatch.setattr("llmwiki.cli.synthesize_new_sessions", _explode)
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _ClassifyingBackend()
    )

    assert cmd_synthesize(_args(candidates_only=True, vault=vault)) == 0


def test_candidates_only_files_by_source_topic_kind(tmp_path: Path, monkeypatch) -> None:
    """#147: harvest kind comes from source bullets, not a classifier call."""
    vault = _mk_vault(
        tmp_path, {s: ["Compounding"] for s in ("a", "b", "c")}, kind="concept"
    )
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _UnavailableBackend()
    )

    assert cmd_synthesize(_args(candidates_only=True, vault=vault)) == 0
    assert (vault / "wiki" / "candidates" / "concepts" / "Compounding.md").is_file()


def test_rerun_with_nothing_new_succeeds(tmp_path: Path, monkeypatch) -> None:
    """Already-filed stubs are settled, so a re-run asks nothing of the
    backend and must not fail over an unreachable one."""
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _ClassifyingBackend()
    )
    assert cmd_synthesize(_args(candidates_only=True, vault=vault)) == 0

    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _UnavailableBackend()
    )

    assert cmd_synthesize(_args(candidates_only=True, vault=vault)) == 0


# ─── #147: harvest does not need a classifier ──────────────────────────


def test_unreachable_backend_still_writes_stubs(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Harvest is offline; Dummy/unavailable backends must not block stubs."""
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _UnavailableBackend()
    )

    rc = cmd_synthesize(_args(candidates_only=True, vault=vault))

    assert rc == 0
    stub = vault / "wiki" / "candidates" / "entities" / "Recurring.md"
    assert stub.is_file()
    err = capsys.readouterr().err
    assert "Nothing was written" not in err


def test_backend_resolution_failure_still_writes_stubs(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})

    def _boom(cfg):
        raise RuntimeError("no backend configured")

    monkeypatch.setattr("llmwiki.cli.resolve_backend", _boom)

    rc = cmd_synthesize(_args(candidates_only=True, vault=vault))

    assert rc == 0
    assert (vault / "wiki" / "candidates" / "entities" / "Recurring.md").is_file()
    assert "backend unavailable" in capsys.readouterr().err


def test_unreadable_sources_fail_the_run(tmp_path: Path, monkeypatch, capsys) -> None:
    """Unreadable source pages still abort harvest with nothing written."""
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})
    (vault / "wiki" / "sources" / "broken.md").mkdir()
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _ClassifyingBackend()
    )

    rc = cmd_synthesize(_args(candidates_only=True, vault=vault))

    err = capsys.readouterr().err
    assert rc == 2
    assert "could not be read" in err
    assert "sources/broken.md" in err
    assert "Nothing was written" in err
    assert not (vault / "wiki" / "candidates").exists()
