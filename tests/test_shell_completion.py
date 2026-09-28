"""Tests for the one-line shell TAB completion and its setup.sh step (#294)."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from llmwiki.cli import build_parser
from llmwiki.shell_completion import MARKER, command_names, completion_line, install_rc_line

GETTING_STARTED = REPO_ROOT / "docs" / "getting-started.md"
SETUP_STEP = REPO_ROOT / "scripts" / "setup-completion.sh"


def _root_choices() -> list[str]:
    parser = build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return list(sub.choices)


def _bash_complete(words: list[str], cword: int) -> list[str]:
    array = " ".join(f"'{w}'" for w in words)
    script = (
        f"{completion_line('bash')}\n"
        f"COMP_WORDS=({array}); COMP_CWORD={cword}; _llmwiki_complete\n"
        'printf "%s\\n" "${COMPREPLY[@]}"\n'
    )
    out = subprocess.run(
        ["bash", "--norc", "--noprofile", "-c", script],
        capture_output=True, text=True, check=True,
    ).stdout
    return [ln for ln in out.splitlines() if ln]


# --- command_names -----------------------------------------------------------


def test_command_names_match_parser():
    names = command_names()
    assert names == _root_choices()
    assert {"sync", "synth", "migrate"} <= set(names)


def test_cli_completion_subcommand_stays_removed():
    assert "completion" not in command_names()


# --- bash behaviour ----------------------------------------------------------


def test_bash_prefix_narrows_to_matching_commands():
    assert sorted(_bash_complete(["llmwiki", "sy"], 1)) == ["sync", "synth"]


def test_bash_empty_word_lists_every_command():
    assert sorted(_bash_complete(["llmwiki", ""], 1)) == sorted(command_names())


def test_bash_after_command_offers_no_command_names():
    assert _bash_complete(["llmwiki", "sync", ""], 2) == []


def test_bash_line_is_registered_for_llmwiki():
    out = subprocess.run(
        ["bash", "--norc", "--noprofile", "-c", f"{completion_line('bash')}\ncomplete -p llmwiki"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "-o default" in out
    assert "-F _llmwiki_complete" in out


# --- zsh ---------------------------------------------------------------------


def test_zsh_line_parses():
    zsh = shutil.which("zsh")
    if zsh is None:
        pytest.skip("zsh is not installed")
    subprocess.run([zsh, "-n", "-c", completion_line("zsh")], check=True)


# --- line shape and docs drift -----------------------------------------------


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_line_is_single_line_with_marker(shell):
    line = completion_line(shell)
    assert "\n" not in line
    assert line.endswith(MARKER)
    for name in command_names():
        assert name in line


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_docs_show_current_line(shell):
    assert completion_line(shell) in GETTING_STARTED.read_text(encoding="utf-8")


# --- install_rc_line ---------------------------------------------------------


def test_install_creates_missing_file(tmp_path):
    rc = tmp_path / ".bashrc"
    assert install_rc_line(rc, "bash") == "added"
    assert rc.read_text(encoding="utf-8") == completion_line("bash") + "\n"


def test_install_preserves_other_content_byte_for_byte(tmp_path):
    rc = tmp_path / ".bashrc"
    original = b"export A=1\r\n# comment\n\nalias ll='ls -l'"
    rc.write_bytes(original)
    assert install_rc_line(rc, "bash") == "added"
    assert rc.read_bytes() == original + b"\n" + completion_line("bash").encode() + b"\n"


def test_install_twice_is_unchanged(tmp_path):
    rc = tmp_path / ".zshrc"
    rc.write_text("setopt autocd\n", encoding="utf-8")
    install_rc_line(rc, "zsh")
    before = rc.read_bytes()
    assert install_rc_line(rc, "zsh") == "unchanged"
    assert rc.read_bytes() == before
    assert rc.read_text(encoding="utf-8").count(MARKER) == 1


def test_install_replaces_stale_line(tmp_path):
    rc = tmp_path / ".bashrc"
    rc.write_text(
        f"export A=1\ncomplete -W 'sync build' llmwiki {MARKER}\nexport B=2\n",
        encoding="utf-8",
    )
    assert install_rc_line(rc, "bash") == "updated"
    assert rc.read_text(encoding="utf-8") == (
        f"export A=1\nexport B=2\n{completion_line('bash')}\n"
    )


def test_install_preserves_non_utf8_bytes(tmp_path):
    rc = tmp_path / ".bashrc"
    original = b"export NAME='caf\xe9'\n\xff\xfe raw\n"
    rc.write_bytes(original)
    assert install_rc_line(rc, "bash") == "added"
    assert rc.read_bytes() == original + completion_line("bash").encode() + b"\n"
    assert install_rc_line(rc, "bash") == "unchanged"


def test_install_through_symlink_keeps_the_link(tmp_path):
    dotfiles = tmp_path / "dotfiles"
    dotfiles.mkdir()
    target = dotfiles / "bashrc"
    target.write_text("export A=1\n", encoding="utf-8")
    rc = tmp_path / ".bashrc"
    rc.symlink_to(target)
    assert install_rc_line(rc, "bash") == "added"
    assert rc.is_symlink()
    assert rc.resolve() == target.resolve()
    assert target.read_text(encoding="utf-8") == f"export A=1\n{completion_line('bash')}\n"
    assert sorted(p.name for p in dotfiles.iterdir()) == ["bashrc"]


def test_install_preserves_file_mode(tmp_path):
    rc = tmp_path / ".zshrc"
    rc.write_text("setopt autocd\n", encoding="utf-8")
    rc.chmod(0o600)
    assert install_rc_line(rc, "zsh") == "added"
    assert stat.S_IMODE(rc.stat().st_mode) == 0o600


def test_install_failed_write_leaves_rc_and_no_temp_file(tmp_path, monkeypatch):
    rc = tmp_path / ".bashrc"
    rc.write_text("export A=1\n", encoding="utf-8")

    def fail_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk full"):
        install_rc_line(rc, "bash")
    assert rc.read_text(encoding="utf-8") == "export A=1\n"
    assert [p.name for p in tmp_path.iterdir()] == [".bashrc"]


# --- setup.sh step -----------------------------------------------------------


def _run_setup_step(
    home: Path, shell: str, answer: str, *, tty: bool, os_name: str = "Linux", **env_extra: str
):
    stub_bin = home.parent / f"{home.name}-bin"
    stub_bin.mkdir(exist_ok=True)
    uname = stub_bin / "uname"
    uname.write_text(f"#!/bin/sh\necho {os_name}\n", encoding="utf-8")
    uname.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k != "LLMWIKI_SKIP_COMPLETION"}
    env.update(
        HOME=str(home),
        SHELL=shell,
        PATH=os.pathsep.join(
            [str(stub_bin), str(Path(sys.executable).parent), os.environ.get("PATH", "")]
        ),
        **env_extra,
    )
    cmd = ["bash", "-c", f'set -eu; . "{SETUP_STEP}"; llmwiki_offer_completion']
    if not tty:
        return subprocess.run(
            cmd, cwd=REPO_ROOT, env=env, input=answer, capture_output=True, text=True, check=True
        )
    master, slave = os.openpty()
    try:
        os.write(master, answer.encode())
        return subprocess.run(
            cmd, cwd=REPO_ROOT, env=env, stdin=slave, capture_output=True, text=True, check=True
        )
    finally:
        os.close(slave)
        os.close(master)


@pytest.mark.parametrize(
    ("shell", "rc_name", "kind"),
    [("/bin/bash", ".bashrc", "bash"), ("/usr/bin/zsh", ".zshrc", "zsh")],
)
def test_setup_yes_adds_one_line(tmp_path, shell, rc_name, kind):
    result = _run_setup_step(tmp_path, shell, "y\n", tty=True)
    rc = tmp_path / rc_name
    assert f"Add llmwiki TAB completion to {rc}? [Y/n]" in result.stdout
    assert rc.read_text(encoding="utf-8") == completion_line(kind) + "\n"
    assert f"added: {rc}" in result.stdout


def test_setup_bash_on_macos_targets_bash_profile(tmp_path):
    result = _run_setup_step(tmp_path, "/bin/bash", "y\n", tty=True, os_name="Darwin")
    rc = tmp_path / ".bash_profile"
    assert f"Add llmwiki TAB completion to {rc}? [Y/n]" in result.stdout
    assert rc.read_text(encoding="utf-8") == completion_line("bash") + "\n"
    assert not (tmp_path / ".bashrc").exists()


def test_setup_zsh_on_macos_targets_zshrc(tmp_path):
    _run_setup_step(tmp_path, "/bin/zsh", "y\n", tty=True, os_name="Darwin")
    assert (tmp_path / ".zshrc").read_text(encoding="utf-8") == completion_line("zsh") + "\n"


def test_setup_enter_defaults_to_yes_and_rerun_keeps_one_line(tmp_path):
    rc = tmp_path / ".bashrc"
    rc.write_text("export A=1\n", encoding="utf-8")
    _run_setup_step(tmp_path, "/bin/bash", "\n", tty=True)
    result = _run_setup_step(tmp_path, "/bin/bash", "\n", tty=True)
    assert f"unchanged: {rc}" in result.stdout
    assert rc.read_text(encoding="utf-8") == f"export A=1\n{completion_line('bash')}\n"


def test_setup_no_leaves_rc_untouched(tmp_path):
    rc = tmp_path / ".bashrc"
    rc.write_text("export A=1\n", encoding="utf-8")
    _run_setup_step(tmp_path, "/bin/bash", "n\n", tty=True)
    assert rc.read_text(encoding="utf-8") == "export A=1\n"


def test_setup_non_tty_asks_nothing(tmp_path):
    result = _run_setup_step(tmp_path, "/bin/bash", "y\n", tty=False)
    assert "Add llmwiki TAB completion" not in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_setup_skip_variable_asks_nothing(tmp_path):
    result = _run_setup_step(tmp_path, "/bin/bash", "y\n", tty=True, LLMWIKI_SKIP_COMPLETION="1")
    assert "Add llmwiki TAB completion" not in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_setup_other_shell_prints_line_and_changes_nothing(tmp_path):
    result = _run_setup_step(tmp_path, "/bin/fish", "y\n", tty=True)
    assert "Add llmwiki TAB completion" not in result.stdout
    assert completion_line("bash") in result.stdout
    assert list(tmp_path.iterdir()) == []
