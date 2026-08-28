"""The same vault always lints to the same report, byte for byte (#150, R9).

Several rules walk a ``set``: ``link_integrity`` iterates
:func:`llmwiki.wikilinks.wikilink_targets`, which returns one. Python
randomises ``str`` hashing per process unless ``PYTHONHASHSEED`` is fixed, so
two *processes* linting one unchanged vault emitted the same findings in a
different order — measured as five distinct payload hashes across five seeds.

That predates the opt-out work but #150 makes it load-bearing: the CLI and the
MCP server are different processes, and R9 promises both "report the same
findings". A raw payload diff showing reordered ``issues`` for an unchanged
vault would make that false on a technicality.

``run_lint`` sorts each rule's findings by ``(page, message)``. Sorting happens
*within* a rule, never across rules, so ``REGISTRY`` enumeration order — which
``llmwiki/lint/rules/__init__.py`` documents as deliberate — still decides
which rule's block comes first.

Ordering is a cross-process property, so the check has to cross processes: an
in-process test cannot reproduce it, because set iteration order is stable
within one interpreter.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from llmwiki.lint import REGISTRY, load_pages, run_lint
from llmwiki.lint import rules as _rules  # noqa: F401 — populate REGISTRY
from llmwiki.vault_settings import DEFAULT_MIN_REFS

#: Enough distinct unresolved targets in one page that a stable order cannot
#: happen by luck: 5! orderings per page.
_TARGETS = ("Zulu", "Alpha", "Mike", "Delta", "Papa")

#: Enough source pages naming each target to clear the *stock* threshold, so
#: the fixture produces findings without lowering ``--min-refs``.
_SOURCE_COUNT = DEFAULT_MIN_REFS


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """A vault whose every unresolved target is a genuine gap at stock settings.

    Each of the ``DEFAULT_MIN_REFS`` source pages names all five targets, so
    every one is named often enough to deserve a page it does not have — the
    findings are real at the threshold the demo runs at, not manufactured by
    turning the threshold down.
    """
    sources = tmp_path / "wiki" / "sources"
    sources.mkdir(parents=True)
    body = "\n".join(f"- [[{name}]] — see also" for name in _TARGETS)
    for i in range(_SOURCE_COUNT):
        (sources / f"session-{i}.md").write_text(
            f'---\ntitle: "Session {i}"\ntype: source\n---\n\n## Connections\n{body}\n',
            encoding="utf-8",
        )
    return tmp_path


def _lint_json(vault: Path, seed: str) -> str:
    """Run the real CLI in a fresh process with ``PYTHONHASHSEED`` pinned."""
    proc = subprocess.run(
        [sys.executable, "-m", "llmwiki", "lint", "--vault", str(vault), "--json"],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONHASHSEED": seed},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_fixture_actually_produces_reorderable_findings(vault: Path) -> None:
    """Guard the guard: a single finding could never expose an ordering bug."""
    outcome = run_lint(load_pages(vault / "wiki"))
    links = [i for i in outcome.issues if i["rule"] == "link_integrity"]
    assert len(links) == len(_TARGETS) * _SOURCE_COUNT


def test_same_vault_lints_identically_under_different_hash_seeds(vault: Path) -> None:
    """The whole point: byte-identical JSON across processes, at stock settings."""
    payloads = [_lint_json(vault, seed) for seed in ("1", "2", "3", "17", "12345")]
    assert len(set(payloads)) == 1, (
        "lint --json is not deterministic across processes; "
        f"{len(set(payloads))} distinct payloads across {len(payloads)} hash seeds"
    )


def test_each_rules_findings_are_sorted_by_page_then_message(vault: Path) -> None:
    """The sort key is ``(page, message)`` — the property the payload relies on."""
    outcome = run_lint(load_pages(vault / "wiki"))
    by_rule: dict[str, list[tuple[str, str]]] = {}
    for issue in outcome.issues:
        by_rule.setdefault(issue["rule"], []).append((issue["page"], issue["message"]))
    for rule, keys in by_rule.items():
        assert keys == sorted(keys), f"{rule} findings are not sorted"


def test_rules_still_appear_in_registry_order(vault: Path) -> None:
    """Sorting is per rule. Sorting globally would reshuffle the rule blocks.

    ``llmwiki/lint/rules/__init__.py`` states the import order is deliberate so
    "any test or downstream consumer that relied on enumeration order continues
    to see the same sequence" — this pins that the determinism fix did not
    quietly trade one ordering contract for another.
    """
    outcome = run_lint(load_pages(vault / "wiki"))
    seen: list[str] = []
    for issue in outcome.issues:
        if issue["rule"] not in seen:
            seen.append(issue["rule"])
    assert seen == [name for name in REGISTRY if name in seen]
