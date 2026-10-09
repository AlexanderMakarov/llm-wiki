"""Section-aware Markdown chunking shared by ``add`` and ``synth`` (#311).

Port of kbbuilder ``chunkMarkdownBySections``. Documents are stored whole;
this splitter only ever runs in memory, at synth time, against the active
backend's :meth:`~llmwiki.synth.base.BaseSynthesizer.usable_body_chars`
budget (and in the estimate, which must agree with the run). One chunker
for both consumers — do not grow a second one.

Splits happen at heading boundaries, then blank-line paragraph boundaries; a
hard character slice only ever hits a single paragraph longer than the whole
budget. Every chunk is at most ``max_chars`` long (trailing newline included),
and whitespace between chunks is the only thing a split may drop — no text is
discarded.
"""

from __future__ import annotations

import re as _re
from dataclasses import dataclass

from llmwiki.slugs import first_heading

__all__ = [
    "DEFAULT_CHUNK_MAX_CHARS",
    "MarkdownChunk",
    "chunk_markdown_by_sections",
]

# 7000 is the historical soft default (agent-delegate raw_body[:8000]
# headroom). Synth passes the backend's own budget instead.
DEFAULT_CHUNK_MAX_CHARS = 7000

_FENCE_RE = _re.compile(r"^\s*(`{3,}|~{3,})")


@dataclass
class MarkdownChunk:
    index: int          # 1-based position within the document
    total: int
    heading: str        # first heading inside the chunk ('' if none)
    body: str           # verbatim slice, newline-terminated


def _first_heading_line(body: str) -> str:
    """A chunk's heading, which goes through the same markup-stripping the
    document heading does."""
    return first_heading(body)


def _split_sections(text: str, levels: tuple[int, ...]) -> list[str]:
    lines = text.split("\n")
    sections: list[str] = []
    buf: list[str] = []
    fence = None
    for line in lines:
        m = _FENCE_RE.match(line)
        if m:
            marker = m.group(1)[0]
            fence = marker if fence is None else (None if fence == marker else fence)
        h = _re.match(r"^(#{1,6})\s", line)
        if fence is None and h and len(h.group(1)) in levels and buf:
            sections.append("\n".join(buf) + "\n")
            buf = []
        buf.append(line)
    if buf:
        sections.append("\n".join(buf) + "\n")
    return sections


def _split_oversized(section: str, max_chars: int) -> list[str]:
    """Split one over-budget section on paragraph boundaries.

    Each piece is emitted newline-terminated, so paragraphs are kept to
    ``max_chars - 1`` and the terminator never pushes a piece over budget.
    """
    room = max_chars - 1
    paras = _re.split(r"\n{2,}", section)
    out: list[str] = []
    cur = ""

    def flush() -> None:
        nonlocal cur
        if cur.strip():
            out.append(cur.rstrip("\n") + "\n")
        cur = ""

    for p in paras:
        if len(p) > room:
            flush()
            for i in range(0, len(p), room):
                piece = p[i:i + room].strip()
                if piece:
                    out.append(piece + "\n")
            continue
        if cur and len(cur) + len(p) + 2 > room:
            flush()
        cur += ("\n\n" if cur else "") + p
    flush()
    return out


def chunk_markdown_by_sections(
    markdown: str,
    max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    heading_levels: tuple[int, ...] = (1, 2),
) -> list[MarkdownChunk]:
    """Split a Markdown document into section-aligned chunks ≤ max_chars.

    Sections pack greedily; an oversized section splits on blank-line
    paragraph boundaries, hard-slicing only as a last resort. Heading
    detection is fence-aware. A document within budget returns whole."""
    max_chars = max(2, int(max_chars))
    text = markdown.replace("\r\n", "\n")
    sections = _split_sections(text, heading_levels)
    bodies: list[str] = []
    cur = ""

    def flush() -> None:
        nonlocal cur
        if cur.strip():
            bodies.append(cur.rstrip("\n") + "\n")
        cur = ""

    for sec in sections:
        if len(sec) > max_chars:
            flush()
            bodies.extend(_split_oversized(sec, max_chars))
            continue
        if cur and len(cur) + len(sec) > max_chars:
            flush()
        cur += sec
    flush()

    if not bodies:
        body = text.strip()
        if not body:
            return []
        return [MarkdownChunk(1, 1, _first_heading_line(body), body + "\n")]
    total = len(bodies)
    return [MarkdownChunk(i + 1, total, _first_heading_line(b), b) for i, b in enumerate(bodies)]
