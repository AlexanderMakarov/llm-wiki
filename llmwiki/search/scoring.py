"""Pure per-page scoring for wiki search (#197).

No I/O. Tokenisation lives on :class:`ExtractQuery` so it runs once per
query, not once per page (the MCP loop used to re-split on every file).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from llmwiki.search.corpus import ScannedPage


@dataclass(frozen=True, slots=True)
class ExtractQuery:
    """Pre-parsed extract-mode query: raw string, lowercased form, tokens."""

    raw: str
    lower: str
    tokens: list[str]

    @classmethod
    def parse(cls, question: str) -> ExtractQuery:
        """Tokenise ``question`` once. Caller strips empty / whitespace checks."""
        lower = question.lower()
        tokens = [t for t in re.split(r"\W+", lower) if t]
        return cls(raw=question, lower=lower, tokens=tokens)


@dataclass(frozen=True, slots=True)
class MatchedPage:
    """One page that matched a literal term (match mode)."""

    rel_path: str
    title: str
    name_match: bool
    lines: tuple[tuple[int, str], ...]


def score_extract(page: ScannedPage, query: ExtractQuery) -> float:
    """Length-normalised extract score (#418), arithmetic unchanged from MCP.

    Body: +50 whole-phrase, +10 per token, divided by
    ``log2(max(len(text), 256))``. Title: +100 phrase, +20 per token,
    unnormalised.
    """
    body_score = 0
    if query.lower in page.text_lower:
        body_score += 50
    body_score += sum(10 for t in query.tokens if t in page.text_lower)
    if body_score > 0:
        length_factor = math.log2(max(len(page.text), 256))
        normalised_body = body_score / length_factor
    else:
        normalised_body = 0.0

    title_score = 0.0
    title = page.title.lower()
    if title:
        if query.lower in title:
            title_score += 100
        title_score += sum(20 for t in query.tokens if t in title)
    return normalised_body + title_score


def extract_snippet(
    content: str, tokens: list[str], *, max_chars: int = 400
) -> str:
    """Return a ~``max_chars`` window centred on the first token match, or a prefix.

    Shared by phrase / extract mode (page body) and term / match mode (each
    matching line). Default 400 characters total (±200 around the hit).
    """
    content_lower = content.lower()
    for token in tokens:
        idx = content_lower.find(token)
        if idx >= 0:
            start = max(0, idx - max_chars // 2)
            end = min(len(content), idx + max_chars // 2)
            prefix = "…" if start > 0 else ""
            suffix = "…" if end < len(content) else ""
            return prefix + content[start:end] + suffix
    return content[:max_chars] + ("…" if len(content) > max_chars else "")


def match_page(
    page: ScannedPage,
    term_lower: str,
    kind: str = "",
) -> MatchedPage | None:
    """Return a match for ``term_lower``, or ``None`` if filtered / no hit.

    ``kind`` filters on frontmatter ``type`` (case-insensitive). Empty
    ``kind`` means no filter. Name match is title or relative path; body
    lines are every line containing the term (engine applies hit caps).
    Line text uses :func:`extract_snippet` (same ~400-char centred window
    as phrase mode).
    """
    if kind:
        page_kind = str(page.meta.get("type", "")).strip().lower()
        if page_kind != kind:
            return None
    name_match = term_lower in page.title.lower() or term_lower in page.rel_path.lower()
    lines: list[tuple[int, str]] = []
    for i, line in enumerate(page.text.splitlines(), start=1):
        stripped = line.strip()
        if term_lower in stripped.lower():
            lines.append((i, extract_snippet(stripped, [term_lower])))
    if not (lines or name_match):
        return None
    return MatchedPage(
        rel_path=page.rel_path,
        title=page.title,
        name_match=name_match,
        lines=tuple(lines),
    )
