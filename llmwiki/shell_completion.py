"""One-line shell TAB completion for the ``llmwiki`` entry point (#294).

The line is plain shell text with the top-level command names written in as
literals, so no Python runs at shell startup or at TAB time. ``setup.sh``
writes it into the user's rc file through :func:`install_rc_line`, and the
docs drift test checks that ``docs/getting-started.md`` shows exactly the
line :func:`completion_line` produces.
"""

from __future__ import annotations

import argparse
import os
import stat
import tempfile
from pathlib import Path
from typing import Literal

from llmwiki.cli import build_parser

Shell = Literal["bash", "zsh"]
InstallResult = Literal["added", "updated", "unchanged"]

MARKER = "# llmwiki-completion"


def command_names() -> list[str]:
    """Return the top-level llmwiki command names in registration order."""
    for action in build_parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            return list(action.choices)
    return []


def completion_line(shell: Shell) -> str:
    """Return the one-line completion snippet for *shell*, ending in :data:`MARKER`."""
    names = " ".join(command_names())
    if shell == "bash":
        return (
            "_llmwiki_complete() { COMPREPLY=(); "
            'if [ "$COMP_CWORD" -eq 1 ]; then '
            f'COMPREPLY=($(compgen -W "{names}" -- "${{COMP_WORDS[1]}}")); fi; }}; '
            f"complete -o default -F _llmwiki_complete llmwiki {MARKER}"
        )
    if shell == "zsh":
        return (
            "(( $+functions[compdef] )) || { autoload -Uz compinit && compinit; }; "
            f"_llmwiki_complete() {{ _arguments '1:command:({names})' '*::arg:_files'; }}; "
            f"compdef _llmwiki_complete llmwiki {MARKER}"
        )
    raise ValueError(f"unsupported shell: {shell!r}")


def _new_file_mode() -> int:
    """Return the mode a plain ``open(..., "w")`` would give a new file under the current umask."""
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


def install_rc_line(rc: Path, shell: Shell) -> InstallResult:
    """Write the current completion line into the rc file *rc*.

    Every existing line containing :data:`MARKER` is dropped and the current
    line is appended; all other bytes stay as they were, including bytes that
    are not valid UTF-8. The file is created when missing. The new content is
    written to a temp file next to the resolved target and moved into place
    with ``os.replace``, so a failed write never truncates the rc file and a
    symlinked rc stays a symlink. Returns ``"added"`` when no marker line
    existed, ``"unchanged"`` when the file already ended in exactly the
    current line with no other marker line, and ``"updated"`` otherwise.
    """
    line = completion_line(shell)
    target = rc.resolve()
    exists = target.exists()
    old = target.read_bytes().decode("utf-8", errors="surrogateescape") if exists else ""
    kept = [ln for ln in old.splitlines(keepends=True) if MARKER not in ln]
    had_marker = len(kept) != len(old.splitlines(keepends=True))
    body = "".join(kept)
    if body and not body.endswith("\n"):
        body += "\n"
    new = body + line + "\n"
    if new == old:
        return "unchanged"
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(new.encode("utf-8", errors="surrogateescape"))
        os.chmod(tmp, stat.S_IMODE(target.stat().st_mode) if exists else _new_file_mode())
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return "updated" if had_marker else "added"
