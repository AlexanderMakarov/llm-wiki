"""Fold ``llmwiki lint`` issues into doctor findings (area I / J).

Skip lint when early actionable env findings block further work, or when the
run is a pure ``--error`` lookup. Map known rules to catalog ids; otherwise
emit ``lint:<rule>``. Honor ``auto_fixable`` → safe runners where mapped
(especially ``index_sync`` → ``reindex``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmwiki.doctor.kb import finding_from_entry, get_entry
from llmwiki.doctor.models import Finding, FixTier
from llmwiki.lint import REGISTRY, load_pages, run_lint

#: Lint rule name → heal-catalog id (when the catalog owns a dedicated row).
RULE_TO_CATALOG_ID: dict[str, str] = {
    "index_sync": "lint.index_sync",
    "provenance_integrity": "provenance.broken_chain",
}

#: auto_fixable rules → safe runner ids doctor may execute after confirm.
RULE_TO_SAFE_RUNNER: dict[str, str] = {
    "index_sync": "reindex",
}

#: Plain-language what-to-do for lint rules (never "Address lint rule …").
RULE_HUMAN_FIX: dict[str, str] = {
    "claim_verification": (
        "Open the named page and add citations under ## Sources (or [[wikilinks]] "
        "to source pages) for each claim, or remove unsupported claims."
    ),
    "content_freshness": (
        "Refresh the page from newer sources (update Key Facts / last_updated), "
        "or archive it if it is no longer needed."
    ),
    "contradiction_detection": (
        "Open ## Contradictions on the named page and resolve the conflict "
        "(pick one claim, or keep both with an explicit decision note)."
    ),
    "duplicate_detection": (
        "Merge or remove the duplicate page: keep one canonical page, retarget "
        "links, or discard the weaker stub via llmwiki candidates."
    ),
    "frontmatter_completeness": (
        "Fill missing frontmatter fields on the named page (title, type, tags/topics, "
        "last_updated as required for that page kind)."
    ),
    "frontmatter_validity": (
        "Fix invalid frontmatter on the named page so YAML parses and required "
        "fields use allowed values."
    ),
    "index_sync": (
        "Rewrite wiki/index.md from pages on disk (doctor can run reindex). "
        "This is catalog drift, not “candidates are bad”: any page under wiki/ "
        "(including candidates/) should appear in the index. Reindex only updates "
        "the catalog — it does not promote or delete candidates. If skipped, "
        "Home/index navigation and counts omit those pages."
    ),
    "link_integrity": (
        "Fix or remove the broken [[wikilink]]: create the missing page, correct "
        "the spelling, or delete the link."
    ),
    "orphan_detection": (
        "Add an inbound [[wikilink]] from a related page, list it in a parent "
        "Connections section, or discard the page if it should not exist."
    ),
    "page_findability": (
        "Give the page a clear frontmatter title and ensure search/index can "
        "find it; rename or retitle if the title is empty or colliding."
    ),
    "provenance_integrity": (
        "Repair the sources: → wiki source → source_file: → raw chain "
        "(llmwiki trace, synth, or migrate broken-provenance as appropriate)."
    ),
    "stale_candidates": (
        "Review with llmwiki candidates — promote, merge, or discard the stub."
    ),
    "stale_reference_detection": (
        "Update or remove the dated claim so it matches the newer target page."
    ),
    "stub_source_pages": (
        "Run llmwiki synth so stub source pages get real summaries, or remove "
        "stubs that should not remain."
    ),
    "tags_topics_convention": (
        "On project pages use topics: (not tags:); edit frontmatter or run "
        "llmwiki tag rename <old> <new> as appropriate."
    ),
    "title_ambiguity": (
        "Disambiguate colliding titles (rename one page or clarify the title "
        "in frontmatter)."
    ),
}

#: Areas whose error-severity actionable findings make lint useless until healed.
_EARLY_ENV_AREAS = frozenset("ABCDEF")


def should_skip_lint(
    *,
    error_lookup: bool = False,
    early_findings: list[Finding] | None = None,
) -> bool:
    """True when the lint stage must not run (R7 / tech §2.6 step 4)."""
    if error_lookup:
        return True
    for finding in early_findings or ():
        if (
            finding.actionable
            and finding.severity == "error"
            and finding.area in _EARLY_ENV_AREAS
        ):
            return True
    return False


def _rule_auto_fixable(rule: str) -> bool:
    cls = REGISTRY.get(rule)
    if cls is None:
        return False
    return bool(getattr(cls, "auto_fixable", False))


def finding_from_lint_issue(issue: dict[str, Any]) -> Finding:
    """Map one lint issue dict to a :class:`Finding` (dedupe by caller)."""
    rule = str(issue.get("rule") or "unknown")
    catalog_id = RULE_TO_CATALOG_ID.get(rule)
    page = str(issue.get("page") or "")
    message = str(issue.get("message") or rule)
    if rule == "index_sync":
        # Make catalog-drift vs “bad candidate” explicit in the headline.
        detail = (
            f"Catalog drift in wiki/index.md: {message}"
            + (f" (index path={page})" if page else "")
            + ". The page on disk is fine to keep; the catalog just does not "
            "list it yet (or lists a ghost path)."
        )
    elif page:
        detail = f"{message} (page={page})"
    else:
        detail = message

    if catalog_id is not None:
        entry = get_entry(catalog_id)
        if entry is not None:
            return finding_from_entry(entry, message=detail)

    runner: str | None = None
    tier = FixTier.GUIDED
    if _rule_auto_fixable(rule) and rule in RULE_TO_SAFE_RUNNER:
        runner = RULE_TO_SAFE_RUNNER[rule]
        tier = FixTier.SAFE
    human = RULE_HUMAN_FIX.get(rule)
    issue_fix = issue.get("fix")
    if human:
        fix = human
    elif issue_fix:
        fix = str(issue_fix)
    else:
        fix = (
            f"Inspect the named page and correct what {rule} reported "
            f"(details: llmwiki lint --rules {rule})."
        )
    return Finding(
        id=f"lint:{rule}",
        area="I",
        message=detail,
        fix=fix,
        actionable=True,
        severity=str(issue.get("severity") or "warning"),
        tier=tier,
        runner=runner,
    )


def fold_lint_issues(issues: list[dict[str, Any]]) -> list[Finding]:
    """Collapse lint issues into one finding per catalog id / ``lint:<rule>``.

    Multiple pages with the same rule share one finding; the message names the
    first issue and notes how many more exist.
    """
    by_key: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for issue in issues:
        rule = str(issue.get("rule") or "unknown")
        key = RULE_TO_CATALOG_ID.get(rule, f"lint:{rule}")
        if key not in by_key:
            order.append(key)
            by_key[key] = []
        by_key[key].append(issue)

    findings: list[Finding] = []
    for key in order:
        group = by_key[key]
        base = finding_from_lint_issue(group[0])
        if len(group) > 1:
            extra = len(group) - 1
            message = f"{base.message} (+{extra} more)"
            base = Finding(
                id=base.id,
                area=base.area,
                message=message,
                fix=base.fix,
                actionable=base.actionable,
                severity=base.severity,
                tier=base.tier,
                runner=base.runner,
            )
        findings.append(base)
    return findings


def run_lint_fold(vault: Path) -> list[Finding]:
    """Load wiki pages, run lint, and fold issues into findings."""
    wiki_dir = Path(vault) / "wiki"
    # Ensure rules register before REGISTRY lookups in fold helpers.
    from llmwiki.lint import rules as _rules  # noqa: F401, PLC0415

    pages = load_pages(wiki_dir)
    if not pages:
        return []
    outcome = run_lint(pages)
    return fold_lint_issues(outcome.issues)
