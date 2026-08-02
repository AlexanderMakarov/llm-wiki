"""Install hints must name the interpreter that is actually running llmwiki."""

from __future__ import annotations

import sys
from pathlib import Path

from llmwiki.install_hint import (
    DIST_NAME,
    PythonEnv,
    _is_uv_venv,
    detect_env,
    install_hint,
    install_target,
    python_module_command,
)

PYTHON = "/opt/env/bin/python"
ROOT = Path("/opt/checkout")


def _env(**over) -> PythonEnv:
    base = dict(executable=PYTHON, has_pip=True, uv_managed=False,
                has_uv=False, project_root=None)
    base.update(over)
    return PythonEnv(**base)


# ── installer selection ──────────────────────────────────────────────

def test_pip_hint_names_the_running_interpreter_not_bare_pip():
    # The whole point: a bare `pip` may belong to another Python.
    hint = install_hint("add", _env())
    assert hint == f"{PYTHON} -m pip install '{DIST_NAME}[add]'"
    assert not hint.startswith("pip ")


def test_uv_venv_uses_uv_because_it_has_no_pip_module():
    hint = install_hint("add", _env(has_pip=False, uv_managed=True, has_uv=True))
    assert hint == f"uv pip install --python {PYTHON} '{DIST_NAME}[add]'"


def test_uv_preferred_over_pip_when_uv_owns_the_environment():
    # pip can be present in a uv venv (user installed it); uv still owns it.
    hint = install_hint("add", _env(has_pip=True, uv_managed=True, has_uv=True))
    assert hint.startswith("uv pip install --python")


def test_uv_used_when_interpreter_has_no_pip_even_outside_a_uv_venv():
    hint = install_hint("add", _env(has_pip=False, has_uv=True))
    assert hint.startswith("uv pip install --python")


def test_uv_venv_without_uv_on_path_still_points_at_uv_with_install_docs():
    # ensurepip is disabled in uv venvs, so suggesting it would be a dead end.
    hint = install_hint("add", _env(has_pip=False, uv_managed=True, has_uv=False))
    assert hint.startswith("uv pip install --python")
    assert "docs.astral.sh/uv" in hint


def test_no_pip_and_no_uv_falls_back_to_ensurepip():
    hint = install_hint("add", _env(has_pip=False))
    assert hint == (f"{PYTHON} -m ensurepip --upgrade && "
                    f"{PYTHON} -m pip install '{DIST_NAME}[add]'")


# ── install target ───────────────────────────────────────────────────

def test_checkout_installs_editable_so_the_running_copy_gets_the_extra():
    # Naming the published dist would fetch a *second* copy from PyPI and
    # leave the checkout the user is running without the extra.
    assert install_target("add", _env(project_root=ROOT)) == f"-e '{ROOT}[add]'"


def test_non_checkout_installs_the_published_distribution():
    assert install_target("add", _env()) == f"'{DIST_NAME}[add]'"


def test_extra_name_is_interpolated():
    assert "[e2e]" in install_hint("e2e", _env())


# ── quoting ──────────────────────────────────────────────────────────

def test_paths_with_spaces_are_shell_quoted():
    spaced = "/opt/my env/bin/python"
    hint = install_hint("add", _env(executable=spaced,
                                    project_root=Path("/opt/my checkout")))
    assert "'/opt/my env/bin/python'" in hint
    assert "'/opt/my checkout[add]'" in hint


def test_python_module_command_quotes_the_interpreter():
    cmd = python_module_command("playwright", "install", "chromium",
                                env=_env(executable="/opt/my env/bin/python"))
    assert cmd == "'/opt/my env/bin/python' -m playwright install chromium"


# ── uv venv detection ────────────────────────────────────────────────

def test_uv_venv_detected_from_pyvenv_cfg(tmp_path):
    (tmp_path / "pyvenv.cfg").write_text("home = /x\nuv = 0.11.25\nversion_info = 3.13.11\n")
    assert _is_uv_venv(tmp_path) is True


def test_stdlib_venv_not_reported_as_uv(tmp_path):
    (tmp_path / "pyvenv.cfg").write_text("home = /usr/bin\ninclude-system-site-packages = false\n")
    assert _is_uv_venv(tmp_path) is False


def test_missing_pyvenv_cfg_is_not_a_uv_venv(tmp_path):
    assert _is_uv_venv(tmp_path / "nope") is False


def test_uv_key_matched_on_its_own_line_not_as_a_substring(tmp_path):
    (tmp_path / "pyvenv.cfg").write_text("home = /home/someone/uv = fake\n")
    assert _is_uv_venv(tmp_path) is False


def test_detect_env_uses_prefix_so_a_symlinked_interpreter_still_resolves(monkeypatch, tmp_path):
    # .venv/bin/python is normally a symlink into the base install; resolving
    # it walks out of the venv and pyvenv.cfg is never found.
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("uv = 0.11.25\n")
    real_python = tmp_path / "base" / "bin" / "python"
    real_python.parent.mkdir(parents=True)
    real_python.touch()
    link = venv / "bin" / "python"
    link.symlink_to(real_python)

    monkeypatch.setattr("sys.executable", str(link))
    monkeypatch.setattr("sys.prefix", str(venv))
    assert detect_env().uv_managed is True


def test_detect_env_reports_this_interpreter():
    assert detect_env().executable == sys.executable
