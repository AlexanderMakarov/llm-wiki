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
import unicodedata
from collections import defaultdict
from collections.abc import Mapping

__all__ = [
    "ALIAS_NOTE_SEP",
    "WIKILINK_RE",
    "build_page_alias_map",
    "count_source_refs",
    "format_alias_bullet",
    "norm_page_key",
    "parse_page_aliases",
    "resolve_wikilink_target",
    "rewrite_wikilinks",
    "strip_anchor",
    "wikilink_targets",
]

#: Matches ``[[Target]]`` and ``[[Target|display text]]``. Group 1 is the
#: target as written, including any ``#section`` anchor.
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")

#: Strip everything except letters and digits after case folding — page
#: identity fold. Unicode-aware, so a non-Latin name keeps its own key instead
#: of folding to the empty string every other non-Latin name shares.
_PAGE_KEY_RE = re.compile(r"[\W_]")


def strip_anchor(target: str) -> str:
    """Return ``target`` without its ``#section`` anchor, whitespace trimmed.

    An anchor-only link such as ``[[#section]]`` names no page and reduces to
    the empty string.
    """
    return target.split("#")[0].strip()


def norm_page_key(name: str) -> str:
    """Case/punctuation-insensitive key for wiki **page identity**.

    ``LLM-Wiki``, ``llm wiki``, and ``llm-wiki`` all become ``llmwiki``;
    ``Мой-Проект`` becomes ``мойпроект``. Used
    by ``link_integrity``, candidate harvest, and ``migrate wikilink-titles``
    so case/punct variants of a wikilink target resolve to one page.

    The name is NFKC-normalised and case-folded first, so the two Unicode
    spellings of an accented name (``é`` as one code point or as ``e`` plus a
    combining accent) are one identity, and full case folding covers the
    letters ``.lower()`` leaves alone (``Straße`` and ``STRASSE``, Greek final
    ``ς`` and medial ``σ``).

    This folds the written **link target** (slug / stem), not topic vocabulary
    labels. Topic HTML paths use :func:`llmwiki.topics.topic_slug` instead
    (hyphenated, keeps separators as ``-``).
    """
    return _PAGE_KEY_RE.sub("", unicodedata.normalize("NFKC", name).casefold())


def wikilink_targets(text: str) -> set[str]:
    """Return the distinct pages ``text`` links to.

    Anchors are stripped and whitespace trimmed. Links that name no page
    (``[[#section]]``) are excluded from the result.
    """
    targets = {strip_anchor(raw) for raw in WIKILINK_RE.findall(text)}
    targets.discard("")
    return targets


_ALIASES_HEADING_RE = re.compile(r"^##\s+Aliases\s*$", re.MULTILINE)

#: What separates an alias from the note explaining it in an ``## Aliases``
#: bullet. The note never contains it, so the alias is everything before the
#: **last** one — a name that contains an em dash round-trips.
ALIAS_NOTE_SEP = " — "


def format_alias_bullet(alias: str, note: str) -> str:
    """Render the ``## Aliases`` bullet :func:`parse_page_aliases` reads back.

    ``note`` says how the name got here (``merged 2026-01-01 (2 source
    pages)``). It must not contain :data:`ALIAS_NOTE_SEP`, or the alias would
    no longer be recoverable; a note that does raises ``ValueError``.

    The alias is written as plain text, not as a ``[[wikilink]]``: the page
    listing it is the page the name resolves to, so a link here would be a
    self-edge in the graph and an inbound reference to the page from itself.
    """
    if ALIAS_NOTE_SEP in note:
        raise ValueError(f"alias note may not contain {ALIAS_NOTE_SEP!r}: {note!r}")
    return f"- {alias}{ALIAS_NOTE_SEP}{note}"


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
    bullets (``- [[Foo]]``). The note is separated by the **last** em dash on
    the line, so a name that contains one (``- A — B — merged …``) comes back
    whole and :func:`format_alias_bullet` round-trips.
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
        alias = rest.rsplit("—", 1)[0].strip()
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
    page's slug; the alias lookup folds case and punctuation with
    :func:`norm_page_key`, so ``[[foo bar]]`` finds an alias recorded as
    ``Foo-Bar``.
    """
    name = strip_anchor(target)
    if not name:
        return None
    if name in slugs:
        return name
    if alias_map:
        canonical = alias_map.get(name)
        if canonical is None:
            key = norm_page_key(name)
            canonical = next(
                (slug for alias, slug in alias_map.items() if norm_page_key(alias) == key),
                None,
            )
        if canonical and canonical in slugs:
            return canonical
    return None


def rewrite_wikilinks(
    text: str, targets: Mapping[str, str | None], *, self_stem: str | None = None,
) -> tuple[str, dict[str, int]]:
    """Unlink or retarget every link whose page is named in ``targets``.

    ``targets`` maps a :func:`norm_page_key` to the page slug its links should
    point at instead, or to ``None`` to turn them into plain text. Matching is
    case/punctuation-insensitive, so ``[[Foo]]``, ``[[foo]]`` and
    ``[[Foo#Usage|the foo]]`` all match the key ``foo``.

    The reader-visible text survives either way: the display label when the
    link has one, otherwise the target as written (without its anchor). A
    retargeted link keeps that text as its label — ``[[Foo|the foo]]`` becomes
    ``[[Bar|the foo]]`` and ``[[Foo]]`` becomes ``[[Bar|Foo]]``.

    ``self_stem`` is the stem of the page ``text`` came from. A link that
    would be retargeted at that same page becomes plain text instead: the
    redirect target's own ``[[Foo]]`` bullet reads as ``Foo`` rather than
    linking the page to itself. Identity is compared with
    :func:`norm_page_key`, so a case or punctuation variant still counts.

    Known limitation: the whole document is rewritten, so a ``[[Name]]``
    written inside a fenced code block or a quoted transcript preview is
    rewritten like any other link.

    Returns the new text and the number of links rewritten per key.
    """
    counts: dict[str, int] = defaultdict(int)
    self_key = norm_page_key(self_stem) if self_stem else ""

    def _replace(match: re.Match[str]) -> str:
        full = match.group(0)
        name = strip_anchor(match.group(1))
        key = norm_page_key(name)
        if not key or key not in targets:
            return full
        _, sep, label = full[2:-2].partition("|")
        display = label.strip() if sep and label.strip() else name
        counts[key] += 1
        replacement = targets[key]
        if replacement is None or (
            self_key and norm_page_key(replacement) == self_key
        ):
            return display
        if display == replacement:
            return f"[[{replacement}]]"
        return f"[[{replacement}|{display}]]"

    return WIKILINK_RE.sub(_replace, text), dict(counts)


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
