"""``llmwiki migrate whole-document-storage`` — merge legacy split documents (#311).

Before #311 a long ``add`` was stored as ``raw/docs/<project>/<slug>-01.md``
… ``<slug>-NN.md`` and summarised into one wiki source page per piece. A new
import is one raw file and one summary page. This migration turns each clear
multi-piece document in an existing vault into that same one-document shape,
offline — no synthesis backend is called and nothing is re-summarised:

* **Group** — raw files that share a directory and the ``-NN``-stripped base
  slug of :func:`~llmwiki.raw_docs_site.base_slug_from_stem` (the #305 site
  grouping) *and* carry ``(part i/N)`` markers, a contiguous ``1..N`` run and
  one agreeing ``content_sha256``. Wiki pages come from each piece's derived
  page name (``<date>-<slug>-NN[--part-MM].md``) and from ``source_file:``
  claims.
* **Ambiguous** (a gap, a hash or project/date/title disagreement, a whole
  ``<slug>.md`` that is not the same document, a wiki page that claims another
  raw file, pieces only partly summarised, a canonical page that claims another
  document) is listed in the preview, and **apply exits non-zero and changes
  nothing** for the whole vault until every ambiguous group is resolved.
* **Raw** — ``raw/docs/<project>/<slug>.md`` is written from the pieces (the
  part breadcrumbs removed, the legacy whole-document ``content_sha256``
  kept, so duplicate detection still matches) when it is missing; a whole file
  with a different hash is never overwritten. The old ``-NN`` files are moved to
  ``.llmwiki-whole-doc-recovery/<UTC>/raw/docs/…``.
* **Wiki** — the pieces' summaries go through the same deterministic
  :func:`~llmwiki.synth.stitch.stitch_chunk_bodies` the synth uses (no AI
  polish); ``tags`` are unioned. The old part pages move to
  ``.llmwiki-whole-doc-recovery/<UTC>/wiki/sources/…`` and their names are
  recorded under the canonical page's ``## Aliases``, so no part page stays in
  the Wiki corpus: every ``[[old-part]]`` link and ``sources:`` entry follows to
  the canonical page. A canonical page that already is a real summary is kept.
* **State** — the per-piece synth state keys collapse to the whole-document key
  and ``synth.pending`` is refreshed. A re-run after a clean apply finds
  nothing to do; a run interrupted part-way resumes.
* **Optional re-synth queue** — the merged documents stay recorded as
  synthesised (stitched summaries kept). :func:`mark_unsynth` (CLI
  ``--mark-unsynth``, or a TTY ``y`` answer) forgets the whole-document keys so
  the next ``llmwiki synth`` re-runs them; the migration itself never calls a
  backend.

Usage::

    llmwiki migrate whole-document-storage --vault /path/to/vault --dry-run
    llmwiki migrate whole-document-storage --vault /path/to/vault
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmwiki._frontmatter import parse_frontmatter
from llmwiki._system_pages import is_archived_path
from llmwiki.add_doc import _frontmatter as _raw_doc_frontmatter
from llmwiki.raw_docs_site import (
    _CHUNK_STEM_SUFFIX_RE,
    _PART_BREADCRUMB_RE,
    base_slug_from_stem,
)
from llmwiki.state_store import mtime_to_iso, resolve_state_file
from llmwiki.state_store import update_state as _update_state
from llmwiki.synth.pipeline import (
    DOCS_REL_PREFIX,
    _append_log,
    _is_stub_page,
    _load_state,
    _rebuild_index,
    is_log_page,
    raw_source_key,
    refresh_synth_pending,
    source_page_paths,
    synth_page_filename,
)
from llmwiki.synth.stitch import stitch_chunk_bodies
from llmwiki.wikilinks import (
    format_alias_bullet,
    norm_page_key,
    parse_page_aliases,
    rewrite_wikilinks,
)

__all__ = ["RECOVERY_DIR_NAME", "mark_unsynth", "merged_document_paths", "print_report", "run_migration"]

#: Vault-root folder the old pieces are moved into, one ``<UTC>/`` run per apply.
RECOVERY_DIR_NAME = ".llmwiki-whole-doc-recovery"

# ``Title (part 3/11)`` / ``Title (part 3/11: Section)`` — add_doc's chunk title.
_PART_TITLE_RE = re.compile(r"\s*\(part (?P<i>\d+)/(?P<n>\d+)(?::.*)?\)\s*$")
_ALIASES_HEADING_RE = re.compile(r"^##[ \t]+Aliases[ \t]*$", re.MULTILINE)
_H2_RE = re.compile(r"^##[ \t]+", re.MULTILINE)
_SOURCES_INLINE_RE = re.compile(r"^(sources:[ \t]*\[)(.*)(\][ \t]*)$")
_SOURCES_BLOCK_RE = re.compile(r"^sources:[ \t]*$")
_BLOCK_ITEM_RE = re.compile(r"^([ \t]*-[ \t]+)(.*?)([ \t]*)$")

_RAW_DOC_STAMP_TAGS = frozenset({"wiki-add", "raw-doc"})


# ─── data model ──────────────────────────────────────────────────────────


@dataclass
class _Page:
    """One live ``wiki/sources`` page."""

    path: Path
    rel: str                      # wiki-relative, posix
    text: str
    meta: dict[str, Any]
    body: str
    stub: bool
    claim: str                    # ``source_file:`` normalised, "" when blank

    @property
    def stem(self) -> str:
        return self.path.stem


@dataclass
class _Part:
    """One legacy raw piece (``<base>-NN.md``)."""

    path: Path
    rel: str                      # relative to raw/docs, posix
    stem: str
    meta: dict[str, Any]
    body: str                     # body with the part breadcrumb removed
    index: int                    # NN from the stem
    marker: tuple[int, int] | None  # (i, N) from ``(part i/N)`` in the title
    pages: list[_Page] = field(default_factory=list)

    @property
    def source_file(self) -> str:
        return raw_source_key(DOCS_REL_PREFIX + self.rel, is_doc=True)

    @property
    def state_key(self) -> str:
        return DOCS_REL_PREFIX + self.rel


@dataclass
class _Group:
    """One logical document stored in pieces."""

    key: str                      # ``<raw/docs-relative dir>/<base>``
    base: str
    directory: Path
    parts: list[_Part]
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    # whole raw document
    whole_path: Path | None = None
    whole_exists: bool = False
    title: str = ""
    project: str = "docs"
    date: str = ""
    content_hash: str = ""
    source: str = ""
    extractor: str = ""
    # wiki
    wiki_state: str = "none"      # none | stub | real
    pages: list[_Page] = field(default_factory=list)       # every old page, doc order
    merge: list[_Page] = field(default_factory=list)       # the real ones
    canonical_path: Path | None = None
    canonical_action: str = "none"  # none | write | replace | keep
    canonical_existing: _Page | None = None
    old_stems: list[str] = field(default_factory=list)
    state_present: list[str] = field(default_factory=list)

    @property
    def ambiguous(self) -> bool:
        return bool(self.reasons)

    @property
    def whole_rel(self) -> str:
        """``raw/docs``-relative path of the whole document."""
        return f"{self.key}.md"


# ─── reading ─────────────────────────────────────────────────────────────


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _read(path: Path, errors: list[str], root: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"{_rel(path, root)}: {exc}")
        return None


def _strip_breadcrumb(body: str) -> str:
    """Drop the ``> Part i of N of **Title**`` line add_doc put above a piece."""
    text = body.lstrip("\n")
    m = _PART_BREADCRUMB_RE.match(text)
    if m:
        text = text[m.end():]
    return text.strip("\n")


def _str_tags(meta: dict[str, Any]) -> list[str]:
    raw = meta.get("tags", [])
    if isinstance(raw, str):
        raw = [raw]
    return [str(t).strip() for t in raw or [] if str(t).strip()]


def _scan_raw_docs(docs_dir: Path, vault: Path, errors: list[str]) -> dict[Path, dict[str, _Part]]:
    """Every raw doc, keyed by directory then stem (``_``-prefixed files skipped)."""
    out: dict[Path, dict[str, _Part]] = {}
    if not docs_dir.is_dir():
        return out
    for path in sorted(docs_dir.rglob("*.md")):
        rel_parts = path.relative_to(docs_dir).parts
        if any(p.startswith("_") for p in rel_parts) or not path.is_file():
            continue
        text = _read(path, errors, vault)
        if text is None:
            continue
        meta, body = parse_frontmatter(text)
        m = _CHUNK_STEM_SUFFIX_RE.search(path.stem)
        index = int(m.group()[1:]) if m else -1
        marker_m = _PART_TITLE_RE.search(str(meta.get("title") or ""))
        marker = (int(marker_m["i"]), int(marker_m["n"])) if marker_m else None
        out.setdefault(path.parent, {})[path.stem] = _Part(
            path=path,
            rel=path.relative_to(docs_dir).as_posix(),
            stem=path.stem,
            meta=meta,
            body=_strip_breadcrumb(body),
            index=index,
            marker=marker,
        )
    return out


def _scan_wiki_sources(wiki: Path, vault: Path, errors: list[str]) -> list[_Page]:
    root = wiki / "sources"
    pages: list[_Page] = []
    if not root.is_dir():
        return pages
    for path in sorted(root.rglob("*.md")):
        if path.name.startswith("_") or not path.is_file():
            continue
        text = _read(path, errors, vault)
        if text is None:
            continue
        meta, body = parse_frontmatter(text)
        pages.append(_Page(
            path=path,
            rel=path.relative_to(wiki).as_posix(),
            text=text,
            meta=meta,
            body=body,
            stub=_is_stub_page(body),
            claim=str(meta.get("source_file") or "").replace("\\", "/").strip(),
        ))
    return pages


# ─── planning ────────────────────────────────────────────────────────────


def _clean_title(title: str) -> str:
    return _PART_TITLE_RE.sub("", title).strip()


def _check_raw(group: _Group, siblings: dict[str, _Part]) -> None:
    """Fill ``group.reasons`` from the raw pieces; set the whole-document fields."""
    parts = group.parts
    reasons = group.reasons
    for part in parts:
        if part.marker is None:
            reasons.append(f"{part.rel}: no '(part i/N)' marker in its title")
    totals = {p.marker[1] for p in parts if p.marker}
    if len(totals) > 1:
        reasons.append(f"pieces disagree on the total part count: {sorted(totals)}")
    if len(totals) == 1:
        total = next(iter(totals))
        present = {p.index for p in parts}
        expected = set(range(1, total + 1))
        if expected - present:
            missing = ", ".join(f"{i:02d}" for i in sorted(expected - present))
            reasons.append(f"gap: part(s) {missing} of {total} are missing")
        if present - expected:
            extra = ", ".join(f"{i:02d}" for i in sorted(present - expected))
            reasons.append(f"unexpected part number(s) {extra} for a {total}-part document")
    for part in parts:
        if part.marker and part.marker[0] != part.index:
            reasons.append(f"{part.rel}: filename says part {part.index:02d}, title says part {part.marker[0]}")

    hashes = {str(p.meta.get("content_sha256") or "").strip() for p in parts}
    if "" in hashes or len(hashes) != 1:
        shown = sorted(h[:12] if h else "<none>" for h in hashes)
        reasons.append(f"pieces do not agree on one content_sha256: {', '.join(shown)}")
    projects = {str(p.meta.get("project") or "docs") for p in parts}
    if len(projects) > 1:
        reasons.append(f"pieces name different projects: {', '.join(sorted(projects))}")
    dates = {str(p.meta.get("date") or "") for p in parts}
    if len(dates) > 1:
        reasons.append(f"pieces carry different dates: {', '.join(sorted(dates))}")
    titles = {_clean_title(str(p.meta.get("title") or "")) for p in parts}
    if len(titles) > 1:
        reasons.append("pieces carry different document titles")

    first = parts[0]
    group.title = _clean_title(str(first.meta.get("title") or "")) or group.base
    group.project = str(first.meta.get("project") or "docs")
    group.date = str(first.meta.get("date") or "")
    group.content_hash = next(iter(hashes)) if len(hashes) == 1 else ""
    group.source = str(first.meta.get("source") or "")
    group.extractor = next((str(p.meta.get("extractor")) for p in parts if p.meta.get("extractor")), "")
    group.whole_path = group.directory / f"{group.base}.md"

    whole = siblings.get(group.base)
    if whole is not None:
        group.whole_exists = True
        whole_hash = str(whole.meta.get("content_sha256") or "").strip()
        if not whole_hash or whole_hash != group.content_hash:
            reasons.append(
                f"{whole.rel} already exists with a different content_sha256 "
                f"({whole_hash[:12] or '<none>'} vs {group.content_hash[:12] or '<none>'}); "
                "it is never overwritten"
            )


def _attach_wiki(
    group: _Group,
    sources_dir: Path,
    by_path: dict[Path, _Page],
    by_claim: dict[str, list[_Page]],
) -> None:
    """Find each piece's wiki pages and classify the group's wiki side."""
    reasons = group.reasons
    for part in group.parts:
        project = str(part.meta.get("project") or "docs")
        filename = synth_page_filename(part.meta, part.path.stem)
        found: list[_Page] = []
        for path in source_page_paths(sources_dir / project, filename, is_doc=True):
            page = by_path.get(path)
            if page is None:
                continue
            if page.claim and page.claim != part.source_file:
                reasons.append(
                    f"wiki page {page.rel} claims {page.claim}, not {part.source_file}"
                )
                continue
            found.append(page)
        for page in sorted(by_claim.get(part.source_file, []), key=lambda p: p.rel):
            if page not in found:
                found.append(page)
        part.pages = found
        group.old_stems.append(filename)
        states = {p.stub for p in found}
        if len(states) > 1:
            reasons.append(f"{part.rel}: some of its wiki pages are real and some are stubs")

    for part in group.parts:
        group.pages.extend(part.pages)
        for page in part.pages:
            if page.stem not in group.old_stems:
                group.old_stems.append(page.stem)
    group.merge = [p for p in group.pages if not p.stub]
    covered = [bool(part.pages) and not part.pages[0].stub for part in group.parts]
    if group.merge:
        group.wiki_state = "real"
        if not all(covered):
            missing = ", ".join(
                part.rel for part, ok in zip(group.parts, covered, strict=True) if not ok
            )
            reasons.append(f"wiki summaries cover only some pieces; no real summary for: {missing}")
    elif group.pages:
        group.wiki_state = "stub"

    # canonical page for the whole document
    project_dir = sources_dir / group.project
    filename = synth_page_filename({"slug": group.base, "date": group.date}, group.base)
    group.canonical_path = project_dir / f"{filename}.md"
    existing = by_path.get(group.canonical_path)
    group.canonical_existing = existing
    whole_source = f"raw/docs/{group.whole_rel}"
    if existing is not None and existing.claim and existing.claim != whole_source:
        reasons.append(
            f"canonical page {existing.rel} claims {existing.claim}, not {whole_source}"
        )
    if group.wiki_state == "real":
        if existing is None:
            group.canonical_action = "write"
        elif existing.stub:
            group.canonical_action = "replace"
        else:
            group.canonical_action = "keep"
            group.notes.append("a real canonical page already exists and is kept")
    elif existing is not None and not existing.stub:
        group.canonical_action = "keep"
    # a page the group would relocate is never the canonical page itself
    group.pages = [p for p in group.pages if p.path != group.canonical_path]
    group.merge = [p for p in group.merge if p.path != group.canonical_path]


def _plan(vault: Path, errors: list[str]) -> list[_Group]:
    docs_dir = vault / "raw" / "docs"
    wiki = vault / "wiki"
    raw = _scan_raw_docs(docs_dir, vault, errors)
    pages = _scan_wiki_sources(wiki, vault, errors)
    by_path = {p.path: p for p in pages}
    by_claim: dict[str, list[_Page]] = {}
    for page in pages:
        if page.claim:
            by_claim.setdefault(page.claim, []).append(page)

    groups: list[_Group] = []
    for directory, docs in sorted(raw.items()):
        by_base: dict[str, list[_Part]] = {}
        for stem, part in docs.items():
            if _CHUNK_STEM_SUFFIX_RE.search(stem):
                by_base.setdefault(base_slug_from_stem(stem), []).append(part)
        for base, members in sorted(by_base.items()):
            members.sort(key=lambda p: p.index)
            key = (directory.relative_to(docs_dir) / base).as_posix()
            if not any(m.marker for m in members):
                # Numbered names with no part markers are separate documents
                # (``chapter-01``, ``v0-7-55``) — unless they share one hash.
                hashes = {str(m.meta.get("content_sha256") or "").strip() for m in members}
                if len(members) > 1 and len(hashes) == 1 and "" not in hashes:
                    group = _Group(key=key, base=base, directory=directory, parts=members)
                    group.reasons.append(
                        "numbered files share one content_sha256 but carry no '(part i/N)' markers"
                    )
                    group.whole_path = directory / f"{base}.md"
                    groups.append(group)
                continue
            group = _Group(key=key, base=base, directory=directory, parts=members)
            _check_raw(group, docs)
            _attach_wiki(group, wiki / "sources", by_path, by_claim)
            groups.append(group)

    # two groups may never land on one canonical page
    seen: dict[Path, _Group] = {}
    for group in groups:
        cp = group.canonical_path
        if cp is None:
            continue
        other = seen.get(cp)
        if other is not None and not group.ambiguous and not other.ambiguous:
            msg = f"canonical page {_rel(cp, vault / 'wiki')} is also the target of {other.key}"
            group.reasons.append(msg)
            other.reasons.append(f"canonical page {_rel(cp, vault / 'wiki')} is also the target of {group.key}")
        seen.setdefault(cp, group)

    state_file = resolve_state_file(vault)
    try:
        state = _load_state(state_file)
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f"state load: {exc}")
        state = {}
    for group in groups:
        group.state_present = [p.state_key for p in group.parts if p.state_key in state]
    return groups


# ─── page / raw composition ──────────────────────────────────────────────


def _whole_raw_text(group: _Group) -> str:
    tags = [t for t in _union_tags([_str_tags(p.meta) for p in group.parts]) if t not in _RAW_DOC_STAMP_TAGS]
    fm = _raw_doc_frontmatter(
        group.title, group.base, group.project, tuple(tags), group.date, group.source,
        content_sha256=group.content_hash, extractor=group.extractor or None,
    )
    body = "\n\n".join(p.body for p in group.parts if p.body).rstrip("\n")
    return fm + body + "\n"


def _union_tags(lists: list[list[str]]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for tags in lists:
        for tag in tags:
            if tag.casefold() not in seen:
                seen.add(tag.casefold())
                out.append(tag)
    return out


def _canonical_page_text(group: _Group, today: str) -> str:
    tags = _union_tags([_str_tags(p.meta) for p in group.merge])
    model = next((str(p.meta.get("model")) for p in group.merge if p.meta.get("model")), "")
    body = stitch_chunk_bodies([p.body.strip("\n") for p in group.merge]).strip("\n") + "\n"
    fm = [
        "---",
        f"title: {json.dumps(group.title, ensure_ascii=False)}",
        "type: source",
        f"tags: [{', '.join(tags)}]",
        f"date: {group.date}",
        f"source_file: raw/docs/{group.whole_rel}",
        f"project: {group.project}",
        f"model: {model}",
        f"last_updated: {today}",
        "---",
        "",
    ]
    return "\n".join(fm) + body


def _with_aliases(text: str, stems: list[str], canonical_stem: str, today: str, parts: int) -> str:
    """Record the old part names under ``## Aliases`` (once each)."""
    _meta, body = parse_frontmatter(text)
    have = {a.casefold() for a in parse_page_aliases(body)}
    new = [s for s in stems if s != canonical_stem and s.casefold() not in have]
    if not new:
        return text
    note = f"whole-document storage {today} ({parts} parts)"
    bullets = "\n".join(format_alias_bullet(s, note) for s in new)
    heading = _ALIASES_HEADING_RE.search(text)
    if heading is None:
        return text.rstrip("\n") + f"\n\n## Aliases\n\n{bullets}\n"
    nxt = _H2_RE.search(text, heading.end())
    end = nxt.start() if nxt else len(text)
    head = text[:end].rstrip("\n")
    tail = text[end:]
    return head + "\n" + bullets + "\n" + (("\n" + tail) if tail else "")


def _rewrite_sources_field(text: str, mapping: dict[str, str]) -> str:
    """Map old stems to canonical stems in the frontmatter ``sources:`` list."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n").lstrip("﻿") != "---":
        return text
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip("\r\n").strip() == "---"), None)
    if end is None:
        return text

    def _bare(item: str) -> str:
        s = item.strip()
        return s[1:-1] if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"" else s

    def _remap(item: str) -> str:
        s = item.strip()
        value = _bare(s)
        new = mapping.get(value, value)
        if new == value:
            return s
        return f"{s[0]}{new}{s[0]}" if value != s else new

    out = list(lines)
    in_block = False
    block_seen: set[str] = set()
    drop: set[int] = set()
    for i in range(1, end):
        body = lines[i].rstrip("\r\n")
        nl = lines[i][len(body):]
        if in_block:
            m = _BLOCK_ITEM_RE.match(body)
            if m:
                new = _remap(m.group(2))
                if _bare(new) in block_seen:
                    drop.add(i)
                    continue
                block_seen.add(_bare(new))
                out[i] = f"{m.group(1)}{new}{m.group(3)}{nl}"
                continue
            in_block = False
        if _SOURCES_BLOCK_RE.match(body):
            in_block, block_seen = True, set()
            continue
        m = _SOURCES_INLINE_RE.match(body)
        if not m or not m.group(2).strip():
            continue
        items = [_remap(x) for x in m.group(2).split(",")]
        deduped: list[str] = []
        for item in items:
            if _bare(item) not in {_bare(d) for d in deduped}:
                deduped.append(item)
        new_body = f"{m.group(1)}{', '.join(deduped)}{m.group(3)}"
        if new_body != body:
            out[i] = new_body + nl
    return "".join(line for i, line in enumerate(out) if i not in drop)


# ─── apply ───────────────────────────────────────────────────────────────


class _Recovery:
    """Lazily created ``.llmwiki-whole-doc-recovery/<UTC>/`` run folder."""

    def __init__(self, vault: Path, now: datetime) -> None:
        self._vault = vault
        self._stamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        self.root: Path | None = None
        self.moves: list[dict[str, str]] = []
        self.state_removed: dict[str, Any] = {}

    def _ensure(self) -> Path:
        if self.root is None:
            base = self._vault / RECOVERY_DIR_NAME
            base.mkdir(parents=True, exist_ok=True)
            root = base / self._stamp
            n = 2
            while True:
                try:
                    root.mkdir()
                    break
                except FileExistsError:
                    root = base / f"{self._stamp}-{n}"
                    n += 1
            self.root = root
        return self.root

    def move(self, path: Path) -> Path:
        dest = self._ensure() / path.relative_to(self._vault)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(dest))
        self.moves.append({
            "from": path.relative_to(self._vault).as_posix(),
            "to": dest.relative_to(self._vault).as_posix(),
        })
        return dest

    def write_manifest(self) -> None:
        if self.root is None:
            return
        manifest = {
            "migration": "whole-document-storage",
            "moves": self.moves,
            "state_removed": self.state_removed,
        }
        (self.root / "MANIFEST.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def _link_targets(groups: list[_Group], live: list[Path], wiki: Path) -> tuple[dict[str, str | None], dict[str, str], list[str]]:
    """Map every old part name to its canonical stem.

    Returns ``(link targets by norm key, sources: stem map, notes)``. A name
    that a live page outside the migrated set also answers to is left alone:
    rewriting it could capture links meant for that page.
    """
    relocated = {p.path for g in groups for p in g.pages}
    live_keys = {norm_page_key(p.stem) for p in live if p not in relocated}
    targets: dict[str, str | None] = {}
    stems: dict[str, str] = {}
    notes: list[str] = []
    for group in groups:
        assert group.canonical_path is not None
        canonical = group.canonical_path.stem
        for stem in group.old_stems:
            if stem == canonical:
                continue
            if norm_page_key(stem) in live_keys:
                notes.append(f"[[{stem}]] also names a live page; links to it were left as they are")
                continue
            stems[stem] = canonical
            targets[norm_page_key(stem)] = canonical
        for page in group.pages:
            if page.stem not in stems:
                continue
            rel = page.rel.removesuffix(".md")      # sources/<project>/<stem>
            for variant in (rel, f"wiki/{rel}", rel.removeprefix("sources/")):
                targets[norm_page_key(variant)] = canonical
    return targets, stems, notes


def _apply(
    vault: Path,
    groups: list[_Group],
    now: datetime,
    errors: list[str],
    report: dict[str, Any],
) -> None:
    wiki = vault / "wiki"
    today = now.astimezone(UTC).strftime("%Y-%m-%d")
    recovery = _Recovery(vault, now)
    ready: list[_Group] = []

    # 1. the whole raw file and the canonical page — additive, nothing moves yet
    for group in groups:
        assert group.whole_path is not None and group.canonical_path is not None
        try:
            if not group.whole_exists:
                group.whole_path.write_text(_whole_raw_text(group), encoding="utf-8")
            if group.canonical_action in ("write", "replace"):
                if group.canonical_action == "replace" and group.canonical_existing is not None:
                    recovery.move(group.canonical_existing.path)
                group.canonical_path.parent.mkdir(parents=True, exist_ok=True)
                text = _canonical_page_text(group, today)
                group.canonical_path.write_text(
                    _with_aliases(text, group.old_stems, group.canonical_path.stem, today, len(group.parts)),
                    encoding="utf-8",
                )
            elif group.canonical_action == "keep" and group.canonical_existing is not None:
                kept = group.canonical_existing.text
                aliased = _with_aliases(kept, group.old_stems, group.canonical_path.stem, today, len(group.parts))
                if aliased != kept:
                    group.canonical_path.write_text(aliased, encoding="utf-8")
        except OSError as exc:
            errors.append(f"{group.key}: {exc}; group skipped")
            continue
        # 2. the old part pages leave the live wiki (recoverable)
        try:
            for page in group.pages:
                if page.path.is_file():
                    recovery.move(page.path)
        except OSError as exc:
            errors.append(f"{group.key}: {exc}; old pages only partly moved, rerun to resume")
            continue
        ready.append(group)

    if ready:
        _rewrite_links(vault, wiki, ready, errors, report)
        _update_synth_state(vault, ready, recovery, errors)

    # 3. the raw pieces move last: they are what a re-run finds the group by
    state_ok = not any(e.startswith("state:") for e in errors)
    for group in ready if state_ok else []:
        try:
            for part in group.parts:
                if part.path.is_file():
                    recovery.move(part.path)
        except OSError as exc:
            errors.append(f"{group.key}: {exc}; raw pieces only partly moved, rerun to resume")
            continue
        report["applied"].append(group.key)
    recovery.write_manifest()
    report["recovery_dir"] = _rel(recovery.root, vault) if recovery.root else None
    report["moved"] = recovery.moves


def _rewrite_links(
    vault: Path, wiki: Path, ready: list[_Group], errors: list[str], report: dict[str, Any]
) -> None:
    live = [
        p for p in sorted(wiki.rglob("*.md"))
        if p.is_file() and not is_archived_path(p.relative_to(wiki).parts)
        and not (p.parent == wiki and is_log_page(p.name))
    ]
    targets, stems, notes = _link_targets(ready, live, wiki)
    report["notes"].extend(notes)
    pages_changed = 0
    links = 0
    for path in live:
        text = _read(path, errors, vault)
        if text is None:
            continue
        new, counts = rewrite_wikilinks(text, targets, self_stem=path.stem)
        new = _rewrite_sources_field(new, stems)
        if new == text:
            continue
        try:
            path.write_text(new, encoding="utf-8")
        except OSError as exc:
            errors.append(f"{_rel(path, wiki)}: {exc}")
            continue
        pages_changed += 1
        links += sum(counts.values())
    report["pages_rewritten"] = pages_changed
    report["links_rewritten"] = links


def _update_synth_state(
    vault: Path, ready: list[_Group], recovery: _Recovery, errors: list[str]
) -> None:
    state_file = resolve_state_file(vault)
    removed: dict[str, Any] = {}
    add: dict[str, str] = {}
    for group in ready:
        assert group.whole_path is not None and group.canonical_path is not None
        part_keys = [p.state_key for p in group.parts]
        canonical = group.canonical_path
        done = canonical.is_file() and not _is_stub_page(
            parse_frontmatter(canonical.read_text(encoding="utf-8"))[1]
        )
        if done:
            add[DOCS_REL_PREFIX + group.whole_rel] = mtime_to_iso(group.whole_path.stat().st_mtime)
        for k in part_keys:
            removed[k] = None

    def _mut(s: dict[str, Any]) -> dict[str, Any]:
        synth = s.setdefault("synth", {})
        files = dict(synth.get("files") or {}) if isinstance(synth.get("files"), dict) else {}
        for key in removed:
            if key in files:
                recovery.state_removed[key] = files.pop(key)
        for key, value in add.items():
            files.setdefault(key, value)
        synth["files"] = files
        return s

    try:
        _update_state(_mut, state_file)
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f"state: {exc}")


def merged_document_paths(report: dict[str, Any]) -> list[str]:
    """Vault-relative ``raw/docs/…`` paths of the documents an apply merged."""
    return [f"raw/docs/{key}.md" for key in report.get("applied", [])]


def mark_unsynth(vault: Path, report: dict[str, Any]) -> list[str]:
    """Drop the whole-document synth-done keys of the merged documents and refresh pending.

    Optional follow-up to an apply (#311): the merge records each document as
    synthesised (stitched summary kept). This forgets that, so the next
    ``llmwiki synth`` re-summarises the documents. No backend is called. Returns
    the ``docs::<rel>`` keys that were actually removed; failures are appended to
    ``report["errors"]``.
    """
    vault = Path(vault).expanduser().resolve()
    keys = [f"{DOCS_REL_PREFIX}{key}.md" for key in report.get("applied", [])]
    state_file = resolve_state_file(vault)
    dropped: list[str] = []

    def _mut(s: dict[str, Any]) -> dict[str, Any]:
        synth = s.setdefault("synth", {})
        files = dict(synth.get("files") or {}) if isinstance(synth.get("files"), dict) else {}
        for key in keys:
            if key in files:
                files.pop(key)
                dropped.append(key)
        synth["files"] = files
        return s

    errors: list[str] = report.setdefault("errors", [])
    try:
        _update_state(_mut, state_file)
        refresh_synth_pending(
            raw_dir=vault / "raw" / "sessions",
            docs_dir=vault / "raw" / "docs",
            wiki_sources_dir=vault / "wiki" / "sources",
            state_file=state_file,
        )
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f"mark-unsynth: {exc}")
    return dropped


# ─── entry point ─────────────────────────────────────────────────────────


def _group_report(group: _Group, vault: Path) -> dict[str, Any]:
    wiki = vault / "wiki"
    assert group.whole_path is not None
    return {
        "key": group.key,
        "status": "ambiguous" if group.ambiguous else "clear",
        "reasons": list(group.reasons),
        "parts": [p.rel for p in group.parts],
        "whole_raw": f"raw/docs/{group.whole_rel}",
        "whole_raw_exists": group.whole_exists,
        "wiki_state": group.wiki_state,
        "wiki_pages": [p.rel for p in group.pages],
        "canonical_page": _rel(group.canonical_path, wiki) if group.canonical_path else None,
        "canonical_action": group.canonical_action,
        "state_keys": list(group.state_present),
        "notes": list(group.notes),
    }


def run_migration(
    *, vault: Path, dry_run: bool = False, now: datetime | None = None
) -> dict[str, Any]:
    """Merge every clear multi-piece document under ``vault``; block on ambiguity.

    Returns a report dict. ``blocked`` is true when an ambiguous group stopped an
    apply (nothing was changed); ``changed`` is false on a clean second run.
    """
    vault = Path(vault).expanduser().resolve()
    report: dict[str, Any] = {
        "vault": str(vault),
        "dry_run": dry_run,
        "groups": [],
        "ambiguous": [],
        "blocked": False,
        "applied": [],
        "moved": [],
        "recovery_dir": None,
        "pages_rewritten": 0,
        "links_rewritten": 0,
        "notes": [],
        "errors": [],
        "changed": False,
    }
    errors: list[str] = report["errors"]
    if not (vault / "raw").is_dir() and not (vault / "wiki").is_dir():
        errors.append(f"not a vault (no raw/ or wiki/): {vault}")
        return report

    groups = _plan(vault, errors)
    report["groups"] = [_group_report(g, vault) for g in groups]
    report["ambiguous"] = [g for g in report["groups"] if g["status"] == "ambiguous"]
    clear = [g for g in groups if not g.ambiguous]
    report["changed"] = bool(clear) and not report["ambiguous"]
    if dry_run:
        report["changed"] = bool(clear)
        return report
    if report["ambiguous"]:
        report["blocked"] = True
        report["changed"] = False
        return report
    if not clear:
        return report

    _apply(vault, clear, now or datetime.now(UTC), errors, report)
    wiki = vault / "wiki"
    if report["applied"]:
        if (wiki / "index.md").is_file():
            try:
                _rebuild_index(wiki)
            except (OSError, ValueError, RuntimeError) as exc:
                errors.append(f"index rebuild: {exc}")
        try:
            refresh_synth_pending(
                raw_dir=vault / "raw" / "sessions",
                docs_dir=vault / "raw" / "docs",
                wiki_sources_dir=wiki / "sources",
                state_file=resolve_state_file(vault),
            )
        except (OSError, ValueError) as exc:
            errors.append(f"pending refresh: {exc}")
        _append_log(
            "whole-document storage",
            log_path=wiki / "log.md",
            operation="migrate",
            details={"processed": f"{len(report['applied'])} document(s) merged"},
        )
    return report


def print_report(report: dict[str, Any]) -> None:
    """Print the groups, what each would (or did) do, ambiguity and recovery."""
    groups = report["groups"]
    if not groups and not report["errors"]:
        print("nothing to migrate: no document is stored in pieces")
        return
    mode = "preview (no changes made)" if report["dry_run"] else "apply"
    print(f"vault:   {report['vault']}")
    print(f"mode:    {mode}")
    clear = [g for g in groups if g["status"] == "clear"]
    print(f"documents stored in pieces: {len(groups)} ({len(clear)} clear, {len(report['ambiguous'])} ambiguous)")
    for g in clear:
        print(f"  {g['key']}: {len(g['parts'])} raw pieces → {g['whole_raw']}")
        if g["whole_raw_exists"]:
            print("    raw: whole file already present (same content_sha256); pieces will be relocated")
        action = g["canonical_action"]
        if action in ("write", "replace"):
            print(f"    wiki: {len(g['wiki_pages'])} page(s) → {g['canonical_page']} (stitched, tags unioned)")
        elif action == "keep":
            print(f"    wiki: {g['canonical_page']} kept; {len(g['wiki_pages'])} part page(s) relocated + aliased")
        elif g["wiki_pages"]:
            print(f"    wiki: {len(g['wiki_pages'])} stub page(s) relocated; synth will summarise the whole file")
        else:
            print("    wiki: no summary pages; synth will summarise the whole file")
        for note in g["notes"]:
            print(f"    note: {note}")
    for g in report["ambiguous"]:
        print(f"  ! AMBIGUOUS {g['key']}:")
        for reason in g["reasons"]:
            print(f"      - {reason}")
    if report["ambiguous"]:
        if report["dry_run"]:
            print("apply would be blocked: resolve every ambiguous group first (apply changes nothing until then)")
        else:
            print("blocked: nothing was changed. Resolve every ambiguous group above, then re-run.")
    if not report["dry_run"] and report["applied"]:
        print(f"merged:  {len(report['applied'])} document(s)")
        print(f"links:   {report['links_rewritten']} rewritten across {report['pages_rewritten']} page(s)")
        if report["recovery_dir"]:
            print(f"recovery: {report['recovery_dir']}/ (old raw pieces and part pages; MANIFEST.json lists every move)")
        print("note: run `llmwiki build --vault …` so site/ picks up the merged pages.")
    for note in report["notes"]:
        print(f"  note: {note}")
    if report["errors"]:
        print(f"errors:  {len(report['errors'])}")
        for err in report["errors"][:10]:
            print(f"  ! {err}")
