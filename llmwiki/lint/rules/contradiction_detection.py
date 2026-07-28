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
_FILLER_BODY_RE = re.compile(
    r"^(?:"
    r"none"
    r"|none\s+identified(?:\s+against\s+existing\s+wiki\s+content)?"
    r"|none\s+noted"
    r"|none\s*[—\-–]\s*no\s+claims\s+were\s+made(?:\s+in\s+this\s+session)?"
    r"|no\s+claims\s+were\s+made(?:\s+in\s+this\s+session)?"
    r"|n/?a"
    r")\.?$",
    re.IGNORECASE,
)


def _normalize_filler_line(line: str) -> str:
    text = _FILLER_MARKUP_RE.sub("", line)
    return " ".join(text.split()).strip()


def _is_filler_contradictions_body(section: str) -> bool:
    """True when every non-empty line is placeholder text, not a real conflict."""
    lines = [_normalize_filler_line(ln) for ln in section.splitlines()]
    lines = [ln for ln in lines if ln]
    if not lines:
        return True
    return all(_FILLER_BODY_RE.match(ln) for ln in lines)


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
