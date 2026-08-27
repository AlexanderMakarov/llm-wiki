"""Remap or clear broken ``source_file`` / ``sources:`` hops to missing raw sessions (#180).

After Cursor CLI re-syncs that used ``sessionId: store``, force-convert can leave
wiki pages pointing at deleted ``raw/sessions/…`` paths while newer raw files
exist under the same project slug. This offline migration:

* remaps a missing ``source_file`` only to a same-calendar-day interactive
  (or legacy unmarked) raw file under the same project slug — never across
  days, never to explicit ``is_headless: true``;
* when several eligible same-day candidates remain, remaps to the uniquely
  closest HH-MM;
* otherwise clears the broken ``source_file`` (and drops matching ``sources:``
  list aliases) — including ambiguous same-day pools — rather than leaving a
  provenance lint error.

Never deletes wiki pages. ``raw/`` is never written.

Usage::

    llmwiki migrate-broken-provenance --vault /path/to/vault --dry-run
    llmwiki migrate-broken-provenance --vault /path/to/vault
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.candidates import parse_sources_field

_CONTEXT_FILE = "_context.md"
_FENCE = re.compile(r"^---[ \t]*$")
_SOURCE_FILE_LINE = re.compile(r"^source_file:[ \t]*.*$")
_SOURCES_LINE = re.compile(r"^sources:[ \t]*.*$")
_DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})T")
# Cursor CLI project slugs: cursor-<12 hex of workspace hash>
_CURSOR_PROJECT = re.compile(r"(cursor-[a-f0-9]{12})", re.IGNORECASE)
_RAW_SESSIONS_PREFIX = "raw/sessions/"


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _normalize_source_file(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip().strip("\"'")
    return text or None


def _is_headless_true(meta: dict[str, Any]) -> bool:
    """True only when frontmatter explicitly marks the session headless."""
    raw = meta.get("is_headless")
    if isinstance(raw, bool):
        return raw is True
    if isinstance(raw, str):
        return raw.strip().lower() in ("true", "yes", "1")
    return False


def _is_remap_eligible(meta: dict[str, Any]) -> bool:
    """Interactive or legacy unmarked — matches synth eligibility for missing flags."""
    return not _is_headless_true(meta)


def _project_slug_from_missing(rel: str) -> str | None:
    """Best-effort project slug from a missing ``raw/sessions/…`` path."""
    name = Path(rel).name
    m = _CURSOR_PROJECT.search(name)
    if m:
        return m.group(1).lower()
    # Generic: YYYY-MM-DDTHH-MM-<project>-<slug>.md — take the segment after
    # the datetime when frontmatter is unavailable (file missing).
    dm = _DATE_PREFIX.match(name)
    if not dm:
        return None
    rest = name[dm.end() :]
    if rest.endswith(".md"):
        rest = rest[:-3]
    # Drop trailing --disambig hash if present.
    rest = re.sub(r"--[a-f0-9]{6,}$", "", rest, flags=re.IGNORECASE)
    # Prefer everything before the final ``-<slug>`` when the slug looks short.
    parts = rest.rsplit("-", 1)
    if len(parts) == 2 and parts[0]:
        return parts[0]
    return rest or None


def _date_from_missing(rel: str) -> str | None:
    name = Path(rel).name
    m = _DATE_PREFIX.match(name)
    return m.group(1) if m else None


_TIME_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})")


def _minutes_from_name(name: str) -> int | None:
    """Minutes since midnight from a ``YYYY-MM-DDTHH-MM-…`` session filename."""
    m = _TIME_PREFIX.match(name)
    if not m:
        return None
    return int(m.group(2)) * 60 + int(m.group(3))


def _closest_by_clock(
    pool: list[Path],
    *,
    target_minutes: int | None,
) -> Path | None:
    """Pick the uniquely closest same-day file by HH-MM, if any."""
    if target_minutes is None or not pool:
        return None
    scored: list[tuple[int, Path]] = []
    for path in pool:
        mins = _minutes_from_name(path.name)
        if mins is None:
            continue
        scored.append((abs(mins - target_minutes), path))
    if not scored:
        return None
    scored.sort(key=lambda item: (item[0], item[1].name))
    if len(scored) == 1 or scored[0][0] < scored[1][0]:
        return scored[0][1]
    return None


def _index_raw_sessions(sessions_root: Path) -> list[Path]:
    if not sessions_root.is_dir():
        return []
    return sorted(p for p in sessions_root.rglob("*.md") if p.is_file())


def _candidates_for_project(
    files: list[Path],
    project_slug: str,
) -> list[Path]:
    needle = project_slug.casefold()
    return [p for p in files if needle in p.name.casefold()]


def _remap_eligible_paths(pool: list[Path]) -> list[Path]:
    out: list[Path] = []
    for path in pool:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        meta, _body = parse_frontmatter(text)
        if _is_remap_eligible(meta if isinstance(meta, dict) else {}):
            out.append(path)
    return out


def _pick_remap_target(
    candidates: list[Path],
    *,
    date_prefix: str | None,
    missing_rel: str | None = None,
) -> tuple[Path | None, str]:
    """Return ``(path, outcome)`` where outcome is remap|unresolved|clear.

    Never remaps across calendar days. When ``date_prefix`` is set and no
    same-day raw exists, return ``clear`` (do not fall back to other dates —
    that falsely pointed every June stub at a single January session).
    Same-day remap shortlist is interactive or legacy unmarked (never
    explicit headless). Ambiguous closest-time ties → ``unresolved``.
    """
    if not candidates:
        return None, "clear"

    if date_prefix:
        pool = [p for p in candidates if p.name.startswith(date_prefix)]
        if not pool:
            return None, "clear"
    else:
        pool = candidates

    shortlist = _remap_eligible_paths(pool)
    target_minutes = (
        _minutes_from_name(Path(missing_rel).name) if missing_rel else None
    )
    # Explicit headless-only days clear — those rows would be dropped under
    # ``exclude_headless``. Unmarked legacy stays eligible (synth parity).
    if not shortlist:
        return None, "clear"
    if len(shortlist) == 1:
        return shortlist[0], "remap"
    pick = _closest_by_clock(shortlist, target_minutes=target_minutes)
    if pick is not None:
        return pick, "remap"
    return None, "unresolved"


def _sources_aliases_for_missing(missing_rel: str) -> set[str]:
    """Values that may appear in ``sources:`` referring to the missing raw."""
    aliases: set[str] = {missing_rel, missing_rel.replace("\\", "/")}
    name = Path(missing_rel).name
    stem = Path(missing_rel).stem
    aliases.add(name)
    aliases.add(stem)
    # Drop --disambig from stem for aliasing.
    aliases.add(re.sub(r"--[a-f0-9]{6,}$", "", stem, flags=re.IGNORECASE))
    if missing_rel.startswith(_RAW_SESSIONS_PREFIX):
        aliases.add(missing_rel[len(_RAW_SESSIONS_PREFIX) :])
    return {a for a in aliases if a}


def _rewrite_source_file_line(text: str, new_value: str | None) -> str:
    """Set or remove the frontmatter ``source_file:`` line; preserve endings."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return text
    out: list[str] = [lines[0]]
    found = False
    for i, line in enumerate(lines[1:], start=1):
        stripped = line.rstrip("\r\n")
        ending = line[len(stripped) :]
        if _FENCE.match(stripped):
            if not found and new_value is not None:
                out.append(f"source_file: {new_value}{ending}")
            out.extend(lines[i:])
            return "".join(out)
        if _SOURCE_FILE_LINE.match(stripped):
            found = True
            if new_value is None:
                continue  # drop the line
            out.append(f"source_file: {new_value}{ending}")
            continue
        out.append(line)
    return text


def _rewrite_sources_line(text: str, drop: set[str]) -> str:
    """Remove matching entries from frontmatter ``sources:``; drop empty list."""
    if not drop:
        return text
    drop_cf = {d.casefold() for d in drop}
    meta, _body = parse_frontmatter(text)
    existing = parse_sources_field(meta.get("sources"))
    if not existing:
        return text
    kept = [s for s in existing if s.casefold() not in drop_cf]
    if kept == existing:
        return text

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return text
    out: list[str] = [lines[0]]
    for i, line in enumerate(lines[1:], start=1):
        stripped = line.rstrip("\r\n")
        ending = line[len(stripped) :]
        if _FENCE.match(stripped):
            out.extend(lines[i:])
            return "".join(out)
        if _SOURCES_LINE.match(stripped):
            if not kept:
                continue  # remove empty sources:
            out.append(f"sources: [{', '.join(kept)}]{ending}")
            continue
        out.append(line)
    return text


def _vault_rel_raw(path: Path, vault: Path) -> str:
    return path.resolve().relative_to(vault.resolve()).as_posix()


def run_migration(*, vault: Path, dry_run: bool = False) -> dict[str, Any]:
    """Remap or clear broken raw-session provenance under ``vault/wiki``."""
    vault = Path(vault).expanduser().resolve()
    wiki = vault / "wiki"
    sessions_root = vault / "raw" / "sessions"
    report: dict[str, Any] = {
        "vault": str(vault),
        "wiki_dir": str(wiki),
        "dry_run": dry_run,
        "remapped": 0,
        "cleared": 0,
        "unresolved": 0,
        "sources_entries_dropped": 0,
        "pages_touched": 0,
        "errors": [],
        "details": [],
        "changed": False,
    }
    if not wiki.is_dir():
        report["errors"].append(f"missing wiki dir: {wiki}")
        return report

    raw_files = _index_raw_sessions(sessions_root)
    # Track cleared missing paths so a second pass can drop sources: aliases.
    cleared_missing: set[str] = set()

    for path in sorted(wiki.rglob("*.md")):
        if not path.is_file() or path.name == _CONTEXT_FILE:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            report["errors"].append(f"{_relative(path, vault)}: {exc}")
            continue

        meta, _body = parse_frontmatter(text)
        if not isinstance(meta, dict):
            meta = {}
        source_file = _normalize_source_file(meta.get("source_file"))
        new_text = text
        page_detail: dict[str, Any] | None = None

        if source_file and source_file.replace("\\", "/").startswith(
            _RAW_SESSIONS_PREFIX
        ):
            target = vault / source_file
            if not target.is_file():
                project = _project_slug_from_missing(source_file)
                date_prefix = _date_from_missing(source_file)
                candidates = (
                    _candidates_for_project(raw_files, project) if project else []
                )
                pick, outcome = _pick_remap_target(
                    candidates,
                    date_prefix=date_prefix,
                    missing_rel=source_file,
                )
                if outcome == "remap" and pick is not None:
                    new_rel = _vault_rel_raw(pick, vault)
                    new_text = _rewrite_source_file_line(new_text, new_rel)
                    report["remapped"] += 1
                    page_detail = {
                        "wiki_path": _relative(path, vault),
                        "action": "remap",
                        "from": source_file,
                        "to": new_rel,
                    }
                elif outcome == "clear":
                    new_text = _rewrite_source_file_line(new_text, None)
                    cleared_missing.add(source_file.replace("\\", "/"))
                    report["cleared"] += 1
                    page_detail = {
                        "wiki_path": _relative(path, vault),
                        "action": "clear",
                        "from": source_file,
                    }
                else:
                    # Ambiguous same-day pool: clear rather than leave a
                    # provenance_integrity error (wrong remap is worse).
                    new_text = _rewrite_source_file_line(new_text, None)
                    cleared_missing.add(source_file.replace("\\", "/"))
                    report["unresolved"] += 1
                    report["cleared"] += 1
                    page_detail = {
                        "wiki_path": _relative(path, vault),
                        "action": "clear-ambiguous",
                        "from": source_file,
                        "candidates": len(candidates),
                        "same_day": len(
                            [
                                p
                                for p in candidates
                                if date_prefix and p.name.startswith(date_prefix)
                            ]
                        ),
                    }

        if new_text != text:
            report["pages_touched"] += 1
            if not dry_run:
                try:
                    path.write_text(new_text, encoding="utf-8")
                except OSError as exc:
                    report["errors"].append(f"{_relative(path, vault)}: {exc}")
                    continue
            if page_detail is not None:
                report["details"].append(page_detail)
        elif page_detail is not None:
            report["details"].append(page_detail)

    # Second pass: drop ``sources:`` aliases that named a cleared missing raw.
    if cleared_missing:
        drop_aliases: set[str] = set()
        for missing in cleared_missing:
            drop_aliases |= _sources_aliases_for_missing(missing)
        for path in sorted(wiki.rglob("*.md")):
            if not path.is_file() or path.name == _CONTEXT_FILE:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            before = parse_sources_field(parse_frontmatter(text)[0].get("sources"))
            if not before:
                continue
            new_text = _rewrite_sources_line(text, drop_aliases)
            after = parse_sources_field(parse_frontmatter(new_text)[0].get("sources"))
            dropped = len(before) - len(after)
            if dropped <= 0 or new_text == text:
                continue
            report["sources_entries_dropped"] += dropped
            report["pages_touched"] += 1
            report["details"].append(
                {
                    "wiki_path": _relative(path, vault),
                    "action": "sources_trim",
                    "dropped": dropped,
                }
            )
            if not dry_run:
                try:
                    path.write_text(new_text, encoding="utf-8")
                except OSError as exc:
                    report["errors"].append(f"{_relative(path, vault)}: {exc}")

    report["changed"] = bool(
        report["remapped"]
        or report["cleared"]
        or report["sources_entries_dropped"]
        or report["pages_touched"]
    )
    return report


def print_report(report: dict[str, Any]) -> None:
    """Print an operator-facing summary."""
    if not report["changed"] and not report["errors"] and report["unresolved"] == 0:
        print("nothing to migrate: no broken raw/sessions provenance hops found")
        return
    print(f"vault:                  {report['vault']}")
    print(f"wiki:                   {report['wiki_dir']}")
    print(f"dry_run:                {report['dry_run']}")
    print(f"remapped:               {report['remapped']}")
    print(f"cleared:                {report['cleared']}")
    print(f"unresolved:             {report['unresolved']}")
    print(f"sources entries dropped:{report['sources_entries_dropped']}")
    print(f"pages touched:          {report['pages_touched']}")
    for detail in report["details"][:30]:
        action = detail.get("action")
        loc = detail.get("wiki_path")
        if action == "remap":
            print(f"  remap  {loc}: {detail.get('from')} → {detail.get('to')}")
        elif action in ("clear", "clear-ambiguous"):
            label = "clear-ambiguous" if action == "clear-ambiguous" else "clear"
            print(f"  {label}  {loc}: {detail.get('from')}")
        elif action == "unresolved":
            print(
                f"  unresolved  {loc}: {detail.get('from')} "
                f"({detail.get('candidates')} candidates)"
            )
        elif action == "sources_trim":
            print(f"  sources_trim  {loc}")
    if len(report["details"]) > 30:
        print(f"  … +{len(report['details']) - 30} more")
    if report["errors"]:
        print(f"errors:                 {len(report['errors'])}")
        for err in report["errors"][:10]:
            print(f"  ! {err}")
