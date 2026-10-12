"""Whole-feature acceptance for prior discard reasons on near-match candidates (#146).

# @layer: integration
# @spec: 326-harvest-discard-reason-surface
# @regression

Unit and slice coverage lives in ``tests/test_dismissal_ledger.py``,
``tests/test_candidates_near_match.py``, ``tests/test_candidates.py``,
``tests/test_candidates_site.py``, and ``tests/test_migrate_dismissal_ledger.py``.
This file is **glue**: one vault journey per FR cluster from
``context/spec/326-harvest-discard-reason-surface/functional-spec.md`` (FR1–FR6).

True near-matches use ``FooBars`` vs discarded ``Foobar`` (distinct
``norm_page_key``, SequenceMatcher ≥ 0.90). ``FooBar`` / ``Foobar`` fold equal
and must not be treated as a near-match.

AC coverage matrix:

    FR1 near-match stays + marked (list + site)  -> test_near_match_stays_in_queue_marked_on_list_and_site
    FR2 reason / empty placeholder               -> test_near_match_stays_in_queue_marked_on_list_and_site;
                                                   test_empty_reason_shows_discarded_without_explanation
    FR4 exact settled not re-proposed / unmarked -> test_exact_settled_name_not_reproposed_or_near_matched
    FR5 merge is not a prior dismissal           -> test_merge_not_marked_as_prior_dismissal
    FR6 ledger write + migrate/load rebuild      -> test_new_discard_writes_ledger_not_reason_txt;
                                                   test_migrate_and_load_rebuild_legacy_reasons_surface
"""

from __future__ import annotations

import json
from pathlib import Path

from llmwiki.build import render_candidates_page
from llmwiki.candidates import archive_dir, discard, list_candidates, merge
from llmwiki.candidates_harvest import harvest_targets
from llmwiki.candidates_near_match import EMPTY_REASON_DISPLAY
from llmwiki.candidates_site import render_candidates_body
from llmwiki.cli import build_parser
from llmwiki.dismissal_ledger import (
    archive_candidates_dir,
    iter_dismissals,
    ledger_path,
    load_ledger,
)
from llmwiki.wikilinks import norm_page_key
from tests import test_candidates as candidates_tests
from tests import test_dismissal_ledger as ledger_tests

REASON = "hosting detail, not subject matter"


def _mk_wiki(tmp_path: Path) -> Path:
    return candidates_tests._mk_wiki(tmp_path)


def _write_candidate(wiki: Path, kind: str, slug: str, **kwargs) -> Path:
    return candidates_tests._write_candidate(wiki, kind, slug, **kwargs)


def _cite_in_sources(wiki: Path, name: str, *, n: int = 3) -> None:
    """Plant ``n`` source pages that each wikilink ``name`` (enough for harvest)."""
    sources = wiki / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (sources / f"s{i}.md").write_text(
            f"---\ntitle: s{i}\ntype: source\n---\n\n"
            f"## Connections\n- [[{name}]] — mentioned again\n",
            encoding="utf-8",
        )


# @regression
def test_near_match_stays_in_queue_marked_on_list_and_site(
    tmp_path: Path, capsys
) -> None:
    """FR1 + FR2: FooBars stays pending, marked on CLI list and candidates.html.

    # @spec: 326-harvest-discard-reason-surface
    """
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Foobar")
    discard("Foobar", wiki, reason=REASON)
    _write_candidate(wiki, "entities", "FooBars", date="2026-04-15")
    _write_candidate(wiki, "entities", "Unrelated")

    assert norm_page_key("Foobar") != norm_page_key("FooBars")
    assert norm_page_key("Foobar") == norm_page_key("FooBar")

    items = {c["slug"]: c for c in list_candidates(wiki)}
    assert "FooBars" in items
    prior = items["FooBars"]["prior_dismissal"]
    assert prior["name"] == "Foobar"
    assert prior["reason"] == REASON
    assert prior["ratio"] >= 0.90
    assert "prior_dismissal" not in items["Unrelated"]

    args = build_parser().parse_args([
        "candidates", "list", "--wiki-dir", str(wiki),
    ])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "[entities ] FooBars" in out
    assert "prior dismissals:" in out
    assert f'- "Foobar" — {REASON}' in out
    assert "\n        prior dismissals:" in out

    site = tmp_path / "site"
    site.mkdir()
    html_path = render_candidates_page(wiki, site)
    html = html_path.read_text(encoding="utf-8")
    assert 'class="muted cand-prior-dismissals"' in html
    assert "Prior dismissals:" in html
    assert f"&quot;Foobar&quot; — {REASON}" in html
    assert "Discard with prior reason" in html
    assert "Unrelated" in html


# @regression
def test_empty_reason_shows_discarded_without_explanation(tmp_path: Path, capsys) -> None:
    """FR2: empty recorded reason displays as (discarded without explanation).

    # @spec: 326-harvest-discard-reason-surface
    """
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "concepts", "ApiClient")
    discard("ApiClient", wiki, reason="")
    _write_candidate(wiki, "concepts", "ApiClients", date="2026-04-17")

    items = {c["slug"]: c for c in list_candidates(wiki)}
    assert items["ApiClients"]["prior_dismissal"]["reason"] == ""

    args = build_parser().parse_args([
        "candidates", "list", "--wiki-dir", str(wiki),
    ])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert f'- "ApiClient" — {EMPTY_REASON_DISPLAY}' in out

    body = render_candidates_body(wiki)
    assert f"&quot;ApiClient&quot; — {EMPTY_REASON_DISPLAY}" in body
    assert "Prior dismissals:" in body


# @regression
def test_exact_settled_name_not_reproposed_or_near_matched(tmp_path: Path) -> None:
    """FR4: same folded key stays out of harvest and is not a prior_dismissal mark.

    # @spec: 326-harvest-discard-reason-surface
    """
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Foobar")
    discard("Foobar", wiki, reason=REASON)
    _cite_in_sources(wiki, "FooBar", n=3)

    proposed = {t.name for t in harvest_targets(wiki, min_refs=3)}
    assert "Foobar" not in proposed
    assert "FooBar" not in proposed
    assert "foobar" not in {norm_page_key(n) for n in proposed}

    # Exact fold planted as pending must not get a near-match annotation.
    _write_candidate(wiki, "entities", "FooBar")
    _write_candidate(wiki, "entities", "FooBars")
    items = {c["slug"]: c for c in list_candidates(wiki)}
    assert "prior_dismissal" not in items["FooBar"]
    assert items["FooBars"]["prior_dismissal"]["name"] == "Foobar"


# @regression
def test_merge_not_marked_as_prior_dismissal(tmp_path: Path) -> None:
    """FR5: a merge is not a dismissal — near-match of the merged name stays unmarked.

    # @spec: 326-harvest-discard-reason-surface
    """
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "MergedThing")
    (wiki / "entities" / "Main.md").write_text("# Main\n", encoding="utf-8")
    merge("MergedThing", wiki, into_slug="Main")
    _write_candidate(wiki, "entities", "MergedThings")

    items = {c["slug"]: c for c in list_candidates(wiki)}
    assert "MergedThings" in items
    assert "prior_dismissal" not in items["MergedThings"]
    assert list(iter_dismissals(wiki)) == []


# @regression
def test_new_discard_writes_ledger_not_reason_txt(tmp_path: Path) -> None:
    """FR6: discard upserts dismissals.json and does not create *.reason.txt.

    # @spec: 326-harvest-discard-reason-surface
    """
    wiki = _mk_wiki(tmp_path)
    _write_candidate(wiki, "entities", "Fake")
    archived = discard("Fake", wiki, reason=REASON).path

    assert ledger_path(wiki).is_file()
    assert not archived.with_suffix(".reason.txt").is_file()
    assert all(
        not p.with_suffix(".reason.txt").is_file()
        for p in archive_dir(wiki).rglob("*.md")
    )
    rows = list(iter_dismissals(wiki))
    assert len(rows) == 1
    assert rows[0]["name"] == "Fake"
    assert rows[0]["reason"] == REASON


# @regression
def test_migrate_and_load_rebuild_legacy_reasons_surface(
    tmp_path: Path, capsys
) -> None:
    """FR6: migrate dismissal-ledger / load_ledger rebuild import legacy reason files.

    # @spec: 326-harvest-discard-reason-surface
    """
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    for sub in ("entities", "concepts"):
        (wiki / sub).mkdir(parents=True, exist_ok=True)
        (wiki / "candidates" / sub).mkdir(parents=True, exist_ok=True)
    archive = archive_candidates_dir(wiki)
    archive.mkdir(parents=True)

    ledger_tests._write_stub(
        archive,
        "2026-03-01T12-00-00/Foobar.md",
        title="Foobar",
        reason=REASON,
    )
    assert not ledger_path(wiki).is_file()

    args = build_parser().parse_args([
        "migrate", "dismissal-ledger", "--vault", str(vault),
    ])
    assert args.func(args) == 0
    assert ledger_path(wiki).is_file()
    data = json.loads(ledger_path(wiki).read_text(encoding="utf-8"))
    assert data["dismissals"][0]["name"] == "Foobar"
    assert data["dismissals"][0]["reason"] == REASON

    _write_candidate(wiki, "entities", "FooBars")
    items = {c["slug"]: c for c in list_candidates(wiki)}
    assert items["FooBars"]["prior_dismissal"]["reason"] == REASON

    # Auto-rebuild path: remove ledger, keep legacy reason file, load_ledger imports.
    ledger_path(wiki).unlink()
    assert not ledger_path(wiki).is_file()
    rebuilt = load_ledger(wiki)
    assert ledger_path(wiki).is_file()
    assert rebuilt["dismissals"][0]["reason"] == REASON

    capsys.readouterr()
    list_args = build_parser().parse_args([
        "candidates", "list", "--wiki-dir", str(wiki),
    ])
    assert list_args.func(list_args) == 0
    out = capsys.readouterr().out
    assert f'- "Foobar" — {REASON}' in out
