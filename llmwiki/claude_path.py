"""Resolve and validate the ``claude`` CLI binary path (#421).

Extracted from ``build.py`` so synth backends and ``add_doc`` can reuse the
hardened PATH / shell-metachar checks without importing the HTML builder
(#58 PLC0415).
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

_PATH_SHELL_METACHARS = re.compile(r"[;&|`$<>\n\r\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def resolve_claude_path(claude_path: str | None) -> Path | None:
    """Resolve and validate the ``--claude`` path (#421).

    Returns ``None`` when:
      - The path is empty or contains shell metacharacters (rejected loudly).
      - ``shutil.which`` can't find the binary on PATH (when no path passed).
      - The resolved path doesn't exist on disk.

    Returns a ``Path`` when the binary is found and looks safe. Callers
    should treat ``None`` as "skip synthesis" — the synth step is best-
    effort and never fatal.
    """
    if claude_path:
        # Reject explicit paths containing shell metacharacters even
        # though argv is list-form — this keeps the path safe to log.
        if _PATH_SHELL_METACHARS.search(claude_path):
            print(
                f"  warning: refusing claude path with shell metacharacters: "
                f"{claude_path!r}",
                file=sys.stderr,
            )
            return None
        candidate = Path(claude_path)
    else:
        # No explicit path: use shutil.which so PATH-based lookups
        # (homebrew, asdf, npm-global, Windows %PATH%) all just work.
        found = shutil.which("claude")
        if not found:
            return None
        candidate = Path(found)
    if not candidate.exists():
        print(f"  warning: claude CLI not found at {candidate}", file=sys.stderr)
        return None
    return candidate


# Back-compat alias — tests and older call sites used the private name.
_resolve_claude_path = resolve_claude_path
