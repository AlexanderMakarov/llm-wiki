"""Heal document source pages synthesised before #307.

Older releases wrote every ``wiki/sources/`` page synthesised from
``raw/docs/`` with a blank ``source_file:`` and stamped it
``session-transcript``. Re-synth fills the claim in but keeps the stale tag
(existing tags are treated as curation), and re-synth costs a backend call.
This offline migration:

* walks ``raw/docs/`` and derives each doc's page path exactly as synth does
  (:func:`synth_page_filename` + :func:`source_page_paths`, including
  ``--part-NN`` pages), then fills a blank ``source_file`` on that page with
  the claim synth would write today (:func:`raw_source_key`, or the doc's own
  declared ``source_file``);
* removes ``session-transcript`` from every page it identifies as a document
  — by that forward match, by a ``raw/docs/`` claim, or by a ``raw-doc`` /
  ``wiki-add`` tag — and adds ``raw-doc`` when neither document tag remains;
* reports, and leaves untouched, a blank-claim page two raw docs derive to;
* reports a doc-tagged page no raw doc derives to, leaving its claim blank.

A page whose ``source_file`` names ``raw/sessions/`` is never touched.
``raw/`` is never written. Safe to re-run.

Usage::

    llmwiki migrate doc-source-provenance --vault /path/to/vault --dry-run
    llmwiki migrate doc-source-provenance --vault /path/to/vault
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.migrate_broken_provenance import _rewrite_source_file_line
from llmwiki.state_store import resolve_state_file
from llmwiki.synth.pipeline import (
    DOCS_REL_PREFIX,
    _append_log,
    _discover_raw_docs,
    raw_source_key,
    refresh_synth_pending,
    source_page_paths,
    synth_page_filename,
)

_FENCE = re.compile(r"^---[ \t]*$")
_TAGS_LINE = re.compile(r"^tags:[ \t]*(.*?)[ \t]*$")
_BLOCK_ITEM = re.compile(r"^([ \t]+)-[ \t]+(.*?)[ \t]*$")
_SESSION_TAG = "session-transcript"
_DOC_TAGS = ("raw-doc", "wiki-add")
_RAW_SESSIONS_PREFIX = "raw/sessions/"
_RAW_DOCS_PREFIX = "raw/docs/"


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _unquote(token: str) -> str:
    token = token.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


def _claim(meta: dict[str, Any]) -> str:
    return str(meta.get("source_file", "") or "").strip().strip("\"'").replace("\\", "/")


def _expected_claims(vault: Path) -> dict[Path, set[str]]:
    """Map each existing doc source page to the claim(s) synth derives for it."""
    docs_dir = vault / "raw" / "docs"
    sources = vault / "wiki" / "sources"
    out: dict[Path, set[str]] = {}
    for raw_doc, meta, _body in _discover_raw_docs(docs_dir):
        rel = DOCS_REL_PREFIX + str(raw_doc.relative_to(docs_dir))
        key = _claim(meta) or raw_source_key(rel, is_doc=True)
        project = str(meta.get("project") or "docs")
        filename = synth_page_filename(meta, raw_doc.stem)
        for page in source_page_paths(sources / project, filename, is_doc=True):
            out.setdefault(page.resolve(), set()).add(key)
    return out


def _frontmatter_bounds(lines: list[str]) -> int | None:
    """Index of the closing fence, or ``None`` when there is no frontmatter."""
    if not lines or not _FENCE.match(lines[0].rstrip("\r\n")):
        return None
    for i in range(1, len(lines)):
        if _FENCE.match(lines[i].rstrip("\r\n")):
            return i
    return None


def _split_inline(value: str) -> list[str]:
    inner = value[1:-1] if value.startswith("[") and value.endswith("]") else value
    return [t.strip() for t in inner.split(",") if t.strip()]


def _read_tags(text: str) -> list[str]:
    """Tag values from inline (``tags: [a, b]``) or block (``- a``) frontmatter."""
    lines = text.splitlines(keepends=True)
    end = _frontmatter_bounds(lines)
    if end is None:
        return []
    for i in range(1, end):
        m = _TAGS_LINE.match(lines[i].rstrip("\r\n"))
        if not m:
            continue
        if m.group(1):
            return [_unquote(t) for t in _split_inline(m.group(1))]
        values: list[str] = []
        for line in lines[i + 1 : end]:
            item = _BLOCK_ITEM.match(line.rstrip("\r\n"))
            if not item:
                break
            values.append(_unquote(item.group(2)))
        return values
    return []


def _rewrite_doc_tags(text: str) -> tuple[str, bool, bool]:
    """Drop ``session-transcript`` and ensure a document tag.

    Returns ``(text, stripped, added)``. The tags line keeps its form: an
    inline list stays inline, a block list stays a block with its indent.
    """
    lines = text.splitlines(keepends=True)
    end = _frontmatter_bounds(lines)
    if end is None:
        return text, False, False
    ending = lines[0][len(lines[0].rstrip("\r\n")) :] or "\n"

    for i in range(1, end):
        stripped_line = lines[i].rstrip("\r\n")
        m = _TAGS_LINE.match(stripped_line)
        if not m:
            continue
        line_end = lines[i][len(stripped_line) :] or ending
        if m.group(1):
            tokens = _split_inline(m.group(1))
            kept = [t for t in tokens if _unquote(t) != _SESSION_TAG]
            removed = len(kept) != len(tokens)
            added = not any(_unquote(t) in _DOC_TAGS for t in kept)
            if added:
                kept.append("raw-doc")
            if not (removed or added):
                return text, False, False
            lines[i] = f"tags: [{', '.join(kept)}]{line_end}"
            return "".join(lines), removed, added

        j = i + 1
        items: dict[int, str] = {}
        indent = "  "
        while j < end:
            item = _BLOCK_ITEM.match(lines[j].rstrip("\r\n"))
            if not item:
                break
            indent = item.group(1)
            items[j] = _unquote(item.group(2))
            j += 1
        drop = {k for k, v in items.items() if v == _SESSION_TAG}
        added = not any(v in _DOC_TAGS for k, v in items.items() if k not in drop)
        if not (drop or added):
            return text, False, False
        out = [line for k, line in enumerate(lines[:j]) if k not in drop]
        if added:
            out.append(f"{indent}- raw-doc{line_end}")
        out.extend(lines[j:])
        return "".join(out), bool(drop), added

    lines.insert(end, f"tags: [raw-doc]{ending}")
    return "".join(lines), False, True


def run_migration(*, vault: Path, dry_run: bool = False) -> dict[str, Any]:
    """Fill blank document claims and drop session tags under ``vault/wiki/sources``."""
    vault = Path(vault).expanduser().resolve()
    wiki = vault / "wiki"
    sources = wiki / "sources"
    report: dict[str, Any] = {
        "vault": str(vault),
        "wiki_dir": str(wiki),
        "dry_run": dry_run,
        "filled": 0,
        "tags_stripped": 0,
        "raw_doc_added": 0,
        "pages_touched": 0,
        "ambiguous": [],
        "unmatched": [],
        "details": [],
        "errors": [],
        "changed": False,
    }
    if not wiki.is_dir():
        report["errors"].append(f"missing wiki dir: {wiki}")
        return report
    if not sources.is_dir():
        return report

    expected = _expected_claims(vault)

    for path in sorted(sources.rglob("*.md")):
        if not path.is_file() or path.name.startswith("_"):
            continue
        loc = _relative(path, vault)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            report["errors"].append(f"{loc}: {exc}")
            continue
        meta, _body = parse_frontmatter(text)
        claim = _claim(meta if isinstance(meta, dict) else {})
        if claim.startswith(_RAW_SESSIONS_PREFIX):
            continue
        if claim and not claim.startswith(_RAW_DOCS_PREFIX):
            continue

        keys = expected.get(path.resolve(), set())
        doc_tagged = any(t in _DOC_TAGS for t in _read_tags(text))
        new_text = text
        detail: dict[str, Any] = {"wiki_path": loc}

        if not claim:
            if len(keys) > 1:
                report["ambiguous"].append({"wiki_path": loc, "candidates": sorted(keys)})
                continue
            if keys:
                (fill,) = keys
                new_text = _rewrite_source_file_line(new_text, fill)
                if new_text != text:
                    report["filled"] += 1
                    detail["filled"] = fill
            elif doc_tagged:
                report["unmatched"].append(loc)
            else:
                continue

        new_text, stripped, added = _rewrite_doc_tags(new_text)
        if stripped:
            report["tags_stripped"] += 1
            detail["tags_stripped"] = True
        if added:
            report["raw_doc_added"] += 1
            detail["raw_doc_added"] = True

        if new_text == text:
            continue
        if not dry_run:
            try:
                path.write_text(new_text, encoding="utf-8")
            except OSError as exc:
                report["errors"].append(f"{loc}: {exc}")
                continue
        report["pages_touched"] += 1
        report["details"].append(detail)

    report["changed"] = bool(report["pages_touched"])
    if report["changed"] and not dry_run:
        try:
            refresh_synth_pending(
                raw_dir=vault / "raw" / "sessions",
                docs_dir=vault / "raw" / "docs",
                wiki_sources_dir=sources,
                state_file=resolve_state_file(vault),
            )
        except (OSError, ValueError) as exc:
            report["errors"].append(f"pending refresh: {exc}")
        _append_log("doc source provenance", log_path=wiki / "log.md", operation="migrate")
    return report


def print_report(report: dict[str, Any]) -> None:
    """Print an operator-facing summary."""
    if not (report["changed"] or report["errors"] or report["ambiguous"] or report["unmatched"]):
        print("nothing to migrate: every document source page already claims its raw file")
        return
    print(f"vault:          {report['vault']}")
    print(f"wiki:           {report['wiki_dir']}")
    print(f"dry_run:        {report['dry_run']}")
    print(f"claims filled:  {report['filled']}")
    print(f"tags stripped:  {report['tags_stripped']}")
    print(f"raw-doc added:  {report['raw_doc_added']}")
    print(f"pages touched:  {report['pages_touched']}")
    for detail in report["details"][:30]:
        parts = []
        if "filled" in detail:
            parts.append(f"source_file → {detail['filled']}")
        if detail.get("tags_stripped"):
            parts.append(f"-{_SESSION_TAG}")
        if detail.get("raw_doc_added"):
            parts.append("+raw-doc")
        print(f"  {detail['wiki_path']}: {', '.join(parts)}")
    if len(report["details"]) > 30:
        print(f"  … +{len(report['details']) - 30} more")
    if report["ambiguous"]:
        print(f"ambiguous (left unchanged): {len(report['ambiguous'])}")
        for item in report["ambiguous"][:10]:
            print(f"  ? {item['wiki_path']}: {', '.join(item['candidates'])}")
    if report["unmatched"]:
        print(f"unmatched (claim left blank): {len(report['unmatched'])}")
        for loc in report["unmatched"][:10]:
            print(f"  ? {loc}")
    if report["errors"]:
        print(f"errors:         {len(report['errors'])}")
        for err in report["errors"][:10]:
            print(f"  ! {err}")
