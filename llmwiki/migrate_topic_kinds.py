"""Stamp ``(entity|concept)`` onto older source Connections bullets (#174).

Offline one-time migration: kinds come from pages already under
``wiki/entities/``, ``wiki/concepts/``, and the matching ``wiki/candidates/``
folders. No synthesis backend or network call. Complements the #147 catch-up
path by clearing ``source_page_needs_topics_rewrite`` when at least one
resolvable kind can be stamped — without inventing fact lines.

Usage::

    llmwiki migrate-topic-kinds --vault /path/to/vault --dry-run
    llmwiki migrate-topic-kinds --vault /path/to/vault
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.source_topics import (
    _normalize_kind,
    _split_kind_and_description,
    source_page_needs_topics_rewrite,
)
from llmwiki.wikilinks import WIKILINK_RE, strip_anchor

#: Vault-root JSON listing pages stamped by a successful non-dry-run.
STAMPED_LIST_FILENAME = ".llmwiki-topic-kinds-stamped.json"

#: Folder relative to ``wiki/`` → kind stamped onto Connections bullets.
_KIND_FOLDERS: tuple[tuple[str, str], ...] = (
    ("entities", "entity"),
    ("concepts", "concept"),
    ("candidates/entities", "entity"),
    ("candidates/concepts", "concept"),
)

_CONTEXT_FILE = "_context.md"

#: Same spirit as ``synth.pipeline._CONNECTIONS_HEADING_RE`` (copied to avoid
#: importing the synth package).
_CONNECTIONS_HEADING_RE = re.compile(r"^##[ \t]+Connections[ \t]*$", re.M)
_NEXT_HEADING_RE = re.compile(r"^##[ \t]+", re.M)

#: List item that may open a topic bullet (wikilink must lead the body).
_LIST_ITEM_RE = re.compile(r"^(\s*-\s+)(.*)$")


def build_kind_map(wiki: Path) -> tuple[dict[str, str], list[str]]:
    """Return case-folded stem→kind and ambiguous names skipped.

    Scans ``entities``, ``concepts``, and the candidates mirrors. A stem that
    appears under both kinds is removed from the map and listed as ambiguous
    (never guessed). ``_context.md`` and non-files are ignored.
    """
    kind_map: dict[str, str] = {}
    display: dict[str, str] = {}
    ambiguous_keys: set[str] = set()

    for rel, kind in _KIND_FOLDERS:
        folder = wiki / rel
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.md")):
            if not path.is_file() or path.name == _CONTEXT_FILE:
                continue
            key = path.stem.casefold()
            display.setdefault(key, path.stem)
            if key in ambiguous_keys:
                continue
            existing = kind_map.get(key)
            if existing is None:
                kind_map[key] = kind
            elif existing != kind:
                del kind_map[key]
                ambiguous_keys.add(key)

    ambiguous = sorted(display[k] for k in ambiguous_keys)
    return kind_map, ambiguous


def _connections_span(body: str) -> tuple[int, int] | None:
    """Return ``(start, end)`` of the Connections section body, or ``None``."""
    heading = _CONNECTIONS_HEADING_RE.search(body)
    if heading is None:
        return None
    start = heading.end()
    nxt = _NEXT_HEADING_RE.search(body, start)
    end = nxt.start() if nxt else len(body)
    return start, end


def _stamp_topic_line(
    core: str,
    kind_map: dict[str, str],
    ambiguous: set[str],
) -> tuple[str, str]:
    """Return ``(new_core, outcome)`` for one line without its newline.

    ``outcome`` is one of ``stamped``, ``already``, ``unresolved``, ``skip``.
    """
    match = _LIST_ITEM_RE.match(core)
    if match is None:
        return core, "skip"
    content = match.group(2)
    link_match = WIKILINK_RE.match(content)
    if link_match is None:
        return core, "skip"

    name = strip_anchor(link_match.group(1))
    if not name:
        return core, "skip"

    remainder = content[link_match.end() :]
    kind_raw, _description = _split_kind_and_description(remainder)
    if _normalize_kind(kind_raw) is not None:
        return core, "already"

    key = name.casefold()
    if key in ambiguous or key not in kind_map:
        return core, "unresolved"

    kind = kind_map[key]
    insert_at = match.start(2) + link_match.end()
    return core[:insert_at] + f" ({kind})" + core[insert_at:], "stamped"


def stamp_connections_body(
    body: str,
    kind_map: dict[str, str],
    ambiguous: set[str],
) -> tuple[str, dict[str, int]]:
    """Edit ``## Connections`` only; return new body and per-page counters.

    Already-kinded topic bullets stay byte-identical. Nested ``fact:`` lines
    and every section outside Connections are untouched. Counters:
    ``bullets_stamped``, ``bullets_unresolved``.
    """
    counters = {"bullets_stamped": 0, "bullets_unresolved": 0}
    span = _connections_span(body)
    if span is None:
        return body, counters

    start, end = span
    section = body[start:end]
    out: list[str] = []
    for line in section.splitlines(keepends=True):
        core = line.rstrip("\r\n")
        ending = line[len(core) :]
        new_core, outcome = _stamp_topic_line(core, kind_map, ambiguous)
        if outcome == "stamped":
            counters["bullets_stamped"] += 1
        elif outcome == "unresolved":
            counters["bullets_unresolved"] += 1
        out.append(new_core + ending)

    return body[:start] + "".join(out) + body[end:], counters


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _source_file_meta(text: str) -> str | None:
    meta, _body = parse_frontmatter(text)
    raw = meta.get("source_file")
    if raw is None or raw == "":
        return None
    return str(raw).strip().strip("\"'") or None


def _write_stamped_list(vault: Path, pages: list[dict[str, Any]]) -> None:
    payload = {
        "version": 1,
        "command": "migrate-topic-kinds",
        "issue": 174,
        "stamped_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pages": pages,
    }
    (vault / STAMPED_LIST_FILENAME).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run_migration(*, vault: Path, dry_run: bool = False) -> dict[str, Any]:
    """Stamp missing topic kinds on source Connections under ``vault/wiki``.

    Dry-run computes the same report without writing sources or the stamped
    JSON list. The stamped list is written only on a successful non-dry-run
    that stamps at least one page.
    """
    vault = Path(vault).expanduser().resolve()
    wiki = vault / "wiki"
    report: dict[str, Any] = {
        "vault": str(vault),
        "wiki_dir": str(wiki),
        "dry_run": dry_run,
        "pages_stamped": 0,
        "bullets_stamped": 0,
        "bullets_unresolved": 0,
        "pages_pending_rewrite": 0,
        "facts_derived": 0,
        "ambiguous": [],
        "stamped_pages": [],
        "errors": [],
        "changed": False,
    }
    if not wiki.is_dir():
        report["errors"].append(f"missing wiki dir: {wiki}")
        return report

    kind_map, ambiguous_list = build_kind_map(wiki)
    report["ambiguous"] = ambiguous_list
    ambiguous_set = {name.casefold() for name in ambiguous_list}

    sources_dir = wiki / "sources"
    if not sources_dir.is_dir():
        return report

    for path in sorted(sources_dir.rglob("*.md")):
        if not path.is_file() or path.name == _CONTEXT_FILE:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            report["errors"].append(f"{_relative(path, vault)}: {exc}")
            continue

        # Stamp on the full file so frontmatter bytes stay untouched without
        # a reconstruct step (Connections lives in the body).
        new_text, counters = stamp_connections_body(
            text, kind_map, ambiguous_set
        )
        report["bullets_stamped"] += counters["bullets_stamped"]
        report["bullets_unresolved"] += counters["bullets_unresolved"]

        page_would_stamp = (
            counters["bullets_stamped"] > 0
            and not source_page_needs_topics_rewrite(new_text)
        )
        wrote = False
        if counters["bullets_stamped"] > 0 and new_text != text and not dry_run:
            try:
                path.write_text(new_text, encoding="utf-8")
                wrote = True
            except OSError as exc:
                report["errors"].append(f"{_relative(path, vault)}: {exc}")
                # Do not record this page as stamped — FR6 list must match disk.
                if source_page_needs_topics_rewrite(text):
                    report["pages_pending_rewrite"] += 1
                continue

        # Dry-run: count would-stamp pages without writing JSON. Apply: only
        # after a successful write (or when text was already equal — no-op).
        if page_would_stamp and (dry_run or wrote or new_text == text):
            report["pages_stamped"] += 1
            report["stamped_pages"].append(
                {
                    "wiki_path": _relative(path, vault),
                    "source_file": _source_file_meta(text),
                }
            )

        check_text = (
            new_text
            if counters["bullets_stamped"] > 0 and (dry_run or wrote or new_text == text)
            else text
        )
        if source_page_needs_topics_rewrite(check_text):
            report["pages_pending_rewrite"] += 1

    report["changed"] = (
        report["bullets_stamped"] > 0 or report["pages_stamped"] > 0
    )

    if report["pages_stamped"] > 0 and not dry_run:
        try:
            _write_stamped_list(vault, report["stamped_pages"])
        except OSError as exc:
            report["errors"].append(f"{STAMPED_LIST_FILENAME}: {exc}")

    return report


def print_report(report: dict[str, Any]) -> None:
    """Print an operator-facing summary. Quiet when nothing needs stamping."""
    if not report["changed"] and not report["errors"]:
        print("nothing to migrate: no connection lines need topic kinds")
        return
    print(f"vault:                  {report['vault']}")
    print(f"wiki:                   {report['wiki_dir']}")
    print(f"dry_run:                {report['dry_run']}")
    print(f"pages stamped:          {report['pages_stamped']}")
    print(f"bullets stamped:        {report['bullets_stamped']}")
    print(f"bullets unresolved:     {report['bullets_unresolved']}")
    print(f"pages pending rewrite:  {report['pages_pending_rewrite']}")
    print(f"facts derived:          {report['facts_derived']}")
    if report["ambiguous"]:
        names = ", ".join(report["ambiguous"][:20])
        more = (
            ""
            if len(report["ambiguous"]) <= 20
            else f" … +{len(report['ambiguous']) - 20} more"
        )
        print(f"ambiguous (skipped):    {names}{more}")
    for page in report["stamped_pages"]:
        print(f"  stamped  {page['wiki_path']}")
    if report["errors"]:
        print(f"errors:                 {len(report['errors'])}")
        for err in report["errors"][:10]:
            print(f"  ! {err}")
    print(
        "note: no facts were derived — run `llmwiki synth --force --path …` "
        "on stamped pages (see vault-root "
        f"{STAMPED_LIST_FILENAME}) if you want fact lines."
    )
