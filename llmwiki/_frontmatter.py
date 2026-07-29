"""Canonical frontmatter parser (#273).

Historically 8 copies of this function lived scattered across the
codebase with slightly different return shapes — dict vs
``(dict, body)`` tuple vs ``(str | None, body)``.  Consolidating in
one hit is risky (every caller makes specific assumptions about the
return shape), so this module ships the canonical implementation plus
thin wrappers that match the three existing signatures.  New call
sites should use :func:`parse_frontmatter` or
:func:`parse_frontmatter_dict`; legacy sites can migrate over time.

Stdlib-only.  No YAML dependency — we parse the minimal subset of
YAML we use in practice (scalars, inline lists, inline dicts, block
lists with `- ` bullets).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Accept LF, CRLF, or CR after each fence so Windows-authored (CRLF) and
# old-Mac (CR) files parse identically to LF input. The optional newline
# slots match the historical regex (`\n?(.*?)\n?---\n?`) so empty
# frontmatter (`---\n---\nbody`) still parses. BOM is handled separately
# in `_strip_bom()` before the regex runs. See #409, #423.
_FRONTMATTER_RE = re.compile(
    r"^---[ \t]*(?:\r\n|\r|\n)?(.*?)(?:\r\n|\r|\n)?---[ \t]*(?:\r\n|\r|\n)?(.*)$",
    re.DOTALL,
)


def _strip_bom(text: str) -> str:
    """Strip leading UTF-8 BOM if present (#423)."""
    if text and text[0] == "\ufeff":
        return text[1:]
    return text


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return ``(meta, body)`` — the canonical shape.

    Empty or malformed input returns ``({}, text)`` so callers can
    treat every file uniformly. Handles UTF-8 BOM and CR/LF/CRLF
    line endings transparently.
    """
    text = _strip_bom(text)
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta_text = m.group(1)
    body = m.group(2)
    meta: dict[str, Any] = {}
    for line in meta_text.splitlines():
        mm = re.match(r"^([a-zA-Z_][\w-]*):\s*(.*)$", line)
        if not mm:
            continue
        key, raw = mm.group(1), mm.group(2).strip()
        meta[key] = _parse_scalar(raw)
    return meta, body


def is_subagent(meta: dict[str, Any], path: Path) -> bool:
    """Return True iff a session is a sub-agent run (#406 / #492 / #30).

    Prefers the adapter-written ``is_subagent`` frontmatter field (canonical
    contract since #406), accepting it as a real bool or one of the
    case-insensitive strings ``"true"``/``"false"`` since frontmatter parsers
    historically coerced inconsistently. Falls back to the legacy
    ``"subagent" in path.name`` substring check ONLY when the field is missing
    — needed to keep pre-#406 raw files (no field) classified correctly until
    they're re-synced. The renderer renames sub-agent slugs to
    ``<slug>-subagent-<id>``, so the substring match is correct on canonically
    renamed files even when meta is absent.

    Single source of truth for both ``build`` (HTML session counts) and the
    synth pipeline (``include_subagents`` backlog policy).
    """
    raw = meta.get("is_subagent")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("true", "yes", "1"):
            return True
        if s in ("false", "no", "0"):
            return False
    return "subagent" in path.name


def is_headless(meta: dict[str, Any]) -> bool:
    """True when this session was an automated ``claude -p`` / SDK run.

    Reads the ``is_headless`` flag the converter records, tolerating the same
    string/bool spellings as :func:`is_subagent`, and falls back to the raw
    ``entrypoint`` / ``promptSource`` markers when only those were written.

    Absent every marker this returns False rather than guessing from message
    counts. Files converted before the flag existed therefore read as "not
    headless" — a deliberate choice, since silently reclassifying an old
    session as machine noise is worse than leaving it in the backlog where
    it is visible. Re-sync (or prune) to classify legacy files.

    Single source of truth for the synth pipeline's headless backlog policy.
    """
    raw = meta.get("is_headless")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("true", "yes", "1"):
            return True
        if s in ("false", "no", "0"):
            return False
    entrypoint = meta.get("entrypoint")
    if isinstance(entrypoint, str) and entrypoint.strip().lower().startswith("sdk-"):
        return True
    prompt_source = meta.get("promptSource")
    return isinstance(prompt_source, str) and prompt_source.strip().lower() == "sdk"


def parse_frontmatter_dict(text: str) -> dict[str, Any]:
    """Return just the metadata dict — convenience for callers that
    don't need the body."""
    return parse_frontmatter(text)[0]


def parse_frontmatter_or_none(text: str) -> tuple[str | None, str]:
    """Return ``(raw_frontmatter_text | None, body)`` — legacy shape
    used by ``llmwiki/tags.py`` which does its own line-level parsing
    inside the frontmatter block."""
    text = _strip_bom(text)
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    return m.group(1), m.group(2)


def _parse_scalar(raw: str, *, coerce_bool: bool = True) -> Any:
    """Parse a single YAML scalar value (best-effort, no external deps).

    Handles: inline lists ``[a, b, c]``, quoted strings, bools, ints.
    Everything else comes back as the stripped string.

    #py-l1 (#599): pass ``coerce_bool=False`` when recursing into list
    items so a tag list like ``[no, yes, maybe]`` doesn't become
    ``[False, True, "maybe"]``. Top-level scalars still coerce.
    """
    s = raw.strip()
    if not s:
        return ""
    # Quoted string
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    # Inline list: [a, b, c]
    if s.startswith("[") and s.endswith("]"):
        body = s[1:-1].strip()
        if not body:
            return []
        return [_parse_scalar(x, coerce_bool=False) for x in body.split(",")]
    # Bool
    low = s.lower()
    if coerce_bool and low in {"true", "yes"}:
        return True
    if coerce_bool and low in {"false", "no"}:
        return False
    # Int
    try:
        return int(s)
    except ValueError:
        pass
    # Float
    try:
        return float(s)
    except ValueError:
        pass
    return s
