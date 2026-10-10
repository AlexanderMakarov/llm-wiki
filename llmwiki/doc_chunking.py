"""Section-aware Markdown chunking shared by ``add`` and ``synth`` (#311).

Port of kbbuilder ``chunkMarkdownBySections``. Documents are stored whole;
this splitter only ever runs in memory, at synth time, against the active
backend's :meth:`~llmwiki.synth.base.BaseSynthesizer.usable_body_chars`
budget (and in the estimate, which must agree with the run). One chunker
for both consumers — do not grow a second one. The caller always supplies the
budget; there is no module default to drift from the backend's.

Splits happen at heading boundaries, then blank-line paragraph boundaries
(a fenced code block is one paragraph, blank lines inside it included); a hard
slice only ever hits a single paragraph longer than the whole budget, and it
prefers line boundaries, cutting inside a line only when one line alone is over
budget. When a slice lands inside an open code fence, every piece is closed and
re-opened with the original fence line so each chunk is well-formed Markdown. A
heading is never emitted alone: it travels with the content that follows it
(or, at the end of a document, with the content before it) — short of a run of
headings that is itself larger than the whole budget. Every chunk is at
most ``max_chars`` long (trailing newline included); whitespace between chunks
and the fence lines added by re-fencing are the only differences from the
source — no text is discarded.
"""

from __future__ import annotations

import re as _re
from dataclasses import dataclass

from llmwiki.slugs import first_heading

__all__ = [
    "MAX_DOC_MARKDOWN_BYTES",
    "MarkdownChunk",
    "chunk_markdown_by_sections",
    "doc_size_error",
]

#: Hard ceiling on one stored document's Markdown, in UTF-8 bytes (512 KiB).
#: ``llmwiki add`` rejects a larger conversion without writing it, and ``synth``
#: refuses a legacy raw doc already over it (#311).
MAX_DOC_MARKDOWN_BYTES = 512 * 1024

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


_HEADING_RE = _re.compile(r"^#{1,6}(?:\s|$)")


def _is_heading_only(text: str) -> bool:
    """True when every non-blank line is an ATX heading (and there is at least one)."""
    lines = [ln for ln in text.split("\n") if ln.strip()]
    return bool(lines) and all(_HEADING_RE.match(ln) for ln in lines)


def _fence_step(line: str, fence_open: str | None) -> str | None:
    """Fence state after ``line``: the opening line while a fence is open, else ``None``.

    Same open/close rule as :func:`_split_sections` (the marker character decides).
    """
    m = _FENCE_RE.match(line)
    if not m:
        return fence_open
    if fence_open is None:
        return line
    opener = _FENCE_RE.match(fence_open)
    return None if opener and opener.group(1)[0] == m.group(1)[0] else fence_open


def _blocks(section: str) -> list[str]:
    """Paragraph blocks of ``section``; a fenced block stays whole, blank lines and all."""
    blocks: list[str] = []
    buf: list[str] = []
    fence_open: str | None = None
    for line in section.split("\n"):
        if not line.strip() and fence_open is None:
            if buf:
                blocks.append("\n".join(buf))
                buf = []
            continue
        buf.append(line)
        fence_open = _fence_step(line, fence_open)
    if buf:
        blocks.append("\n".join(buf))
    return blocks


def _attach_headings(blocks: list[str]) -> list[str]:
    """Units that never leave a heading alone: headings join the block after them.

    A heading run at the very end has nothing after it, so it joins the last
    unit instead; a document that is only headings stays one unit.
    """
    units: list[str] = []
    pending: list[str] = []
    for b in blocks:
        if _is_heading_only(b):
            pending.append(b)
            continue
        units.append("\n\n".join([*pending, b]))
        pending = []
    if pending:
        tail = "\n\n".join(pending)
        if units:
            units[-1] += "\n\n" + tail
        else:
            units.append(tail)
    return units


def _lines_heading_only(lines: list[str]) -> bool:
    return _is_heading_only("\n".join(lines))


def _hard_split(text: str, room: int) -> list[str]:
    """Split one over-``room`` unit on line boundaries into pieces of at most ``room`` characters.

    Cuts inside a single line only when that line alone exceeds the budget.
    When a piece ends inside an open code fence it is closed, and the next
    piece re-opens with the original opening line, so every piece is
    well-formed; their length is reserved up front. A piece never ends on a
    bare heading: the heading takes the start of the next line, and a heading
    run at the end of the unit travels with the line before it.
    """
    lines = text.split("\n")
    opener_len = closer_len = 0
    state: str | None = None
    for ln in lines:
        state = _fence_step(ln, state)
        m = _FENCE_RE.match(ln)
        if m and state is not None:
            opener_len = max(opener_len, len(ln))
            closer_len = max(closer_len, len(m.group(1)))
    refence = opener_len > 0 and 2 * (opener_len + closer_len + 2) <= room
    budget = room - (opener_len + closer_len + 2 if refence else 0)

    # Index where the unit's trailing heading run begins: those lines must share
    # a piece with the content line just before them.
    tail_group_start = len(lines)
    j = len(lines)
    while j > 0 and (not lines[j - 1].strip() or _HEADING_RE.match(lines[j - 1])):
        j -= 1
    if 0 < j < len(lines) and len("\n".join(lines[j:]).rstrip("\n")) + 2 <= budget:
        tail_group_start = j - 1

    pieces: list[str] = []
    cur: list[str] = []
    cur_len = 0
    fence_open: str | None = None      # fence state after the lines in ``cur``
    start_fence: str | None = None     # fence state when ``cur`` began

    def emit(segment_lines: list[str], begins_in: str | None, ends_in: str | None) -> None:
        content = "\n".join(segment_lines).strip("\n")
        if not content.strip():
            return
        if refence and begins_in is not None:
            content = begins_in + "\n" + content
        if refence and ends_in is not None:
            content += "\n" + _FENCE_RE.match(ends_in).group(1)  # type: ignore[union-attr]
        pieces.append(content + "\n")

    def flush() -> None:
        nonlocal cur, cur_len, start_fence
        emit(cur, start_fence, fence_open)
        cur, cur_len, start_fence = [], 0, fence_open

    def pour(text: str) -> str:
        """Close the open piece, first filling a bare heading with the head of ``text``.

        Returns the part of ``text`` not yet placed.
        """
        nonlocal cur, cur_len
        if cur and start_fence is None and fence_open is None and _lines_heading_only(cur) and text.strip():
            avail = budget - cur_len - 1
            if avail >= 1 and not _FENCE_RE.match(text):
                cur.append(text[:avail])
                text = text[avail:]
        flush()
        return text

    def emit_slices(text: str) -> None:
        for k in range(0, len(text), budget):
            emit([text[k : k + budget]], fence_open, fence_open)

    i = 0
    while i < len(lines):
        line = lines[i]
        cost = len(line) + (1 if cur else 0)
        if i == tail_group_start:
            group = "\n".join(lines[i:]).rstrip("\n")
            bare_heading = bool(cur) and start_fence is None and fence_open is None and _lines_heading_only(cur)
            overflows = len(group) > budget or (cur and cur_len + 1 + len(group) > budget)
            # ``keep`` characters of the line stay with the trailing headings; the
            # rest is placed first (a bare heading before it takes the head).
            keep = min(budget - (len(group) - len(line)), len(line) - 1)
            if overflows and (len(group) > budget or bare_heading) and keep >= 1:
                front = pour(line[:-keep])
                emit_slices(front)
                cur, cur_len = [line[-keep:]], keep
                fence_open = _fence_step(line, fence_open)
                i += 1
                continue
            if overflows:
                flush()
                cost = len(line)
        if (cur and cur_len + cost > budget) or len(line) > budget:
            if cur and not line.strip() and start_fence is None and fence_open is None and _lines_heading_only(cur):
                i += 1  # whitespace between a heading and the next line is droppable
                continue
            rest = pour(line)
            if rest != line:
                lines[i] = rest  # a heading took the head of this line; place the remainder
                if not rest.strip():
                    i += 1
                continue
            cost = len(line)
            if len(line) > budget:
                emit_slices(line[: -(len(line) % budget or budget)])
                tail = line[-(len(line) % budget or budget) :]
                cur, cur_len = [tail], len(tail)
                fence_open = _fence_step(line, fence_open)
                i += 1
                continue
        cur.append(line)
        cur_len += cost
        fence_open = _fence_step(line, fence_open)
        i += 1
    flush()
    return pieces


def _split_oversized(section: str, max_chars: int) -> list[str]:
    """Split one over-budget section on paragraph boundaries, then line boundaries.

    Each piece is emitted newline-terminated, so pieces are kept to
    ``max_chars - 1`` and the terminator never pushes a piece over budget.
    """
    room = max_chars - 1
    out: list[str] = []
    cur = ""

    def flush() -> None:
        nonlocal cur
        if cur.strip():
            out.append(cur.rstrip("\n") + "\n")
        cur = ""

    for unit in _attach_headings(_blocks(section)):
        if len(unit) > room:
            flush()
            out.extend(_hard_split(unit, room))
            continue
        if cur and len(cur) + len(unit) + 2 > room:
            flush()
        cur += ("\n\n" if cur else "") + unit
    flush()
    return out


def _attach_section_headings(sections: list[str]) -> list[str]:
    """Merge heading-only sections into the section after them (or before, at the end)."""
    merged: list[str] = []
    pending = ""
    for sec in sections:
        if _is_heading_only(sec):
            pending += sec
            continue
        merged.append(pending + sec)
        pending = ""
    if pending:
        if merged:
            merged[-1] += pending
        else:
            merged.append(pending)
    return merged


def doc_size_error(markdown: str, label: str) -> str | None:
    """Why ``markdown`` is too large to store as one document, or ``None`` if it fits."""
    size = len(markdown.encode("utf-8"))
    if size <= MAX_DOC_MARKDOWN_BYTES:
        return None
    return (
        f"{label}: converted Markdown is {size / 1024:.0f} KiB, over the "
        f"{MAX_DOC_MARKDOWN_BYTES // 1024} KiB per-document limit — split the source into smaller documents"
    )


def chunk_markdown_by_sections(
    markdown: str,
    max_chars: int,
    heading_levels: tuple[int, ...] = (1, 2),
) -> list[MarkdownChunk]:
    """Split a Markdown document into section-aligned chunks ≤ max_chars.

    Sections pack greedily; an oversized section splits on blank-line
    paragraph boundaries, then line boundaries, hard-slicing inside a line only
    as a last resort (re-fencing code blocks it cuts through). A heading is
    never emitted as a chunk of its own. Heading detection is fence-aware. A
    document within budget returns whole."""
    max_chars = max(2, int(max_chars))
    text = markdown.replace("\r\n", "\n")
    sections = _attach_section_headings(_split_sections(text, heading_levels))
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
