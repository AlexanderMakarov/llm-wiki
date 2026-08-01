"""CLI surface for candidate harvesting (#90).

``--candidates-only`` must work on a vault whose sources are already
synthesized — that is precisely the vault with the largest candidate
backlog — and must not need a synthesis backend to do it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

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
        "allow_unclassified": False,
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


# ─── Behaviour ─────────────────────────────────────────────────────────


class _UnavailableBackend:
    """A backend that is configured but unreachable."""

    name = "offline"

    def is_available(self) -> bool:
        return False

    def synthesize_source_page(self, raw_body, meta, prompt_template):
        raise AssertionError("must not call an unavailable backend")


def test_candidates_only_writes_stubs_without_a_backend(
    tmp_path: Path, monkeypatch
) -> None:
    """The whole point: a caught-up vault, no synthesis, backend unreachable.

    Classification degrades to ``unknown``; the harvest still lands.
    """
    vault = _mk_vault(
        tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")}
    )
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _UnavailableBackend()
    )

    rc = cmd_synthesize(
        _args(candidates_only=True, vault=vault, allow_unclassified=True)
    )

    assert rc == 0
    stub = vault / "wiki" / "candidates" / "entities" / "Recurring.md"
    assert stub.is_file()
    assert "status: candidate" in stub.read_text(encoding="utf-8")


def test_candidates_only_honours_min_refs(tmp_path: Path, monkeypatch) -> None:
    vault = _mk_vault(
        tmp_path,
        {"a": ["Pair"], "b": ["Pair"], "c": ["Trio"], "d": ["Trio"], "e": ["Trio"]},
    )
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _UnavailableBackend()
    )

    cmd_synthesize(
        _args(candidates_only=True, vault=vault, min_refs=3, allow_unclassified=True)
    )

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
        "llmwiki.cli.resolve_backend", lambda cfg: _UnavailableBackend()
    )

    assert cmd_synthesize(
        _args(candidates_only=True, vault=vault, allow_unclassified=True)
    ) == 0


def test_candidates_only_classifies_via_the_backend(tmp_path: Path, monkeypatch) -> None:
    """The CLI must actually route classification through the backend."""
    vault = _mk_vault(tmp_path, {s: ["Compounding"] for s in ("a", "b", "c")})

    class _Backend:
        name = "stub"

        def is_available(self):
            return True

        def synthesize_source_page(self, raw_body, meta, prompt_template):
            return "Compounding: concept\n"

    monkeypatch.setattr("llmwiki.cli.resolve_backend", lambda cfg: _Backend())

    assert cmd_synthesize(_args(candidates_only=True, vault=vault)) == 0
    assert (vault / "wiki" / "candidates" / "concepts" / "Compounding.md").is_file()


def test_candidates_only_survives_backend_resolution_failure(
    tmp_path: Path, monkeypatch
) -> None:
    """A broken backend config must not cost us the harvest."""
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})

    def _boom(cfg):
        raise RuntimeError("no backend configured")

    monkeypatch.setattr("llmwiki.cli.resolve_backend", _boom)

    assert cmd_synthesize(
        _args(candidates_only=True, vault=vault, allow_unclassified=True)
    ) == 0
    assert (vault / "wiki" / "candidates" / "entities" / "Recurring.md").is_file()


def test_unclassified_targets_are_reported_not_silent(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """An operator must be able to tell model-filed from fallback-filed."""
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _UnavailableBackend()
    )

    cmd_synthesize(_args(candidates_only=True, vault=vault, allow_unclassified=True))

    err = capsys.readouterr().err
    assert "1 of 1 candidate(s) are filed as entity_type: unknown" in err


def test_fully_classified_run_reports_no_warning(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    vault = _mk_vault(tmp_path, {s: ["Compounding"] for s in ("a", "b", "c")})

    class _Backend:
        name = "stub"

        def is_available(self):
            return True

        def synthesize_source_page(self, raw_body, meta, prompt_template):
            return "Compounding: concept\n"

    monkeypatch.setattr("llmwiki.cli.resolve_backend", lambda cfg: _Backend())

    cmd_synthesize(_args(candidates_only=True, vault=vault))

    assert "entity_type: unknown" not in capsys.readouterr().err


def test_rerun_still_reports_unknown_stubs(tmp_path: Path, monkeypatch, capsys) -> None:
    """A re-run re-asks nothing, so the count must come from disk, not the call."""
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _UnavailableBackend()
    )

    cmd_synthesize(_args(candidates_only=True, vault=vault, allow_unclassified=True))
    capsys.readouterr()
    cmd_synthesize(_args(candidates_only=True, vault=vault))

    assert (
        "1 of 1 candidate(s) are filed as entity_type: unknown"
        in capsys.readouterr().err
    )


# ─── Unclassified targets are a failure by default ─────────────────────


def test_unclassified_targets_fail_the_run(tmp_path: Path, monkeypatch) -> None:
    """Default is refusal: a half-classified queue is not a good queue."""
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _UnavailableBackend()
    )

    rc = cmd_synthesize(_args(candidates_only=True, vault=vault))

    assert rc == 1


def test_failed_run_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    """Refusing after writing would leave the mess the refusal exists to avoid."""
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _UnavailableBackend()
    )

    cmd_synthesize(_args(candidates_only=True, vault=vault))

    assert not (vault / "wiki" / "candidates").exists()


def test_allow_unclassified_opts_into_unknown_stubs(tmp_path: Path, monkeypatch) -> None:
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _UnavailableBackend()
    )

    rc = cmd_synthesize(
        _args(candidates_only=True, vault=vault, allow_unclassified=True)
    )

    assert rc == 0
    stub = vault / "wiki" / "candidates" / "entities" / "Recurring.md"
    assert "entity_type: unknown" in stub.read_text(encoding="utf-8")


def test_partial_classification_also_fails(tmp_path: Path, monkeypatch) -> None:
    """One unclassified name out of many is still a partial result."""
    vault = _mk_vault(
        tmp_path,
        {f"s{i}": ["Known", "Unknown"] for i in range(3)},
    )

    class _Partial:
        name = "partial"

        def is_available(self):
            return True

        def synthesize_source_page(self, raw_body, meta, prompt_template):
            return "Known: entity\n"

    monkeypatch.setattr("llmwiki.cli.resolve_backend", lambda cfg: _Partial())

    assert cmd_synthesize(_args(candidates_only=True, vault=vault)) == 1


def test_rerun_with_nothing_new_succeeds(tmp_path: Path, monkeypatch) -> None:
    """Already-filed stubs are settled; a re-run must not fail over them."""
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: _UnavailableBackend()
    )
    cmd_synthesize(_args(candidates_only=True, vault=vault, allow_unclassified=True))

    assert cmd_synthesize(_args(candidates_only=True, vault=vault)) == 0
