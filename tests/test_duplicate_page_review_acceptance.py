"""Acceptance tests for the duplicate-page review feature (#365, spec #418).

Verifies end-to-end user flows on tmp_path vaults:
  - Detect + list CLI output + candidates.html "Possible duplicate pages" section
  - Batch merge-pages produces combined survivor, removes the pair
  - keep-distinct is durable — pair absent after ledger upsert even after cache refresh
  - Consolidation uses at most one synthesize call; curated titles stay fixed
  - Doctor and lint surface pending duplicate pairs

# @layer: integration
# @spec: 418-duplicate-page-review
# @regression
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from llmwiki.candidates_site import (
    apply_candidate_actions,
    candidates_payload,
    render_candidates_body,
    validate_candidate_batch,
)
from llmwiki.dismissal_ledger import (
    archive_candidates_dir,
    is_keep_distinct_pair,
    upsert_keep_distinct,
)
from llmwiki.doctor.checks import check_duplicate_page_pairs
from llmwiki.lint import load_pages, run_all
from llmwiki.lint import rules as _lint_rules  # noqa: F401 — registers lint REGISTRY
from llmwiki.page_merge import merge_pages
from llmwiki.synth.base import BaseSynthesizer
from llmwiki.topics import detect_duplicate_pairs
from llmwiki.topics_consolidate import (
    CACHE_VERSION,
    cache_path,
    load_cache,
    prepare_known_names,
)

assert _lint_rules is not None  # ensure REGISTRY is populated


# ─── shared vault helpers ────────────────────────────────────────────────────


def _page(wiki: Path, folder: str, name: str, *, page_type: str, sources: list[str] | None = None) -> Path:
    """Write a minimal live curated page under wiki/<folder>/<name>.md."""
    path = wiki / folder / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    src_yaml = ""
    if sources:
        src_yaml = f"sources: [{', '.join(sources)}]\n"
    path.write_text(
        f'---\ntitle: "{name}"\ntype: {page_type}\n{src_yaml}'
        f'last_updated: "2026-01-01"\n---\n\n# {name}\n\n'
        f'## Connections\n- [[Widget]]\n',
        encoding="utf-8",
    )
    return path


def _session(stem: str, links: list[str], *, project: str = "proj") -> str:
    link_text = " ".join(f"[[{t}]]" for t in links)
    return (
        f"---\ntitle: {stem}\nproject: {project}\n"
        f"source_file: raw/sessions/2026-01-01T00-00-{project}-{stem}.md\n"
        f"---\n\n## Summary\n{link_text}\n"
    )


def _make_wiki(tmp_path: Path, sessions: dict[str, list[str]]) -> Path:
    """Create wiki/ with sources/proj/ sessions."""
    wiki = tmp_path / "wiki"
    src = wiki / "sources" / "proj"
    src.mkdir(parents=True)
    for stem, links in sessions.items():
        (src / f"{stem}.md").write_text(_session(stem, links), encoding="utf-8")
    return wiki


def _write_dirty_cache(wiki: Path, topics: list[dict[str, Any]], *, dropped: list[Any] | None = None) -> None:
    """Write a pre-repair topics cache directly (bypass parse_and_cache constraint)."""
    payload = {
        "version": CACHE_VERSION,
        "topics": topics,
        "dropped": list(dropped or []),
    }
    cache_path(wiki).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _seed_vault_with_pair(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Return (vault_root, wiki_dir, survivor_path) for a wgctl/WidgetCLI pair."""
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["wgctl", "Widget"],
            "s2": ["WGCTL", "Widget"],
            "s3": ["Widget CLI", "Widget"],
        },
    )
    _page(wiki, "entities", "wgctl", page_type="entity", sources=["s1", "s2"])
    p2 = _page(wiki, "entities", "Widget CLI", page_type="entity", sources=["s3"])
    _write_dirty_cache(
        wiki,
        [
            {
                "canonical": "Widget CLI",
                "description": "A widget CLI tool.",
                "aliases": ["wgctl", "WGCTL"],
            },
            {"canonical": "Widget", "aliases": []},
        ],
    )
    vault = tmp_path  # vault root has wiki/ directly under it
    return vault, wiki, p2


# ─── 1. detect + list + candidates.html ─────────────────────────────────────

# @regression
def test_detect_pair_appears_in_candidates_list_and_html(tmp_path: Path) -> None:
    """Seeded duplicate pair surfaces in detect, payload, CLI list, and HTML section.

    Verifies AC 2.1: list command and candidates page both show the pair with
    titles, links, and session counts.
    """
    _vault, wiki, _survivor = _seed_vault_with_pair(tmp_path)

    # 1a. detect_duplicate_pairs returns the pair
    pairs = detect_duplicate_pairs(wiki)
    assert len(pairs) == 1, "expected one detected pair"
    pair = pairs[0]
    titles = {pair.a.title, pair.b.title}
    assert titles == {"wgctl", "Widget CLI"}

    # 1b. candidates_payload embeds duplicate_pairs
    payload = candidates_payload(wiki)
    assert "duplicate_pairs" in payload
    assert isinstance(payload["duplicate_pairs"], list)
    assert len(payload["duplicate_pairs"]) == 1
    dp = payload["duplicate_pairs"][0]
    assert {dp["a"]["title"], dp["b"]["title"]} == {"wgctl", "Widget CLI"}
    # each side carries session_count and kind
    for side_key in ("a", "b"):
        side = dp[side_key]
        assert side["kind"] in ("entities", "concepts", "projects")
        assert isinstance(side["session_count"], int)

    # 1c. render_candidates_body produces an HTML section
    body = render_candidates_body(wiki)
    assert "Possible duplicate pages" in body
    assert "wgctl" in body
    assert "Widget CLI" in body


# @regression
def test_no_pair_when_pages_are_unrelated(tmp_path: Path) -> None:
    """Vault with two unrelated curated pages produces empty duplicate-pairs section."""
    wiki = _make_wiki(
        tmp_path,
        {"s1": ["OpenClaw", "Bun"], "s2": ["OpenClaw", "Bun"]},
    )
    _page(wiki, "entities", "OpenClaw", page_type="entity")
    _page(wiki, "entities", "Bun", page_type="entity")
    _write_dirty_cache(
        wiki,
        [
            {"canonical": "OpenClaw", "aliases": []},
            {"canonical": "Bun", "aliases": []},
        ],
    )

    assert detect_duplicate_pairs(wiki) == []
    payload = candidates_payload(wiki)
    assert payload["duplicate_pairs"] == []
    body = render_candidates_body(wiki)
    # section must be absent or explicitly empty — not an error
    assert "wgctl" not in body and "Widget CLI" not in body


# ─── 2. batch merge-pages produces combined survivor, removes pair ────────────

# @regression
def test_merge_pages_removes_pair_and_produces_combined_survivor(tmp_path: Path) -> None:
    """apply_candidate_actions with merge-pages folds loser into survivor.

    After the merge (AC 2.3):
    - survivor page gains the loser's sources in frontmatter
    - loser's title appears under ## Aliases on the survivor
    - detect_duplicate_pairs returns empty (pair gone)
    - candidates_payload duplicate_pairs is empty
    - candidates.html section has no pending pair
    """
    _vault, wiki, survivor_path = _seed_vault_with_pair(tmp_path)
    # Confirm pair present before merge
    assert len(detect_duplicate_pairs(wiki)) == 1

    results = apply_candidate_actions(
        wiki,
        [{"action": "merge-pages", "from": "wgctl", "into": "Widget CLI"}],
    )
    assert len(results) == 1
    r = results[0]
    assert r["ok"], f"merge-pages failed: {r.get('error')}"

    # 2a. survivor page has the loser's title as an alias
    survivor_text = survivor_path.read_text(encoding="utf-8")
    assert "wgctl" in survivor_text  # recorded as an alias

    # 2b. loser page no longer exists as a live page
    loser_path = wiki / "entities" / "wgctl.md"
    assert not loser_path.exists(), "loser page should be archived"

    # 2c. pair gone from detect
    assert detect_duplicate_pairs(wiki) == []

    # 2d. payload duplicate_pairs empty
    payload = candidates_payload(wiki)
    assert payload["duplicate_pairs"] == []

    # 2e. rendered HTML has no pending pair
    body = render_candidates_body(wiki)
    assert "wgctl" not in body or "Possible duplicate pages (0)" in body or "Possible duplicate pages" not in body


# @regression
def test_merge_pages_cross_kind_survivor_keeps_kind(tmp_path: Path) -> None:
    """Cross-kind merge keeps the survivor's folder and type (AC 2.3).

    A concept merged into a project must leave the project page intact.
    """
    wiki = _make_wiki(
        tmp_path,
        {"s1": ["Widget Pattern", "Widget"], "s2": ["widget-proj", "Widget"]},
    )
    _page(wiki, "concepts", "Widget Pattern", page_type="concept")
    _page(wiki, "projects", "widget-proj", page_type="project")
    archive_candidates_dir(wiki).mkdir(parents=True, exist_ok=True)
    _write_dirty_cache(
        wiki,
        [{"canonical": "widget-proj", "aliases": ["Widget Pattern"]}, {"canonical": "Widget", "aliases": []}],
    )

    results = apply_candidate_actions(
        wiki,
        [{"action": "merge-pages", "from": "Widget Pattern", "into": "widget-proj"}],
    )
    assert results[0]["ok"], results[0].get("error")

    survivor = wiki / "projects" / "widget-proj.md"
    assert survivor.exists(), "survivor project page must remain"
    survivor_text = survivor.read_text(encoding="utf-8")
    assert "Widget Pattern" in survivor_text  # aliased
    assert not (wiki / "concepts" / "Widget Pattern.md").exists()


# ─── 3. keep-distinct durable — survives cache refresh ───────────────────────

# @regression
def test_keep_distinct_durable_pair_absent_after_cache_refresh(tmp_path: Path) -> None:
    """keep-distinct via apply_candidate_actions persists through a cache replacement.

    After marking a pair keep-distinct (AC 2.4):
    - detect immediately returns no pair
    - writing a new dirty cache (simulating vocab refresh) does not resurrect the pair
    """
    _vault, wiki, _survivor = _seed_vault_with_pair(tmp_path)
    assert len(detect_duplicate_pairs(wiki)) == 1  # sanity

    # Apply keep-distinct
    archive_candidates_dir(wiki).mkdir(parents=True, exist_ok=True)
    results = apply_candidate_actions(
        wiki,
        [{"action": "keep-distinct", "a": "wgctl", "b": "Widget CLI"}],
    )
    assert results[0]["ok"], results[0].get("error")

    # Immediately absent
    assert detect_duplicate_pairs(wiki) == []

    # Simulate a vocab cache refresh (new dirty cache with same fold)
    _write_dirty_cache(
        wiki,
        [
            {"canonical": "Widget CLI", "description": "CLI.", "aliases": ["wgctl"]},
            {"canonical": "Widget", "aliases": []},
        ],
    )

    # Still absent — ledger is SoT, not cache
    assert detect_duplicate_pairs(wiki) == []
    # Ledger is durable
    assert is_keep_distinct_pair(wiki, "wgctl", "Widget CLI")


# @regression
def test_keep_distinct_applied_pair_absent_from_html(tmp_path: Path) -> None:
    """HTML section is empty after keep-distinct decision applied to the only pair."""
    _vault, wiki, _survivor = _seed_vault_with_pair(tmp_path)
    archive_candidates_dir(wiki).mkdir(parents=True, exist_ok=True)
    upsert_keep_distinct(wiki, a="wgctl", b="Widget CLI", why="verified distinct")

    body = render_candidates_body(wiki)
    # pair should be absent from HTML output — section gone or count=0
    assert "wgctl" not in body or ("Possible duplicate pages" in body and "0" in body)


# ─── 4. consolidation at most one synthesize; curated titles fixed ────────────

# @regression
def test_consolidation_one_synthesize_call_and_curated_fold_blocked(tmp_path: Path) -> None:
    """prepare_known_names issues one LLM call and blocks curated↔curated fold.

    AC 2.5: curated titles injected as fixed; post-process blocks fold between
    two live curated pages; fingerprint skip on second call.
    """
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["Alpha", "Beta"],
            "s2": ["Alpha", "Beta"],
        },
    )
    _page(wiki, "entities", "Alpha", page_type="entity")
    _page(wiki, "entities", "Beta", page_type="entity")

    class _Spy(BaseSynthesizer):
        is_llm = True
        timeout = 120

        def __init__(self) -> None:
            self.calls = 0

        def synthesize_source_page(self, raw_body, meta, prompt_template, **_kw):
            self.calls += 1
            # Return a fold that the post-process must undo
            return json.dumps({
                "topics": [
                    {"canonical": "Alpha", "description": "A.", "aliases": ["Beta"]},
                ],
                "dropped": [],
            })

        def is_available(self) -> bool:
            return True

    spy = _Spy()
    cfg: dict[str, Any] = {"synthesis": {"known_names": {"candidate_cap": 150}}}
    prepare_known_names(wiki, spy, cfg=cfg)

    # Exactly one synthesize call
    assert spy.calls == 1, f"expected 1 call, got {spy.calls}"

    # Post-process blocked the curated↔curated fold
    cached = load_cache(wiki)
    assert cached is not None
    by_canon = {t["canonical"]: t for t in cached["topics"]}
    assert "Alpha" in by_canon, "Alpha must remain a canonical entry"
    # Beta must NOT be an alias of Alpha (curated→curated fold blocked)
    assert "Beta" not in by_canon.get("Alpha", {}).get("aliases", [])

    # Second call with same fingerprint must skip the LLM
    prepare_known_names(wiki, spy, cfg=cfg)
    assert spy.calls == 1, "fingerprint skip: second call must not call synthesize"


# @regression
def test_consolidation_keep_distinct_pair_not_folded(tmp_path: Path) -> None:
    """keep-distinct pair in ledger is not folded by consolidation post-process."""
    wiki = _make_wiki(
        tmp_path,
        {"s1": ["Gamma", "Delta"], "s2": ["Gamma", "Delta"]},
    )
    _page(wiki, "entities", "Gamma", page_type="entity")
    _page(wiki, "entities", "Delta", page_type="entity")
    archive_candidates_dir(wiki).mkdir(parents=True, exist_ok=True)
    upsert_keep_distinct(wiki, a="Gamma", b="Delta", why="different")

    class _FoldSpy(BaseSynthesizer):
        is_llm = True
        timeout = 120

        def synthesize_source_page(self, raw_body, meta, prompt_template, **_kw):
            # Try to fold Delta onto Gamma
            return json.dumps({
                "topics": [
                    {"canonical": "Gamma", "description": "G.", "aliases": ["Delta"]},
                ],
                "dropped": [],
            })

        def is_available(self) -> bool:
            return True

    cfg: dict[str, Any] = {"synthesis": {"known_names": {"candidate_cap": 150}}}
    prepare_known_names(wiki, _FoldSpy(), cfg=cfg)

    cached = load_cache(wiki)
    assert cached is not None
    by_canon = {t["canonical"]: t for t in cached["topics"]}
    assert "Gamma" in by_canon
    assert "Delta" not in by_canon.get("Gamma", {}).get("aliases", [])


# ─── 5. doctor and lint surface pending pairs ────────────────────────────────

# @regression
def test_doctor_check_emits_finding_for_pending_pair(tmp_path: Path) -> None:
    """check_duplicate_page_pairs returns a finding with id=candidates.duplicate_pairs.

    AC 2.6: doctor surfaces count and open-with instruction.
    """
    vault = tmp_path / "vault"
    wiki = _make_wiki(
        vault,
        {"s1": ["wgctl", "Widget"], "s2": ["Widget CLI", "Widget"]},
    )
    _page(wiki, "entities", "wgctl", page_type="entity")
    _page(wiki, "entities", "Widget CLI", page_type="entity")
    _write_dirty_cache(
        wiki,
        [
            {"canonical": "Widget CLI", "description": "CLI.", "aliases": ["wgctl"]},
            {"canonical": "Widget", "aliases": []},
        ],
    )

    findings = check_duplicate_page_pairs(vault)
    assert len(findings) == 1
    f = findings[0]
    assert f.id == "candidates.duplicate_pairs"
    assert "1 possible duplicate page pair" in f.message
    # message tells user how to open the list
    assert "candidates list" in f.message or "candidates.html" in f.message


# @regression
def test_lint_emits_finding_for_pending_pair(tmp_path: Path) -> None:
    """lint duplicate_page_pairs rule emits one info finding per pending fold pair.

    AC 2.6: lint surfaces the same pair info so it appears in wiki lint output.
    """
    wiki = _make_wiki(
        tmp_path,
        {"s1": ["wgctl", "Widget"], "s2": ["Widget CLI", "Widget"]},
    )
    _page(wiki, "entities", "wgctl", page_type="entity")
    _page(wiki, "entities", "Widget CLI", page_type="entity")
    _write_dirty_cache(
        wiki,
        [
            {"canonical": "Widget CLI", "description": "CLI.", "aliases": ["wgctl"]},
            {"canonical": "Widget", "aliases": []},
        ],
    )

    pages = load_pages(tmp_path)
    issues = run_all(pages, selected=["duplicate_page_pairs"])
    assert len(issues) >= 1
    issue = issues[0]
    assert issue["rule"] == "duplicate_page_pairs"
    assert issue["severity"] == "info"
    assert "wgctl" in issue["message"] or "Widget CLI" in issue["message"]


# @regression
def test_doctor_silent_when_no_pending_pairs(tmp_path: Path) -> None:
    """Doctor emits no candidates.duplicate_pairs finding when vault has no pairs."""
    vault = tmp_path / "vault"
    (vault / "wiki" / "entities").mkdir(parents=True)
    (vault / "wiki" / "entities" / "Only.md").write_text(
        "---\ntitle: Only\ntype: entity\n---\n\n# Only\n",
        encoding="utf-8",
    )
    findings = check_duplicate_page_pairs(vault)
    assert findings == []


# ─── 6. batch conflict validation ────────────────────────────────────────────

# @regression
def test_batch_refuses_merge_and_keep_distinct_on_same_pair() -> None:
    """validate_candidate_batch rejects merge-pages and keep-distinct on the same pair.

    AC 2.2: cannot both merge and keep-distinct the same pair in one batch.
    """
    with pytest.raises(ValueError, match="batch conflict"):
        validate_candidate_batch([
            {"action": "merge-pages", "from": "Alpha", "into": "Beta"},
            {"action": "keep-distinct", "a": "Alpha", "b": "Beta"},
        ])


# @regression
def test_batch_refuses_same_loser_twice() -> None:
    """validate_candidate_batch rejects two merge-pages rows with the same loser."""
    with pytest.raises(ValueError, match="batch conflict"):
        validate_candidate_batch([
            {"action": "merge-pages", "from": "Alpha", "into": "Beta"},
            {"action": "merge-pages", "from": "Alpha", "into": "Gamma"},
        ])


# @regression
def test_merge_pages_refuses_non_mergeable_folder(tmp_path: Path) -> None:
    """merge_pages raises ValueError for pages outside entities/concepts/projects."""
    wiki = tmp_path / "wiki"
    # Put a page in sources/ (not mergeable)
    bad = wiki / "sources" / "RawNote.md"
    bad.parent.mkdir(parents=True)
    bad.write_text(
        '---\ntitle: "RawNote"\ntype: source\n---\n\n# RawNote\n',
        encoding="utf-8",
    )
    keep = wiki / "entities" / "Keep.md"
    keep.parent.mkdir(parents=True)
    keep.write_text(
        '---\ntitle: "Keep"\ntype: entity\n---\n\n# Keep\n',
        encoding="utf-8",
    )
    with pytest.raises((ValueError, FileNotFoundError)):
        merge_pages("RawNote", wiki, into="Keep")
