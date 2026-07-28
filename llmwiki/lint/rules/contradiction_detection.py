"""contradiction_detection — flag pages with non-empty ## Contradictions sections.

Structural only: synthesis often emits a `## Contradictions` heading with
filler ("None identified.", etc.). Those are skipped so the rule surfaces
real recorded contradictions, not boilerplate.
"""

from __future__ import annotations

import re

from llmwiki.lint import LintRule, register

_SECTION_RE = re.compile(
    r"## Contradictions\n(.*?)(?:\n## |\Z)",
    re.DOTALL,
)

# Strip markdown emphasis / list markers, then collapse whitespace.
_FILLER_MARKUP_RE = re.compile(
    r"[*_`~\[\]()]+|^\s*[-*+]\s+|^\s*\d+\.\s+",
    re.MULTILINE,
)

# Synonyms that mean "nothing to record" after `none`.
_NONE_SYNONYMS = (
    r"identified|detected|found|noted|apparent|known|observed|recorded|"
    r"applicable|seen|introduced"
)

# Exact short placeholder lines (after normalize).
_FILLER_EXACT_RE = re.compile(
    r"^(?:"
    r"none"
    r"|none\s+(?:directly\s+)?(?:" + _NONE_SYNONYMS + r")"
    r"(?:\s+(?:in|from|with|within|against|relative\s+to|by)\b.*)?"
    r"|none\s*[—\-–]\s*no\s+claims\s+were\s+made(?:\s+in\s+this\s+session)?"
    r"|no\s+claims?\s+were\s+made(?:\s+in\s+this\s+session)?"
    r"|no\s+contradictions?"
    r"|n/?a"
    r")\.?$",
    re.IGNORECASE,
)

# Body opens as a negative stub ("None identified. This is a reference…").
# Deliberately does NOT match "None of the earlier claims hold…".
_FILLER_OPENING_RE = re.compile(
    r"^(?:"
    r"n/?a\b"
    r"|no\s+claims?\s+were\s+made\b"
    r"|no\s+contradictions?\b"
    r"|none\s+against\b"
    r"|none(?:\s*$|[.!?,;:]|"
    r"\s+(?:directly\s+)?(?:" + _NONE_SYNONYMS + r")\b|"
    r"\s*[—\-–])"
    r")",
    re.IGNORECASE,
)

# Affirmative conflict cues — keep the section flagged when present.
# Avoid bare "conflict with existing" — synthesis filler often says
# "does not conflict with existing wiki entries".
# Avoid bare `vs.` — filler often contrasts design modes ("unrestricted vs.
# restricted") without recording a wiki contradiction.
# `(?<!than )` skips "rather than conflicts with prior…".
_AFFIRMATIVE_CUE_RE = re.compile(
    r"(?:"
    r"contradicts\s+(?:earlier|prior|the\b|\[\[)"
    r"|while\s+others"
    r"|user\s+assumption"
    r"|receives\s+contradictory"
    r"|(?<!than )conflicts?\s+with\s+(?:earlier|prior)\b"
    r"|says\s+.+\s+while\s+.+\s+says"
    r")",
    re.IGNORECASE,
)


def _normalize_filler_line(line: str) -> str:
    text = _FILLER_MARKUP_RE.sub("", line)
    return " ".join(text.split()).strip()


def _is_filler_contradictions_body(section: str) -> bool:
    """True when the section is placeholder text, not a real conflict."""
    lines = [_normalize_filler_line(ln) for ln in section.splitlines()]
    lines = [ln for ln in lines if ln]
    if not lines:
        return True
    whole = " ".join(lines)
    if _AFFIRMATIVE_CUE_RE.search(whole):
        return False
    if _FILLER_OPENING_RE.match(whole):
        return True
    return all(_FILLER_EXACT_RE.match(ln) for ln in lines)


@register
class ContradictionDetection(LintRule):
    """Flag pages whose ## Contradictions section records a real conflict."""

    name = "contradiction_detection"
    severity = "warning"

    def run(self, pages, *, llm_callback=None):  # llm_callback kept for back-compat
        del llm_callback  # unused — reserved / legacy kwarg
        issues = []
        for rel, page in pages.items():
            if "## Contradictions" not in page["body"]:
                continue
            section_match = _SECTION_RE.search(page["body"])
            if not section_match:
                continue
            body = section_match.group(1).strip()
            if not body or _is_filler_contradictions_body(body):
                continue
            issues.append({
                "rule": self.name,
                "severity": "warning",
                "page": rel,
                "message": "page has ## Contradictions section — review required",
            })
        return issues
