"""Move a vault off the ``question`` / ``comparison`` page kinds (#109).

``llmwiki/schema.py`` owns the ``type:`` vocabulary, and it lists five
knowledge kinds: ``source``, ``entity``, ``concept``, ``project``,
``synthesis``. A hand-written page declaring ``question`` or ``comparison``
is therefore a ``frontmatter_validity`` **error**, and this migration is the
supported way to clear it:

* the page's ``type:`` becomes ``concept``;
* the file moves into ``wiki/concepts/`` **keeping its filename**;
* ``wiki/questions/`` and ``wiki/comparisons/`` lose their ``_context.md``
  and are pruned once empty.

Inbound links are deliberately left alone. ``llmwiki.wikilinks`` parses
``[[Target]]`` to a bare name and every consumer — graph, backlinks,
references, ``link_integrity`` — keys pages by filename stem, so a page that
keeps its filename keeps every inbound link no matter which folder it sits
in. Rewriting referrers would be churn with no effect.
:func:`tests.test_page_kinds.test_wikilink_resolution_survives_a_move_between_wiki_folders`
is the evidence.

Two things the migration will not do:

* **Overwrite a page.** When ``wiki/concepts/`` already holds that filename
  the page is retyped where it stands and reported as a collision — the
  vault lints clean and both files survive for the user to reconcile.
* **Delete content it does not recognise.** A removed folder holding
  anything else is left in place and reported.

Usage::

    llmwiki migrate-page-kinds --vault /path/to/vault --dry-run
    llmwiki migrate-page-kinds --vault /path/to/vault
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.synth.pipeline import _append_log, _rebuild_index

#: ``type:`` values this migration clears out of a vault.
REMOVED_KINDS: tuple[str, ...] = ("question", "comparison")

#: Folders those kinds conventionally lived in.
REMOVED_FOLDERS: tuple[str, ...] = ("questions", "comparisons")

#: What a removed-kind page becomes.
TARGET_KIND = "concept"
TARGET_FOLDER = "concepts"

CONTEXT_FILE = "_context.md"

#: Per-action report counter each planned page increments.
_COUNTER = {"moved": "moved", "retyped": "retyped", "collision": "collisions"}

_TYPE_LINE = re.compile(r"^type:[ \t]*\S")
_FENCE = re.compile(r"^---[ \t]*$")
_INDEX_BULLET = re.compile(r"^\s*[-*]\s+\[[^\]]*\]\(([^)\s]+)")


def page_kind(text: str) -> str:
    """Return the frontmatter ``type:`` of ``text``, unquoted and stripped."""
    meta, _body = parse_frontmatter(text)
    return str(meta.get("type") or "").strip().strip("\"'")


def retype_text(text: str) -> str:
    """Return ``text`` with the frontmatter ``type:`` set to ``concept``.

    Only the ``type:`` line inside the leading frontmatter block is touched;
    line endings and every other line are preserved byte for byte.
    """
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines[1:], start=1):
        stripped = line.rstrip("\r\n")
        if _FENCE.match(stripped):
            break
        if _TYPE_LINE.match(stripped):
            lines[i] = f"type: {TARGET_KIND}{line[len(stripped):]}"
            break
    return "".join(lines)


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _plan_pages(wiki: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Return ``(page plans, read errors)`` for every removed-kind page.

    A plan carries the source path, the destination path, and one of three
    actions: ``moved`` (relocated into ``wiki/concepts/``), ``retyped``
    (already there, frontmatter only), ``collision`` (the destination
    filename is taken, so the page is retyped where it stands).
    """
    concepts = wiki / TARGET_FOLDER
    plans: list[dict[str, Any]] = []
    errors: list[str] = []
    claimed: set[Path] = set()
    for path in sorted(wiki.rglob("*.md")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"{_relative(path, wiki)}: {exc}")
            continue
        kind = page_kind(text)
        if kind not in REMOVED_KINDS:
            continue
        dest = concepts / path.name
        if path.parent == concepts:
            action, dest = "retyped", path
        elif dest.exists() or dest in claimed:
            action, dest = "collision", path
        else:
            action = "moved"
            claimed.add(dest)
        plans.append(
            {
                "action": action,
                "kind": kind,
                "path": path,
                "dest": dest,
                "text": retype_text(text),
                "from": _relative(path, wiki),
                "to": _relative(dest, wiki),
            }
        )
    return plans, errors


def _apply_page(plan: dict[str, Any]) -> None:
    path: Path = plan["path"]
    dest: Path = plan["dest"]
    path.write_text(plan["text"], encoding="utf-8")
    if dest != path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        path.rename(dest)


def _leftovers(
    folder: Path, plans: list[dict[str, Any]], *, dry_run: bool
) -> list[str]:
    """Return the entries that would remain in ``folder`` after the pass.

    On a dry run nothing has moved yet, so the entries this run would take
    away — relocated pages and the folder's ``_context.md`` — are subtracted
    on paper to predict the real outcome.
    """
    if not folder.is_dir():
        return []
    pending_moves = (
        {p["path"] for p in plans if p["action"] == "moved"} if dry_run else set()
    )
    pending_context = {folder / CONTEXT_FILE} if dry_run else set()
    return sorted(
        entry.name
        for entry in folder.iterdir()
        if entry not in pending_moves and entry not in pending_context
    )


def _prune_index_links(index_path: Path, folders: list[str]) -> list[str]:
    """Drop ``index.md`` bullets pointing into folders the pass deleted.

    ``reindex`` reconciles a section against the folder that backs it, so it
    has nothing to reconcile once the folder is gone and leaves the section
    behind as dead links — an ``index_sync`` error. Only bullets under a
    folder this run actually pruned are removed, and a section is dropped
    only when removing its bullets leaves it with no content at all, so
    hand-written prose survives. The catalog is otherwise left to
    :func:`~llmwiki.reindex.reindex_wiki`, which runs straight afterwards.
    """
    if not folders or not index_path.is_file():
        return []
    prefixes = tuple(f"{name}/" for name in folders)
    original = index_path.read_text(encoding="utf-8")
    out: list[str] = []
    dropped: list[str] = []
    heading_at: int | None = None
    heading_hit = False

    def close_section() -> None:
        nonlocal heading_at, heading_hit
        if heading_at is not None and heading_hit:
            if not any(line.strip() for line in out[heading_at + 1:]):
                del out[heading_at:]
        heading_at, heading_hit = None, False

    for line in original.splitlines():
        if line.startswith("## "):
            close_section()
            heading_at = len(out)
            out.append(line)
            continue
        match = _INDEX_BULLET.match(line)
        if match and match.group(1).lstrip("./").startswith(prefixes):
            dropped.append(match.group(1))
            heading_hit = True
            continue
        out.append(line)
    close_section()

    if dropped:
        text = "\n".join(out)
        if original.endswith("\n"):
            text += "\n"
        index_path.write_text(text, encoding="utf-8")
    return dropped


def run_migration(*, vault: Path, dry_run: bool = False) -> dict[str, Any]:
    """Retype and relocate removed-kind pages under ``vault/wiki``.

    Returns a report dict; ``changed`` is ``False`` for a vault that carries
    no removed-kind page, no stale ``_context.md``, and no removed folder.
    """
    vault = Path(vault).expanduser().resolve()
    wiki = vault / "wiki"
    report: dict[str, Any] = {
        "vault": str(vault),
        "wiki_dir": str(wiki),
        "dry_run": dry_run,
        "moved": 0,
        "retyped": 0,
        "collisions": 0,
        "pages": [],
        "contexts_removed": [],
        "folders_removed": [],
        "folders_kept": [],
        "index_links_pruned": [],
        "errors": [],
        "changed": False,
    }
    if not wiki.is_dir():
        report["errors"].append(f"missing wiki dir: {wiki}")
        return report

    plans, read_errors = _plan_pages(wiki)
    report["errors"].extend(read_errors)
    for plan in plans:
        report[_COUNTER[plan["action"]]] += 1
        report["pages"].append(
            {k: plan[k] for k in ("action", "kind", "from", "to")}
        )
        if not dry_run:
            try:
                _apply_page(plan)
            except OSError as exc:
                report["errors"].append(f"{plan['from']}: {exc}")

    for folder_name in REMOVED_FOLDERS:
        folder = wiki / folder_name
        if not folder.is_dir():
            continue
        context = folder / CONTEXT_FILE
        if context.is_file():
            report["contexts_removed"].append(_relative(context, wiki))
            if not dry_run:
                try:
                    context.unlink()
                except OSError as exc:
                    report["errors"].append(f"{_relative(context, wiki)}: {exc}")
        leftovers = _leftovers(folder, plans, dry_run=dry_run)
        if leftovers:
            report["folders_kept"].append(
                {"folder": folder_name, "entries": leftovers}
            )
            continue
        report["folders_removed"].append(folder_name)
        if not dry_run:
            try:
                folder.rmdir()
            except OSError as exc:
                report["errors"].append(f"{folder_name}: {exc}")

    report["changed"] = bool(
        report["pages"] or report["contexts_removed"] or report["folders_removed"]
    )
    if report["changed"] and not dry_run:
        # Reconcile the catalog only for a vault that keeps one — seeding a
        # fresh index.md here would hand the user a section pointing at an
        # overview page they never wrote.
        if (wiki / "index.md").is_file():
            try:
                report["index_links_pruned"] = _prune_index_links(
                    wiki / "index.md", report["folders_removed"]
                )
                _rebuild_index(wiki)
            except (OSError, ValueError, RuntimeError) as exc:
                report["errors"].append(f"index rebuild: {exc}")
        _append_log("page kinds", log_path=wiki / "log.md", operation="migrate")
    return report


def print_report(report: dict[str, Any]) -> None:
    """Print a per-file report. A vault with nothing to do stays quiet."""
    if not report["changed"] and not report["errors"]:
        print("nothing to migrate: no page carries a removed kind")
        return
    print(f"vault:            {report['vault']}")
    print(f"wiki:             {report['wiki_dir']}")
    print(f"dry_run:          {report['dry_run']}")
    print(f"moved:            {report['moved']}")
    print(f"retyped:          {report['retyped']}")
    print(f"collisions:       {report['collisions']}")
    for page in report["pages"]:
        if page["action"] == "moved":
            print(f"  {page['kind']} → concept  {page['from']} → {page['to']}")
        elif page["action"] == "retyped":
            print(f"  {page['kind']} → concept  {page['from']}")
        else:
            print(
                f"  ! {page['from']}: concepts/ already holds that filename — "
                f"retyped in place, move it yourself"
            )
    for rel in report["contexts_removed"]:
        print(f"  deleted           {rel}")
    for name in report["folders_removed"]:
        print(f"  pruned            {name}/")
    for href in report["index_links_pruned"]:
        print(f"  unlisted          index.md → {href}")
    for kept in report["folders_kept"]:
        entries = ", ".join(kept["entries"][:10])
        more = "" if len(kept["entries"]) <= 10 else f" … +{len(kept['entries']) - 10} more"
        print(f"  kept              {kept['folder']}/ still holds: {entries}{more}")
    if report["errors"]:
        print(f"errors:           {len(report['errors'])}")
        for err in report["errors"][:10]:
            print(f"  ! {err}")
    print(
        "note: inbound [[wikilinks]] resolve by filename, so no referring page "
        "needed editing. Run `llmwiki build --vault …` afterwards so site/ "
        "picks up the new locations."
    )
