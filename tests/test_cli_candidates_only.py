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


def test_candidates_only_writes_stubs_without_a_backend(tmp_path: Path) -> None:
    """The whole point: a caught-up vault, no synthesis, no backend needed."""
    vault = _mk_vault(
        tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")}
    )

    rc = cmd_synthesize(_args(candidates_only=True, vault=vault))

    assert rc == 0
    stub = vault / "wiki" / "candidates" / "entities" / "Recurring.md"
    assert stub.is_file()
    assert "status: candidate" in stub.read_text(encoding="utf-8")


def test_candidates_only_honours_min_refs(tmp_path: Path) -> None:
    vault = _mk_vault(
        tmp_path,
        {"a": ["Pair"], "b": ["Pair"], "c": ["Trio"], "d": ["Trio"], "e": ["Trio"]},
    )

    cmd_synthesize(_args(candidates_only=True, vault=vault, min_refs=3))

    written = {p.stem for p in (vault / "wiki" / "candidates").rglob("*.md")}
    assert written == {"Trio"}


def test_candidates_only_makes_no_synthesis_calls(tmp_path: Path, monkeypatch) -> None:
    """Guards the contract that this mode costs nothing to run."""
    vault = _mk_vault(tmp_path, {s: ["Recurring"] for s in ("a", "b", "c")})

    def _explode(*a, **kw):  # pragma: no cover - must never run
        raise AssertionError("candidates-only must not synthesize")

    monkeypatch.setattr("llmwiki.cli.synthesize_new_sessions", _explode)

    assert cmd_synthesize(_args(candidates_only=True, vault=vault)) == 0
