"""Canonical ``[[wikilink]]`` parsing.

Every part of llmwiki that reads links out of markdown — the graph, lint,
backlinks, references, harvest, synth, the topic vocabulary — shares the one
pattern and the one anchor-stripping step defined here, so they all agree on
what counts as a link and on which page a link points at.

Leaf module: it imports nothing from :mod:`llmwiki`, so any module can use it
without risking an import cycle.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping

__all__ = [
    "WIKILINK_RE",
    "build_page_alias_map",
    "count_source_refs",
    "parse_page_aliases",
    "resolve_wikilink_target",
    "strip_anchor",
    "wikilink_targets",
]

#: Matches ``[[Target]]`` and ``[[Target|display text]]``. Group 1 is the
#: target as written, including any ``#section`` anchor.
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def strip_anchor(target: str) -> str:
    """Return ``target`` without its ``#section`` anchor, whitespace trimmed.

    An anchor-only link such as ``[[#section]]`` names no page and reduces to
    the empty string.
    """
    return target.split("#")[0].strip()


def wikilink_targets(text: str) -> set[str]:
    """Return the distinct pages ``text`` links to.

    Anchors are stripped and whitespace trimmed. Links that name no page
    (``[[#section]]``) are excluded from the result.
    """
    targets = {strip_anchor(raw) for raw in WIKILINK_RE.findall(text)}
    targets.discard("")
    return targets


_ALIASES_HEADING_RE = re.compile(r"^##\s+Aliases\s*$", re.MULTILINE)


def _aliases_section_lines(body: str) -> list[str]:
    """Return body lines under ``## Aliases``, or ``[]`` when absent."""
    match = _ALIASES_HEADING_RE.search(body)
    if not match:
        return []
    rest = body[match.end() :]
    lines: list[str] = []
    for line in rest.splitlines():
        if line.startswith("## "):
            break
        lines.append(line)
    return lines


def parse_page_aliases(body: str) -> list[str]:
    """Return alias names declared under ``## Aliases``.

    Accepts harvest-merge bullets (``- Foo — merged …``) and wikilink
    bullets (``- [[Foo]]``).
    """
    aliases: list[str] = []
    seen: set[str] = set()
    for line in _aliases_section_lines(body):
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        wikilinks = WIKILINK_RE.findall(stripped)
        if wikilinks:
            for raw in wikilinks:
                alias = strip_anchor(raw)
                if alias and alias.casefold() not in seen:
                    seen.add(alias.casefold())
                    aliases.append(alias)
            continue
        rest = stripped.lstrip("-").strip()
        if not rest:
            continue
        alias = rest.split("—", 1)[0].strip()
        if alias and alias.casefold() not in seen:
            seen.add(alias.casefold())
            aliases.append(alias)
    return aliases


def build_page_alias_map(page_bodies: dict[str, str]) -> dict[str, str]:
    """Map merged-away page names to the survivor slug that lists them.

    First declaration wins when the same alias appears on more than one page.
    """
    alias_map: dict[str, str] = {}
    for slug, body in page_bodies.items():
        for alias in parse_page_aliases(body):
            if alias == slug:
                continue
            if alias not in alias_map:
                alias_map[alias] = slug
    return alias_map


def resolve_wikilink_target(
    target: str,
    slugs: set[str],
    alias_map: dict[str, str] | None = None,
) -> str | None:
    """Return the canonical page slug for ``target``, or ``None`` when missing.

    ``target`` may still carry a ``#section`` anchor; it is stripped before
    lookup. A name listed under another page's ``## Aliases`` resolves to that
    page's slug.
    """
    name = strip_anchor(target)
    if not name:
        return None
    if name in slugs:
        return name
    if alias_map:
        canonical = alias_map.get(name)
        if canonical and canonical in slugs:
            return canonical
    return None


def count_source_refs(texts_by_rel: Mapping[str, str]) -> dict[str, set[str]]:
    """Return ``target -> set of pages naming it`` for a corpus of page text.

    ``texts_by_rel`` maps a page's path (relative to ``wiki/``) to its text.
    A target is counted **once per page**: repeated mentions inside one
    document are one signal, not several.

    Shared by the candidate harvest and ``link_integrity`` (#150) so the
    component that decides a target is worth a page and the component that
    reports the missing page count references the same way.
    """
    by_target: dict[str, set[str]] = defaultdict(set)
    for rel, text in texts_by_rel.items():
        for name in wikilink_targets(text):
            by_target[name].add(rel)
    return dict(by_target)
