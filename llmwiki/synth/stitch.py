"""Deterministic stitch of per-chunk source-page bodies into one page (#311).

A long document is synthesized in memory, one backend call per chunk. The
chunk outputs are assembled here by fixed rules — never by a further AI
"polish" pass:

* ``## Summary`` — the chunks' summaries, concatenated in document order.
* ``## Key Claims`` / ``## Key Quotes`` (and any other section) — ordered
  union; an item whose whitespace-normalised text was already seen is dropped.
* ``## Connections`` — union by wikilink target; the first bullet for a target
  wins, and nested ``fact:`` lines a later duplicate adds are kept under it.
* suggested tags and tag curation are handled by the caller, which strips the
  ``<!-- suggested-tags: … -->`` comment off each chunk before stitching.

Pure text in, text out: no filesystem, no backend, no import of the pipeline.
"""

from __future__ import annotations

import re

from llmwiki.wikilinks import WIKILINK_RE, strip_anchor

__all__ = ["stitch_chunk_bodies"]

_H2_RE = re.compile(r"^##[ \t]+(?P<title>.+?)[ \t]*$")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_BULLET_RE = re.compile(r"^(?:[-*+]|\d+[.)])[ \t]")


def _norm(text: str) -> str:
    """Whitespace-collapsed form used to decide two items are the same."""
    return " ".join(text.split())


def _parse_sections(body: str) -> tuple[str, list[tuple[str, str]]]:
    """Split ``body`` into ``(preamble, [(heading, content), …])`` on ``## `` lines.

    Fence-aware, so a ``## `` inside a code block is content. ``###`` and
    deeper headings stay inside their parent section.
    """
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    fence: str | None = None
    for line in body.splitlines():
        m = _FENCE_RE.match(line)
        if m:
            marker = m.group(1)[0]
            fence = marker if fence is None else (None if fence == marker else fence)
        h = _H2_RE.match(line) if fence is None else None
        if h:
            sections.append((h.group("title").strip(), []))
        elif sections:
            sections[-1][1].append(line)
        else:
            preamble.append(line)
    return "\n".join(preamble).strip(), [
        (title, "\n".join(lines).strip("\n")) for title, lines in sections
    ]


def _split_items(text: str) -> list[str]:
    """Split a section into items: bullets, blockquotes, or prose paragraphs.

    A bullet at column 0 starts an item and indented lines belong to it; a
    ``>`` line starts a new quote unless the line before it was also ``>``;
    otherwise a paragraph break starts a new item.
    """
    items: list[list[str]] = []
    cur: list[str] | None = None
    prev = ""
    blank = False
    for line in text.splitlines():
        if not line.strip():
            blank = True
            continue
        if _BULLET_RE.match(line):
            start = True
        elif line.startswith(">"):
            start = cur is None or blank or not prev.startswith(">")
        elif line[0] in " \t":
            start = cur is None
        else:
            start = cur is None or blank
        if start:
            cur = [line.rstrip()]
            items.append(cur)
        else:
            assert cur is not None
            cur.append(line.rstrip())
        prev = line
        blank = False
    return ["\n".join(lines) for lines in items]


def _join_items(items: list[str]) -> str:
    """Join items; bullets stay tight, quotes and prose get a blank line between."""
    out = ""
    prev_bullet = False
    for item in items:
        is_bullet = bool(_BULLET_RE.match(item))
        if out:
            out += "\n" if (prev_bullet and is_bullet) else "\n\n"
        out += item
        prev_bullet = is_bullet
    return out


def _union_items(contents: list[str]) -> str:
    seen: set[str] = set()
    kept: list[str] = []
    for content in contents:
        for item in _split_items(content):
            key = _norm(item)
            if key in seen:
                continue
            seen.add(key)
            kept.append(item)
    return _join_items(kept)


def _union_connections(contents: list[str]) -> str:
    """Union ``## Connections`` entries by wikilink target (first bullet wins)."""
    entries: list[list[str]] = []        # head line + nested lines
    by_target: dict[str, list[str]] = {}
    seen_plain: set[str] = set()
    for content in contents:
        for item in _split_items(content):
            head, *nested = item.split("\n")
            targets = [strip_anchor(t) for t in WIKILINK_RE.findall(head)]
            target = next((t for t in targets if t), "")
            if target:
                entry = by_target.get(target)
                if entry is None:
                    entry = [head, *nested]
                    by_target[target] = entry
                    entries.append(entry)
                else:
                    have = {_norm(line) for line in entry[1:]}
                    for line in nested:
                        if _norm(line) not in have:
                            entry.append(line)
                            have.add(_norm(line))
                continue
            key = _norm(item)
            if key in seen_plain:
                continue
            seen_plain.add(key)
            entries.append([head, *nested])
    return "\n".join("\n".join(entry) for entry in entries)


def stitch_chunk_bodies(bodies: list[str]) -> str:
    """Assemble per-chunk source-page bodies into one body.

    ``bodies`` are the chunk outputs in document order with their
    suggested-tags comments already removed. One body is returned as-is; two
    or more are stitched by the rules in the module docstring. Section order
    follows first appearance across the chunks.
    """
    if len(bodies) == 1:
        return bodies[0]
    preambles: list[str] = []
    order: list[str] = []                 # section keys, first-seen order
    titles: dict[str, str] = {}
    contents: dict[str, list[str]] = {}
    for body in bodies:
        preamble, sections = _parse_sections(body)
        if preamble and preamble not in preambles:
            preambles.append(preamble)
        for title, content in sections:
            key = _norm(title).casefold()
            if key not in contents:
                order.append(key)
                titles[key] = title
                contents[key] = []
            if content.strip():
                contents[key].append(content)
    parts: list[str] = list(preambles)
    for key in order:
        if key == "summary":
            text = "\n\n".join(c.strip("\n") for c in contents[key])
        elif key == "connections":
            text = _union_connections(contents[key])
        else:
            text = _union_items(contents[key])
        parts.append(f"## {titles[key]}\n\n{text}" if text else f"## {titles[key]}")
    return "\n\n".join(parts).rstrip("\n") + "\n"
