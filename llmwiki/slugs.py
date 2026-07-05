"""Shared slug + title derivation for added documents (issue #16).

Canonical implementation of the slug rules that kbbuilder's async
add-doc worker (kbbuilder#7) converges on: prefer real content headings,
strip site-name suffixes, transliterate Cyrillic instead of collapsing
to a junk fallback, and emit only site-safe ASCII
(subset of raw_docs_site._SAFE_SEG_RE).
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

# Russian → Latin. Enough for the observed failure case (kbbuilder#7:
# Russian document titles slugging to ''); other scripts fall through
# NFKD folding and, if nothing survives, the caller's next candidate.
_CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

_BOILERPLATE_HEADINGS = frozenset({"source: external", "document", "untitled", "home"})

# "X - Site", "X | Site", "X — Site" (spaces required so hyphenated words survive)
_SUFFIX_SEP = re.compile(r"\s+[-|—–]\s+")

_INDEXISH = frozenset({"index", "index.html", "index.htm", "index.php", "default.aspx"})


def slugify(text: str, max_len: int = 80) -> str:
    """Kebab-case ASCII slug. Returns '' when nothing survives —
    callers fall to their next title candidate, never a junk literal."""
    s = text.lower()
    s = "".join(_CYRILLIC.get(ch, ch) for ch in s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"^https?://", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:max_len].rstrip("-")


def strip_site_suffix(title: str) -> str:
    """Drop one trailing site-name segment ("X - Site" → "X"); collapse
    exact repeats ("OpenClaw - OpenClaw" → "OpenClaw")."""
    parts = _SUFFIX_SEP.split(title)
    if len(parts) < 2:
        return title.strip()
    head, tail = " - ".join(parts[:-1]).strip(), parts[-1].strip()
    if head.lower() == tail.lower():
        return head
    # Only strip when the tail looks like a short site name, not content.
    # Site names are typically <= 20 chars; if head is longer, use that as threshold.
    if tail and len(tail) <= max(len(head), 20):
        return head
    return title.strip()


def first_heading(markdown: str) -> str:
    """First markdown heading, skipping '#' lines inside code fences."""
    fence = None
    for line in markdown.split("\n"):
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        if m:
            marker = m.group(1)[0]
            fence = marker if fence is None else (None if fence == marker else fence)
            continue
        if fence is not None:
            continue
        h = re.match(r"^#{1,6}\s+(.*)$", line.strip())
        if h:
            return h.group(1).strip()
    return ""


def title_from_url(url: str) -> str:
    """Last meaningful URL path segment (dashes/underscores → spaces),
    else the hostname."""
    parsed = urlparse(url)
    segments = [s for s in parsed.path.split("/") if s and s.lower() not in _INDEXISH]
    for seg in reversed(segments):
        seg = re.sub(r"\.[a-z0-9]{1,5}$", "", seg, flags=re.IGNORECASE)  # drop extension
        cleaned = seg.replace("-", " ").replace("_", " ").strip()
        if cleaned and not cleaned.isdigit():
            return cleaned
    return parsed.hostname or url


def derive_title(
    *,
    explicit: str | None,
    markdown: str,
    html_title: str | None,
    url: str | None,
    path_name: str | None,
) -> str:
    """Spec preference chain: --title → first real MD heading → cleaned
    HTML <title> → URL path segments → filename stem → hostname."""
    if explicit and explicit.strip():
        return explicit.strip()
    heading = first_heading(markdown)
    if heading and heading.lower() not in _BOILERPLATE_HEADINGS and slugify(heading):
        return heading
    if html_title:
        cleaned = strip_site_suffix(html_title)
        if cleaned and slugify(cleaned):
            return cleaned
    if url:
        t = title_from_url(url)
        if t and slugify(t):
            return t
    if path_name:
        stem = re.sub(r"\.[A-Za-z0-9]{1,8}$", "", path_name)
        if stem:
            return stem
    # Absolute last resort — heading/html_title even if boilerplate, then raw input.
    return heading or (html_title or "").strip() or (url or path_name or "").strip()
