"""Filler-vs-real precision of `contradiction_detection` (#150, R7).

Two demo pages defeated the rule: `None evident.` was not a recognised
"nothing to record" synonym, and a *hypothetical* conflict ("claims that
could conflict with prior wiki entries") read as a recorded one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.lint.rules import ContradictionDetection

# Verbatim ## Contradictions bodies from the committed demo vault.
DEMO_CONFIGURATION_REFERENCE_01 = (
    "None evident. (This is a reference document; contradictions with actual "
    "behavior should be noted when discovered.)"
)
DEMO_CLI_REFERENCE_07 = (
    "None identified. The document is reference material establishing CLI "
    "specifications and design rationale rather than making claims that could "
    "conflict with prior wiki entries."
)
# The genuine finding the rule correctly caught, before the docs were fixed.
DEMO_01_INSTALLATION_REAL = (
    '- **Python version requirement mismatch:** The frontmatter declares "Python '
    '3.12+" as a requirement, but Step 1 explicitly states "expect 3.9 or newer" '
    "and the troubleshooting section confirms ≥3.9 as sufficient. The documented "
    "requirement (3.9+) is less strict than the stated minimum (3.12+)."
)
# The replacement wording, now that docs/tutorials/01-installation.md agrees.
DEMO_01_INSTALLATION_FIXED = (
    "None identified. The tutorial's header, its verification step, and its "
    "troubleshooting section all state Python 3.12 as the minimum, matching what "
    "the project requires."
)


def _page(section_body: str) -> dict:
    body = f"## Contradictions\n{section_body}\n"
    return {
        "path": Path("x"),
        "rel": "x.md",
        "text": f"---\ntitle: A\n---\n{body}",
        "meta": {"title": "A"},
        "body": body,
    }


def _run(section_body: str) -> list[dict]:
    return ContradictionDetection().run({"x.md": _page(section_body)})


@pytest.mark.parametrize("section", [
    DEMO_CONFIGURATION_REFERENCE_01,
    DEMO_CLI_REFERENCE_07,
    DEMO_01_INSTALLATION_FIXED,
])
def test_demo_sections_are_filler(section):
    assert _run(section) == []


@pytest.mark.parametrize("section", [
    "None evident.",
    "*(None evident)*",
    "None evident in this session.",
    "None evident. This page is a reference document.",
])
def test_none_evident_is_filler(section):
    assert _run(section) == []


@pytest.mark.parametrize("modal", ["could", "would", "might", "may"])
def test_modal_conflict_is_hypothetical(modal):
    section = (
        "None identified. The document makes no claims that "
        f"{modal} conflict with prior wiki entries."
    )
    assert _run(section) == []


@pytest.mark.parametrize("modal", ["could", "would", "might", "may"])
def test_modal_conflict_without_negation_is_hypothetical(modal):
    section = f"None identified. Future edits {modal} conflict with prior guidance."
    assert _run(section) == []


def test_real_contradiction_still_flagged():
    """The genuine 01-installation finding must survive the precision fixes."""
    assert len(_run(DEMO_01_INSTALLATION_REAL)) == 1


def test_filler_opening_then_real_conflict_still_flagged():
    section = (
        "None in the summary. However, this page contradicts prior guidance: "
        "it says the default is 3 while [[Config]] says the default is 5."
    )
    assert len(_run(section)) == 1


def test_present_tense_conflict_still_flagged():
    """A recorded (non-modal) conflict is unaffected by the modal negators."""
    section = "This page conflicts with prior guidance on the default threshold."
    assert len(_run(section)) == 1
