"""Acceptance tests for #294: shell TAB completion for llmwiki commands.

# @layer: e2e
# @spec: 294-shell-tab-completion
# @regression

``tests/test_shell_completion.py`` already covers, at unit/slice level:
command_names() vs. the real parser; COMPREPLY contents for a narrowing
prefix, an empty word, and after a command word; the bash line's
registration with ``complete -p``; a zsh ``-n`` parse smoke test; both
lines appearing verbatim in the docs; every ``install_rc_line`` case
(missing file, byte-preserved content, idempotent re-run, stale-line
replacement); and the ``setup.sh`` step for yes / Enter+rerun / no /
non-TTY / skip-var / unsupported-shell.

This module adds only what functional-spec.md asks for that isn't
exercised end-to-end yet:

- FR1's third bullet literally: a real interactive bash session, typing
  ``llmwiki bui<TAB>``, ends up with the line ``llmwiki build `` (the
  single-match auto-insert-plus-trailing-space behaviour of bash's own
  readline, not just that ``COMPREPLY`` contains one element).
- FR2's drift guarantee: a command added to the parser without updating
  the docs would make the drift check (test_docs_show_current_line) fail
  — proving the automated check actually discriminates, not just that it
  currently passes.
- FR4 end-to-end: a stale rc line written for an older, smaller command
  list gets refreshed to the current list on the next ``install_rc_line``
  run, the refreshed line lets bash actually complete the newly-added
  command, and every other byte of the rc file is untouched.
"""

from __future__ import annotations

import os
import select
import subprocess
import time
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from llmwiki import shell_completion as sc
from llmwiki.shell_completion import MARKER, command_names, completion_line, install_rc_line

GETTING_STARTED = REPO_ROOT / "docs" / "getting-started.md"


PROMPT = b"TESTPROMPT$ "
HANG_GUARD_SECONDS = 10.0


def _read_until(master_fd: int, expected: bytes) -> bytes:
    """Read from a pty master until *expected* appears, and return everything read.

    Returns as soon as *expected* shows up. The deadline only guards against a
    hang; when it is hit the caller's output assertion reports the failure.
    """
    data = b""
    deadline = time.monotonic() + HANG_GUARD_SECONDS
    while expected not in data:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        ready, _, _ = select.select([master_fd], [], [], remaining)
        if not ready:
            break
        try:
            chunk = os.read(master_fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        data += chunk
    return data


@pytest.fixture
def bash_pty(tmp_path: Path):
    """Spawn a real interactive bash on a pty, cleaned up on teardown."""
    master_fd, slave_fd = os.openpty()
    env = dict(os.environ)
    env.update(HOME=str(tmp_path), TERM="xterm", PS1="TESTPROMPT$ ")
    proc = subprocess.Popen(
        ["bash", "--noprofile", "--norc", "-i"],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=env,
        start_new_session=True,
    )
    os.close(slave_fd)
    assert PROMPT in _read_until(master_fd, PROMPT), "interactive bash never printed its prompt"
    try:
        yield master_fd
    finally:
        proc.kill()  # an interactive bash ignores SIGTERM
        proc.wait()
        os.close(master_fd)


def test_single_match_prefix_autocompletes_with_trailing_space(bash_pty):
    """FR1: ``llmwiki bui`` + TAB becomes the line ``llmwiki build `` in a real shell."""
    master_fd = bash_pty
    os.write(master_fd, (completion_line("bash") + "\n").encode())
    assert PROMPT in _read_until(master_fd, PROMPT), "bash never returned to the prompt"

    os.write(master_fd, b"llmwiki bui\t")
    out = _read_until(master_fd, b"llmwiki build ")

    assert b"llmwiki build " in out


def test_docs_drift_check_catches_a_command_added_without_doc_update(monkeypatch):
    """FR2: the automated check fails when a command exists but the docs weren't updated."""
    current = command_names()
    monkeypatch.setattr(sc, "command_names", lambda: [*current, "zzz-not-a-real-command"])

    docs_text = GETTING_STARTED.read_text(encoding="utf-8")
    for shell in ("bash", "zsh"):
        assert sc.completion_line(shell) not in docs_text


def test_stale_command_list_refreshes_and_new_command_completes(tmp_path, monkeypatch):
    """FR4: a stale line (older, smaller command set) refreshes to the current one.

    Covers both remaining FR4 bullets together: after refresh the newly
    present command actually completes in bash, and every other byte of the
    rc file is left exactly as it was.
    """
    full_names = command_names()
    assert len(full_names) >= 2
    new_command = full_names[-1]
    old_names = [n for n in full_names if n != new_command]

    rc = tmp_path / ".bashrc"
    rc.write_text("export KEEP=1\nalias ll='ls -l'\n", encoding="utf-8")

    with monkeypatch.context() as m:
        m.setattr(sc, "command_names", lambda: old_names)
        assert install_rc_line(rc, "bash") == "added"
    stale_text = rc.read_text(encoding="utf-8")
    assert new_command not in stale_text
    assert stale_text.count(MARKER) == 1

    assert install_rc_line(rc, "bash") == "updated"
    refreshed_text = rc.read_text(encoding="utf-8")
    assert refreshed_text.count(MARKER) == 1
    assert refreshed_text == f"export KEEP=1\nalias ll='ls -l'\n{completion_line('bash')}\n"

    words = ["llmwiki", new_command[: max(1, len(new_command) - 2)]]
    script = (
        f"{completion_line('bash')}\n"
        f"COMP_WORDS=('{words[0]}' '{words[1]}'); COMP_CWORD=1; _llmwiki_complete\n"
        'printf "%s\\n" "${COMPREPLY[@]}"\n'
    )
    out = subprocess.run(
        ["bash", "--norc", "--noprofile", "-c", script],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert new_command in [ln for ln in out.splitlines() if ln]
