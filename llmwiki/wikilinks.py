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

__all__ = ["WIKILINK_RE", "strip_anchor", "wikilink_targets"]

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
