"""CLI surface for candidate harvesting (#90).

``--candidates-only`` must work on a vault whose sources are already
synthesized — that is precisely the vault with the largest candidate
backlog — without re-synthesizing a single source.

Classification is fail-closed (#102): every new target must be labelled
entity or concept, and a run that cannot get there stops with a
cause-specific error having written nothing.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from llmwiki.cli import build_parser, cmd_synthesize


def _mk_vault(tmp_path: Path, links: dict[str, list[str]]) -> Path:
    """Build a vault whose wiki/sources pages carry the given wikilinks."""
    vault = tmp_path / "vault"
    (vault / "raw" / "sessions").mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    sources = vault / "wiki" / "sources"
    sources.mkdir(parents=True)
    for slug, names in links.items():
        body = "\n".join(f"- [[{n}]]" for n in names)
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
    args = build_parser().parse_args(["synthesize", "--candidates-only"])

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


def test_candidates_only_classifies_via_the_backend(tmp_path: Path, monkeypatch) -> None:
    """The CLI must actually route classification through the backend."""
    vault = _mk_vault(tmp_path, {s: ["Compounding"] for s in ("a", "b", "c")})
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _ClassifyingBackend("concept")
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


# ─── Failure causes: each names itself and writes nothing ──────────────


def test_unreachable_backend_fails_the_run(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Cause (a): the backend was never reached, so there is no reply to blame."""
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _UnavailableBackend()
    )

    rc = cmd_synthesize(_args(candidates_only=True, vault=vault))

    err = capsys.readouterr().err
    assert rc == 1
    assert "unreachable" in err
    assert "offline" in err
    assert "Nothing was written" in err
    assert "Recurring" in err
    assert not (vault / "wiki" / "candidates").exists()


def test_backend_resolution_failure_fails_the_run(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Cause (a) again: a backend that cannot even be constructed is
    unreachable, and harvest must not fall back to guessing."""
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})

    def _boom(cfg):
        raise RuntimeError("no backend configured")

    monkeypatch.setattr("llmwiki.cli.resolve_backend", _boom)

    rc = cmd_synthesize(_args(candidates_only=True, vault=vault))

    assert rc == 1
    assert "unreachable" in capsys.readouterr().err
    assert not (vault / "wiki" / "candidates").exists()


def test_incomplete_reply_fails_the_run(tmp_path: Path, monkeypatch, capsys) -> None:
    """Cause (b): the backend answered, but one name never came back — a
    different problem from an unreachable backend, and it must read as one."""
    vault = _mk_vault(tmp_path, {f"s{i}": ["Known", "Unknown"] for i in range(3)})
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend",
        lambda cfg: _ClassifyingBackend(omit=("Unknown",)),
    )

    rc = cmd_synthesize(_args(candidates_only=True, vault=vault))

    err = capsys.readouterr().err
    assert rc == 1
    assert "incomplete or unparseable" in err
    assert "unreachable" not in err
    assert "Unknown" in err
    assert "Nothing was written" in err
    assert not (vault / "wiki" / "candidates").exists()


def test_unreadable_sources_fail_the_run(tmp_path: Path, monkeypatch, capsys) -> None:
    """Cause (c): a file problem must not be reported as a classifier problem."""
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})
    # A directory named like a page: the scan finds it and cannot read it.
    (vault / "wiki" / "sources" / "broken.md").mkdir()
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _ClassifyingBackend()
    )

    rc = cmd_synthesize(_args(candidates_only=True, vault=vault))

    err = capsys.readouterr().err
    assert rc == 2
    assert "could not be read" in err
    assert "sources/broken.md" in err
    assert "not a classifier problem" in err
    assert "Nothing was written" in err
    assert not (vault / "wiki" / "candidates").exists()
