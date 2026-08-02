"""Build an install command that works in the interpreter actually running llmwiki.

The optional-extra hints used to be hardcoded ``pip install 'llm-wiki[add]'``
strings. That command is wrong whenever a bare ``pip`` resolves to a different
interpreter than the one running llmwiki: a uv-managed venv (which ships no
``pip`` module at all), a wrapper script that execs a venv Python, or a source
checkout put on ``PYTHONPATH``. A hint that installs into the *wrong*
interpreter is worse than no hint — the install reports success and the import
keeps failing, so the user has no signal that anything went wrong.

Everything here is derived from ``sys.executable`` at call time, so the command
we print is the command that fixes the process doing the printing.
"""

from __future__ import annotations

import shlex
import shutil
import sys
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path

#: Distribution name on PyPI. Not the import name (``llmwiki``).
DIST_NAME = "llm-wiki"

_UV_DOCS = "https://docs.astral.sh/uv/"


@dataclass(frozen=True)
class PythonEnv:
    """How packages can be added to one interpreter, and from where.

    Constructed by :func:`detect_env` for the running process. Tests (and the
    planned ``doctor`` command) build it directly to describe an environment
    other than their own.
    """

    executable: str
    has_pip: bool          # ``pip`` importable *by this interpreter*
    uv_managed: bool       # interpreter lives in a uv-created virtualenv
    has_uv: bool           # ``uv`` binary on PATH
    project_root: Path | None  # source checkout to install editable, if any


def _project_root() -> Path | None:
    """Repo root when llmwiki runs from a checkout, else ``None``.

    A checkout must be installed with ``-e '<root>[extra]'``; naming the
    published distribution instead would fetch a second copy from PyPI and
    leave the checkout the user is actually running without the extra.
    """
    root = Path(__file__).resolve().parent.parent
    return root if (root / "pyproject.toml").is_file() else None


def _is_uv_venv(prefix: str | Path) -> bool:
    """True when the environment rooted at ``prefix`` was created by uv.

    uv stamps ``uv = <version>`` into ``pyvenv.cfg`` and omits ``pip`` from the
    venv, so the presence of that key is what tells us ``python -m pip`` will
    not work here.

    Takes the prefix rather than the interpreter path on purpose: ``.venv/bin/
    python`` is typically a symlink into the base installation, so resolving it
    walks *out* of the venv and never finds ``pyvenv.cfg``.
    """
    cfg = Path(prefix) / "pyvenv.cfg"
    try:
        text = cfg.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(line.strip().startswith("uv =") for line in text.splitlines())


def detect_env() -> PythonEnv:
    """Inspect the running interpreter for how to install packages into it."""
    return PythonEnv(
        executable=sys.executable,
        has_pip=find_spec("pip") is not None,
        uv_managed=_is_uv_venv(sys.prefix),
        has_uv=shutil.which("uv") is not None,
        project_root=_project_root(),
    )


def install_target(extra: str, env: PythonEnv | None = None) -> str:
    """Return the shell-quoted requirement for ``extra`` (``-e '<root>[add]'``)."""
    env = env or detect_env()
    if env.project_root is not None:
        return f"-e {shlex.quote(f'{env.project_root}[{extra}]')}"
    return shlex.quote(f"{DIST_NAME}[{extra}]")


def python_module_command(module: str, *args: str, env: PythonEnv | None = None) -> str:
    """Return ``<this python> -m <module> [args]``, interpreter shell-quoted.

    For follow-up steps that must run under the same interpreter as the extra
    that was just installed (``playwright install`` is the one in practice).
    """
    env = env or detect_env()
    return " ".join([shlex.quote(env.executable), "-m", module, *args])


def install_hint(extra: str, env: PythonEnv | None = None) -> str:
    """Return the exact command that installs ``extra`` into *this* interpreter.

    uv wins when it owns the environment or when there is no ``pip`` to call,
    because a uv venv has no ``pip`` module and a bare ``pip`` on PATH usually
    belongs to some other Python entirely.
    """
    env = env or detect_env()
    target = install_target(extra, env)
    python = shlex.quote(env.executable)
    if env.has_uv and (env.uv_managed or not env.has_pip):
        return f"uv pip install --python {python} {target}"
    if env.has_pip:
        return f"{python} -m pip install {target}"
    if env.uv_managed:
        # uv venv with uv missing from PATH: pip is absent here too, and
        # ensurepip is disabled in uv venvs, so uv is the only way back.
        return f"uv pip install --python {python} {target}   # needs uv: {_UV_DOCS}"
    return (f"{python} -m ensurepip --upgrade && "
            f"{python} -m pip install {target}")
