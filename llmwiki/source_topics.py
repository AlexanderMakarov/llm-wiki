"""Parse topic bullets on synthesized source pages (#147).

Source ``## Connections`` bullets carry kind, description, and nested facts::

    - [[ExactName]] (entity) — one-line description
      - fact: A concrete claim this source supports.

Harvest and promote read these fields without another model call. This module
is a leaf: it imports only :mod:`llmwiki.wikilinks` (also a leaf).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from llmwiki.wikilinks import WIKILINK_RE, strip_anchor, wikilink_targets

__all__ = [
    "TopicRecord",
    "parse_source_topics",
    "source_page_needs_topics_rewrite",
]

#: Kinds harvest and promote treat as usable (case-insensitive on input).
_USABLE_KINDS = frozenset({"entity", "concept"})

#: List item whose body is a ``fact:`` line (any indent).
_FACT_LINE_RE = re.compile(r"^\s*-\s+fact:\s*(.*)$")

#: List item that may open a topic bullet (wikilink must lead the body).
_LIST_ITEM_RE = re.compile(r"^\s*-\s+(.*)$")


@dataclass
class TopicRecord:
    """One named topic extracted from a source-page Connections bullet.

    ``name`` is the wikilink target (before ``|`` / ``#``). ``kind`` is
    ``entity`` or ``concept`` when the parent bullet declares a usable kind;
    any other or missing kind becomes ``None``. ``description`` is the text
    after an em-dash (``—``) or hyphen (`` - ``) separator on that bullet.
    ``facts`` are nested ``- fact:`` lines under the parent.
    """

    name: str
    kind: str | None
    description: str
    facts: list[str] = field(default_factory=list)


def _normalize_kind(raw: str | None) -> str | None:
    """Return ``entity`` / ``concept`` lowercased, else ``None``."""
    if raw is None:
        return None
    kind = raw.strip().lower()
    if kind in _USABLE_KINDS:
        return kind
    return None


def _split_kind_and_description(remainder: str) -> tuple[str | None, str]:
    """Parse optional ``(kind)`` and description after the wikilink.

    Description uses an em-dash (``—``) when present; a leading hyphen after
    the kind (the `` - `` fallback once whitespace is stripped) is also
    accepted. Text without a dash separator is not treated as a description.
    """
    rem = remainder.strip()
    kind_raw: str | None = None
    if rem.startswith("("):
        close = rem.find(")")
        if close != -1:
            kind_raw = rem[1:close]
            rem = rem[close + 1 :].strip()
    description = ""
    if rem.startswith("—"):
        description = rem[1:].strip()
    elif rem.startswith("-"):
        description = rem[1:].strip()
    return kind_raw, description


def parse_source_topics(body: str) -> list[TopicRecord]:
    """Extract :class:`TopicRecord` values from source-page markdown ``body``.

    Recognises parent bullets of the form
    ``- [[Name]] (entity|concept) — description`` (``[[Name|alias]]`` allowed;
    record ``name`` is the link target). Nested lines matching ``- fact:`` /
    ``  - fact:`` append to the current topic's ``facts`` (prefix stripped).
    Invalid or missing kinds yield ``kind=None``. Lines that are not topic or
    fact bullets are ignored. Order follows first appearance in ``body``.
    """
    records: list[TopicRecord] = []
    current: TopicRecord | None = None

    for line in body.splitlines():
        fact_match = _FACT_LINE_RE.match(line)
        if fact_match is not None:
            if current is not None:
                text = fact_match.group(1).strip()
                if text:
                    current.facts.append(text)
            continue

        list_match = _LIST_ITEM_RE.match(line)
        if list_match is None:
            continue
        content = list_match.group(1)
        link_match = WIKILINK_RE.match(content)
        if link_match is None:
            continue
        name = strip_anchor(link_match.group(1))
        if not name:
            continue
        kind_raw, description = _split_kind_and_description(
            content[link_match.end() :]
        )
        current = TopicRecord(
            name=name,
            kind=_normalize_kind(kind_raw),
            description=description,
        )
        records.append(current)

    return records


def source_page_needs_topics_rewrite(body: str) -> bool:
    """Return whether a source page should be re-synthesized for topic shape.

    ``True`` when ``body`` has at least one harvestable ``[[wikilink]]``
    (via :func:`llmwiki.wikilinks.wikilink_targets`) and
    :func:`parse_source_topics` yields no record with a usable kind
    (``entity`` or ``concept``). Empty ``body`` is ``False``. A page with any
    usable kind is ``False`` even if other links lack kinds.
    """
    if not body:
        return False
    if not wikilink_targets(body):
        return False
    return not any(record.kind is not None for record in parse_source_topics(body))
