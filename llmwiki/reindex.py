"""Reconcile ``wiki/index.md`` with the pages actually on disk (#71).

The catalog drifts in both directions during ordinary use. ``sync`` seeds a
``wiki/projects/<slug>.md`` stub for every project it converts, and nothing
told the index about it; a page deleted by hand leaves a dead index link
behind. Both show up as ``index_sync`` lint errors that no command could fix.

This module is that command. It is a pure filesystem reconciliation — no LLM,
no token spend — and it is deliberately conservative about text it did not
write:

* **Existing entries are preserved verbatim.** Descriptions after the link are
  human- or agent-authored prose, so a page that already has a bullet keeps
  exactly the bullet it had. Only frontmatter of *newly listed* pages is read,
  which is what keeps a run cheap enough to fire after every ``sync``.
* **Entries whose page is gone are dropped**, and pages with no entry are
  appended to their section.
* **An entry filed under the wrong section moves** to the section that owns its
  folder rather than being dropped and re-added.
* **Unmanaged sections and free text are left alone.** Anything that is not a
  catalog section — the preamble, ``## Overview``, hand-written prose — passes
  through untouched.

Section headings carry a ``(count)`` per the ``#387 U6`` convention. Canonical
folders come first in the order ``CLAUDE.md`` documents them; any other folder
with pages (``comparisons/``, ``questions/``, ``archive/``, …) gets a section
named after it, so a page type added later is still listed rather than
becoming permanent lint noise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from llmwiki._frontmatter import parse_frontmatter
from llmwiki._system_pages import is_system_file

# Catalog folders in the order CLAUDE.md's index format lists them. Folders
# outside this tuple are appended alphabetically after it.
CANONICAL_FOLDERS: tuple[str, ...] = (
    "sources",
    "entities",
    "projects",
    "concepts",
    "syntheses",
)

# Always managed even when empty so draining the last stub can prune a leftover
# ``## Candidates`` section (#101). Not in CANONICAL_FOLDERS — an empty
# Candidates section is dropped entirely rather than kept as ``(0)``.
ALWAYS_MANAGED_FOLDERS: frozenset[str] = frozenset({"candidates"})

# Section that collects loose ``wiki/*.md`` pages (a saved ``lint-report.md``,
# say) which are neither system pages nor linked from anywhere else.
ROOT_SECTION = "Pages"

_H2_RE = re.compile(r"^##\s+(?P<title>.+?)\s*(?:\((?P<count>\d+)\))?\s*$")
_BULLET_RE = re.compile(r"^\s*[-*]\s+\[(?P<title>.+)\]\((?P<href>[^)]+)\)")
_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# Placeholder bodies previous writers left under an empty section. They are
# noise once the section lists real pages, so they never survive a reindex.
_PLACEHOLDERS = frozenset({
    "*(none yet)*",
    "*(none)*",
    "*(placeholder)*",
    "_(none yet)_",
    "_(none)_",
})


def seed_index_text() -> str:
    """The empty catalog ``init`` writes to a fresh vault.

    Lives here so ``init`` and a reindex of a vault with no ``index.md`` at all
    agree on the header — including the ``#387 U6`` note explaining the counts.
    """
    return (
        "# Wiki Index\n\n"
        "<!-- #387 U6: each section heading carries a (count) so the index\n"
        "stays scannable as the wiki grows past ~50 pages. Update the count\n"
        "in the heading when adding/removing pages. The index is otherwise\n"
        "kept flat (no nested folders) so a single grep/scan can find any\n"
        "page without descending into a tree. -->\n\n"
        "## Overview (1)\n- [Overview](overview.md)\n\n"
        "## Sources (0)\n\n"
        "## Entities (0)\n\n"
        "## Projects (0)\n\n"
        "## Concepts (0)\n\n"
        "## Syntheses (0)\n"
    )


@dataclass
class SectionPlan:
    """One catalog section of the rebuilt index."""

    heading: str
    folder: str
    bullets: list[str] = field(default_factory=list)
    preamble: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.bullets)

    def render(self) -> str:
        lines = [f"## {self.heading} ({self.count})", *self.preamble, *self.bullets]
        return "\n".join(lines)


@dataclass
class ReindexPlan:
    """What a reindex would write, and what it would add and drop."""

    index_path: Path
    original: str
    text: str
    sections: list[SectionPlan]

    @property
    def changed(self) -> bool:
        return self.text != self.original

    @property
    def added(self) -> list[str]:
        return [rel for s in self.sections for rel in s.added]

    @property
    def removed(self) -> list[str]:
        return [href for s in self.sections for href in s.removed]


def plan_reindex(wiki_dir: Path) -> ReindexPlan | None:
    """Compute the reconciled ``index.md`` without writing anything.

    Returns ``None`` when there is nothing to reconcile: no ``index.md`` and no
    listable page, i.e. an empty or non-existent wiki. An empty wiki does not
    get an index seeded as a side effect of some other command.
    """
    index_path = wiki_dir / "index.md"
    pages = _discover_pages(wiki_dir)
    try:
        original = index_path.read_text(encoding="utf-8") if index_path.is_file() else ""
    except OSError:
        original = ""
    if not original and not pages:
        return None

    preamble, blocks = _split_blocks(original or seed_index_text())
    managed = _managed_headings(pages)
    on_disk = {rel for rels in pages.values() for rel in rels}

    # Entries harvested from every managed section, keyed by the wiki-relative
    # path they point at. One global map, so an entry filed under the wrong
    # heading moves to the right section instead of being dropped and re-added
    # without its description.
    entries: dict[str, str] = {}
    section_preambles: dict[str, list[str]] = {}
    # Links that exist on disk but no section owns (a system page such as
    # overview.md listed inside a catalog section). Kept where they were.
    strays: dict[str, list[str]] = {}
    dead: dict[str, list[str]] = {}
    linked_elsewhere: set[str] = set()

    for link in _LINK_RE.findall(preamble):
        rel = _resolve_href(link)
        if rel:
            linked_elsewhere.add(rel)

    for heading_line, body in blocks:
        key = _section_key(heading_line, managed)
        if key is None:
            for link in _LINK_RE.findall(body):
                rel = _resolve_href(link)
                if rel:
                    linked_elsewhere.add(rel)
            continue
        for line in body.splitlines():
            match = _BULLET_RE.match(line)
            if not match:
                stripped = line.strip()
                if stripped and stripped not in _PLACEHOLDERS:
                    section_preambles.setdefault(key, []).append(line.rstrip())
                continue
            rel = _resolve_href(match.group("href"))
            if not rel:
                continue
            if rel in on_disk:
                entries.setdefault(rel, line.rstrip())
            elif (wiki_dir / rel).is_file():
                strays.setdefault(key, []).append(line.rstrip())
            else:
                dead.setdefault(key, []).append(match.group("href"))

    sections: dict[str, SectionPlan] = {}
    for key in _section_order(managed):
        plan = SectionPlan(
            heading=managed[key],
            folder=key,
            preamble=section_preambles.get(key, []),
            removed=dead.get(key, []),
        )
        for rel in pages.get(key, []):
            if rel in linked_elsewhere and key == "":
                # A loose root page already listed in a hand-written section
                # is not an orphan — don't list it twice.
                continue
            line = entries.get(rel)
            if line is None:
                line = _new_bullet(wiki_dir, rel)
                plan.added.append(rel)
            plan.bullets.append(line)
        plan.bullets.extend(strays.get(key, []))
        sections[key] = plan

    return ReindexPlan(
        index_path=index_path,
        original=original,
        text=_render(preamble, blocks, sections, managed),
        sections=list(sections.values()),
    )


def apply_reindex(plan: ReindexPlan) -> bool:
    """Write ``plan`` to disk. Returns True when the file changed."""
    if not plan.changed:
        return False
    plan.index_path.parent.mkdir(parents=True, exist_ok=True)
    plan.index_path.write_text(plan.text, encoding="utf-8")
    return True


def reindex_wiki(wiki_dir: Path, *, dry_run: bool = False) -> ReindexPlan | None:
    """Plan a reindex of ``wiki_dir`` and, unless ``dry_run``, write it."""
    plan = plan_reindex(wiki_dir)
    if plan is not None and not dry_run:
        apply_reindex(plan)
    return plan


def format_reindex_report(
    plan: ReindexPlan, *, dry_run: bool = False, limit: int = 20
) -> str:
    """Human-readable summary of what a reindex did (or would do).

    Per-page lines are capped at ``limit`` each — the first run on a drifted
    vault can list thousands of sources, and the section counts above already
    carry the totals.
    """
    lines = [f"  index: {plan.index_path}"]
    for section in plan.sections:
        delta = ""
        if section.added:
            delta += f"  +{len(section.added)} added"
        if section.removed:
            delta += f"  -{len(section.removed)} dead"
        lines.append(f"    {section.heading:<14} {section.count:>5} pages{delta}")
    for rel in plan.added[:limit]:
        lines.append(f"    + {rel}")
    if len(plan.added) > limit:
        lines.append(f"    + ... and {len(plan.added) - limit} more listed")
    for href in plan.removed[:limit]:
        lines.append(f"    - {href} (dead link)")
    if len(plan.removed) > limit:
        lines.append(f"    - ... and {len(plan.removed) - limit} more dead links")
    if not plan.changed:
        lines.append("  index.md already matches the pages on disk — nothing to do.")
    elif dry_run:
        lines.append("  --dry-run: nothing written.")
    else:
        lines.append(f"  wrote {plan.index_path.name}")
    return "\n".join(lines)


# ─── Discovery ─────────────────────────────────────────────────────────


def _is_listable(path: Path) -> bool:
    """True for a page the catalog should list.

    ``_``-prefixed files are folder metadata (``_context.md``, #60) and
    ``README.md`` is repo furniture; neither belongs in the catalog, and lint
    exempts both.
    """
    return (
        path.is_file()
        and path.suffix == ".md"
        and not path.name.startswith((".", "_"))
        and path.name != "README.md"
    )


def _discover_pages(wiki_dir: Path) -> dict[str, list[str]]:
    """Map section key → wiki-relative page paths, ordered by path.

    The key is the folder name; ``""`` collects loose pages at the wiki root.
    Folders with no listable page are absent, so an empty ``hot/`` never grows
    a section.
    """
    pages: dict[str, list[str]] = {}
    if not wiki_dir.is_dir():
        return pages
    for child in sorted(wiki_dir.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        rels = [
            p.relative_to(wiki_dir).as_posix()
            for p in sorted(child.rglob("*.md"))
            if _is_listable(p)
        ]
        if rels:
            pages[child.name] = rels
    root = [
        p.name
        for p in sorted(wiki_dir.glob("*.md"))
        if _is_listable(p) and not is_system_file(p.name)
    ]
    if root:
        pages[""] = root
    return pages


def _heading_for(key: str) -> str:
    """Section heading for a folder name (``syntheses`` → ``Syntheses``)."""
    if key == "":
        return ROOT_SECTION
    return key.replace("-", " ").replace("_", " ").title()


def _managed_headings(pages: dict[str, list[str]]) -> dict[str, str]:
    """Map section key → heading text for every section reindex owns.

    Canonical folders are managed even when empty, so a stale ``## Sources``
    still gets its count corrected and its duplicates collapsed. ``candidates``
    is always managed (#101) so promote/discard can drop dead catalog bullets
    after the folder is emptied.
    """
    managed = {key: _heading_for(key) for key in CANONICAL_FOLDERS}
    for key in ALWAYS_MANAGED_FOLDERS:
        managed.setdefault(key, _heading_for(key))
    for key in pages:
        managed.setdefault(key, _heading_for(key))
    return managed


def _section_order(managed: dict[str, str]) -> list[str]:
    """Canonical folders first, then other folders alphabetically, root last.

    A canonical section with no pages is emitted only when the index already
    has that heading — ``_render`` decides that; here it stays in the order so
    its plan (count 0) exists either way. ``candidates`` is ordered with the
    other non-canonical folders (alphabetically among extras).
    """
    reserved = set(CANONICAL_FOLDERS) | {""}
    extra = sorted(k for k in managed if k not in reserved)
    order = [*CANONICAL_FOLDERS, *extra]
    if "" in managed:
        order.append("")
    return order


# ─── Index text parsing + rendering ────────────────────────────────────


def _split_blocks(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Split index text into ``(preamble, [(heading_line, body)])``."""
    preamble: list[str] = []
    blocks: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if _H2_RE.match(line):
            blocks.append((line, []))
        elif blocks:
            blocks[-1][1].append(line)
        else:
            preamble.append(line)
    return "\n".join(preamble), [(h, "\n".join(b)) for h, b in blocks]


def _section_key(heading_line: str, managed: dict[str, str]) -> str | None:
    """Return the section key a ``## Heading (N)`` line names, else None."""
    match = _H2_RE.match(heading_line)
    if not match:
        return None
    title = match.group("title").strip().lower()
    for key, heading in managed.items():
        if title == heading.lower():
            return key
    return None


def _resolve_href(href: str) -> str:
    """Normalise an index link to a wiki-relative path (``""`` if external).

    Mirrors ``lint.rules._helpers._resolve_index_href``: drops fragments and
    queries, collapses ``.``/``..``, and rejects anything that escapes the
    wiki root or points off-site.
    """
    href = href.split("#", 1)[0].split("?", 1)[0].strip()
    if not href or href.startswith(("http://", "https://", "mailto:")):
        return ""
    parts: list[str] = []
    for seg in href.replace("\\", "/").split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if not parts:
                return ""
            parts.pop()
            continue
        parts.append(seg)
    return "/".join(parts)


def _new_bullet(wiki_dir: Path, rel: str) -> str:
    """Build the bullet for a page that has no entry yet.

    Title comes from frontmatter (falling back to the filename). Description
    comes from a ``description:`` field when the page has one; session sources
    fall back to ``project · date``, which is what the catalog has always shown
    for them. Everything else is listed bare — reindex never invents prose.
    """
    path = wiki_dir / rel
    meta: dict[str, object] = {}
    try:
        meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    except OSError:
        pass
    title = str(meta.get("title") or "").strip() or path.stem
    desc = str(meta.get("description") or "").strip()
    if not desc and rel.startswith("sources/"):
        facets = [
            str(meta.get("project") or "").strip(),
            str(meta.get("date") or "").strip(),
        ]
        desc = " · ".join(f for f in facets if f)
    suffix = f" — {desc}" if desc else ""
    return f"- [{title}]({rel}){suffix}"


def _render(
    preamble: str,
    blocks: list[tuple[str, str]],
    sections: dict[str, SectionPlan],
    managed: dict[str, str],
) -> str:
    """Rebuild the index, replacing managed sections in place.

    The first occurrence of a managed heading is replaced by its rebuilt
    section; later duplicates of the same heading are dropped (the drift #71
    describes — a count-less ``## Sources`` appended below ``## Sources (0)``).
    Managed sections that have pages but no heading yet are appended in
    canonical order.
    """
    chunks: list[str] = []
    seen: set[str] = set()
    for heading_line, body in blocks:
        key = _section_key(heading_line, managed)
        if key is None:
            chunk = "\n".join([heading_line, body]).rstrip()
            chunks.append(chunk)
            continue
        if key in seen:
            continue
        seen.add(key)
        section = sections[key]
        # Drop empty non-canonical sections (e.g. leftover ## Candidates after
        # the last stub was promoted — #101). Canonical empties keep ``(0)``.
        if not section.bullets and key not in CANONICAL_FOLDERS:
            continue
        chunks.append(section.render().rstrip())
    for key, section in sections.items():
        if key in seen or not section.bullets:
            continue
        chunks.append(section.render().rstrip())
    head = preamble.rstrip()
    body_text = "\n\n".join(c for c in chunks if c)
    if head and body_text:
        return f"{head}\n\n{body_text}\n"
    return f"{head or body_text}\n"
