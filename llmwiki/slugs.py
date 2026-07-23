"""Shared slug + title derivation for added documents (issue #16).

Canonical slug rules for document ingestion: prefer real content headings, strip site-name suffixes,
transliterate Cyrillic instead of collapsing to a junk fallback, and emit only site-safe ASCII
(subset of raw_docs_site._SAFE_SEG_RE).
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

# Russian → Latin. Enough for the observed failure case where
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

# Segments that mark the end of the machine-specific prefix in a cwd-encoded
# directory name — whatever follows one of these is the project itself.
_WORKSPACE_MARKERS = ("draft", "production", "Desktop")


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


def project_slug_from_encoded_dir(name: str) -> str:
    """Decode a cwd-encoded directory name into a project slug.

    Agent tooling flattens a working directory into one path segment by
    replacing separators with hyphens — ``~/.claude/projects/-home-dev-code-my-app/``
    and the per-session scratchpad dirs both use this form. The separators
    are unrecoverable, so the tail is a heuristic: everything after a
    recognizable workspace marker, otherwise the last two segments (a
    two-word project name is far more common than a one-word one at the end
    of a ``.../code/<project>`` path).
    """
    parts = name.lstrip("-").split("-")
    for marker in _WORKSPACE_MARKERS:
        if marker in parts:
            idx = len(parts) - 1 - parts[::-1].index(marker)
            tail = parts[idx + 1:]
            if tail:
                return "-".join(tail)
    return "-".join(parts[-2:]) if len(parts) >= 2 else name


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


def _plain_heading_text(text: str) -> str:
    """Heading text with inline markdown markup resolved to plain prose.

    A heading becomes a title, a slug, and a raw/docs directory name, so any
    surviving markup leaks into all three. Two cases matter in practice:

    * ``[#](#0-toc-title)`` — the self-link CMSs render inside every heading.
      Its label is pure punctuation and carries no meaning, so it is dropped
      whole rather than reduced to its label.
    * ``[sole traders](/docs/ip)`` — a genuine in-heading link. Keep the
      label, drop the target.
    """
    def _link(m: re.Match[str]) -> str:
        label = m.group(1).strip()
        # Punctuation-only labels (#, ¶, §, ↩) are permalink glyphs, not words.
        return "" if not re.search(r"[^\W_]", label, re.UNICODE) else label

    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", _link, text)
    text = re.sub(r"(\*{1,3}|_{1,3})(?=\S)(.+?)(?<=\S)\1", r"\2", text)
    text = text.replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def first_heading(markdown: str, levels: tuple[int, ...] = (1, 2, 3, 4, 5, 6)) -> str:
    """First markdown heading, skipping '#' lines inside code fences.

    ``levels`` restricts which heading depths count, so a caller after the
    document's own title can ask for ``(1,)`` and not settle for a body
    subsection.
    """
    fence = None
    for line in markdown.split("\n"):
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        if m:
            marker = m.group(1)[0]
            fence = marker if fence is None else (None if fence == marker else fence)
            continue
        if fence is not None:
            continue
        h = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if h and len(h.group(1)) in levels:
            return _plain_heading_text(h.group(2))
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
    """Spec preference chain: --title → the document's own H1 → cleaned
    HTML <title> → URL path segments → filename stem → hostname.

    Only an H1 counts as "the document's own" heading. A CMS article's <h1>
    frequently sits outside the container an extractor treats as content, so
    the first heading in the markdown is a body subsection — using it gave
    whole families of articles the same generic title (every bank's guide
    named after its "signing in" section, colliding into "-2" suffixes)
    while the correct, specific title sat unused in html_title. A
    lower-level heading is still the last resort below, for documents that
    have nothing else to offer."""
    if explicit and explicit.strip():
        return explicit.strip()
    heading = first_heading(markdown, levels=(1,))
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
    # Absolute last resort — any heading (a subsection beats nothing) or an
    # html_title even if boilerplate, then raw input.
    return (heading or first_heading(markdown) or (html_title or "").strip()
            or (url or path_name or "").strip())
