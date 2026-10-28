"""Session-config helpers extracted from cli.py (#691 / #arch-h8).

Schedule and synthesis settings from ``examples/sessions_config.json``
(the canonical shipped config). ``cli.py`` re-exports schedule helpers
under the original underscored names for back-compat.
"""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Any

from llmwiki import PACKAGE_ROOT
from llmwiki.state_store import configure_state_file

# Config files always live in the git clone, even when ``LLMWIKI_ROOT``
# points content reads/writes at an external vault.
_CLONE_ROOT = PACKAGE_ROOT.parent
_SESSIONS_CONFIG = _CLONE_ROOT / "examples" / "sessions_config.json"
_USER_CONFIG = _CLONE_ROOT / "config.json"


def user_config_path() -> Path:
    """The operator's ``config.json`` — the one file settings are read from and saved to.

    Resolved on each call, so code that writes settings follows wherever the
    read side points (tests redirect it away from the clone, #367).
    """
    return _USER_CONFIG


def _load_sessions_config(config_path: Path | None = None) -> dict[str, Any]:
    if config_path is not None:
        path = config_path
        if not path.is_file():
            return {}
        try:
            data = _json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    merged: dict[str, Any] = {}
    for path in (_SESSIONS_CONFIG, _USER_CONFIG):
        if not path.is_file():
            continue
        try:
            data = _json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        for section, value in data.items():
            if isinstance(value, dict) and isinstance(merged.get(section), dict):
                merged[section].update(value)
            else:
                merged[section] = value
    return merged


def load_default_vault_path() -> Path | None:
    """Return ``vault.default_path`` from config.json / sessions_config.json."""
    vault = _load_sessions_config().get("vault", {})
    if not isinstance(vault, dict):
        return None
    raw = str(vault.get("default_path", "")).strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def default_vault_for_checkout(working_dir: Path) -> Path | None:
    """``vault.default_path`` a run started in checkout ``working_dir`` resolves.

    Reads ``<working_dir>/config.json`` first, then
    ``<working_dir>/examples/sessions_config.json`` — the same precedence
    :func:`_load_sessions_config` gives the running clone. ``~`` is expanded and a
    relative path is taken against ``working_dir``, the run's current directory.
    Returns ``None`` when neither file sets a path.
    """
    wd = Path(working_dir)
    for path in (wd / "config.json", wd / "examples" / "sessions_config.json"):
        vault = _load_sessions_config(path).get("vault", {})
        if not isinstance(vault, dict):
            continue
        raw = str(vault.get("default_path", "")).strip()
        if raw:
            target = Path(raw).expanduser()
            return target if target.is_absolute() else wd / target
    return None


class VaultNotConfigured(RuntimeError):
    """No vault was named and config has no ``vault.default_path``.

    Callers must not fall back to the package directory or the source
    checkout. That used to look like success while writing
    ``llmwiki-state.json`` next to the installed package.
    """

    def __init__(self) -> None:
        super().__init__(
            "no vault configured. Pass --vault PATH or set "
            "vault.default_path in config.json."
        )


_BOUND_VAULT: Path | None = None


def clear_vault_binding() -> None:
    """Drop the process vault so the next call resolves again.

    Tests bind a throwaway vault per test. A binding left from an earlier
    call would ignore that.
    """
    global _BOUND_VAULT
    _BOUND_VAULT = None


def bind_vault(path: Path) -> Path:
    """Remember ``path`` as the only vault root for this process.

    State is ``<vault>/llmwiki-state.json``. Later vault reads and writes
    use this path instead of resolving again.
    """
    global _BOUND_VAULT
    resolved = Path(path).expanduser().resolve()
    _BOUND_VAULT = resolved
    configure_state_file(resolved)
    return resolved


def active_vault() -> Path:
    """Return the process vault, resolving it on the first call.

    An explicit :func:`bind_vault` (CLI ``--vault``, or a test) wins.
    Otherwise ``vault.default_path`` from config is bound and reused.
    When neither is set, this raises :class:`VaultNotConfigured`.
    """
    if _BOUND_VAULT is not None:
        return _BOUND_VAULT
    default = load_default_vault_path()
    if default is None:
        raise VaultNotConfigured()
    return bind_vault(default)


def resolve_content_root() -> Path:
    """Return the directory containing ``raw/`` and ``wiki/`` for reads/writes.

    Same path as :func:`active_vault`. The package directory is not a vault.
    """
    return active_vault()


def vault_path(*parts: str) -> Path:
    """Join ``parts`` onto the one vault this process is bound to.

    This is the only way to name ``raw/``, ``wiki/``, ``site/``, or
    ``graph/``. Callers do not invent a second root.
    """
    return active_vault().joinpath(*parts)


def resolve_vault_dir(
    explicit: Path | None,
    legacy: Path | None,
    *parts: str,
) -> Path:
    """Return a directory inside the bound vault.

    An explicit path wins. A ``legacy`` module global wins only when a
    test has pointed it somewhere other than the code checkout
    (``_CLONE_ROOT``). The checkout copy of ``raw/`` or ``wiki/`` is not
    a vault.
    """
    if explicit is not None:
        return explicit
    packaged = _CLONE_ROOT.joinpath(*parts)
    if legacy is not None and legacy != packaged:
        return legacy
    return vault_path(*parts)


def apply_default_vault(args: Any) -> None:
    """Fill ``args.vault`` once and point state at that vault.

    ``--vault`` wins. Otherwise the first resolution reads
    ``vault.default_path``. Library code then uses the bound vault and
    does not read config again. ``--state-file``, when the command has
    one, still overrides the state file after the vault is bound.
    With neither ``--vault`` nor a configured default, the vault stays
    unbound so a later read or write fails instead of using the package
    directory.
    """

    if getattr(args, "vault", None) is None:
        default = load_default_vault_path()
        if default is not None:
            args.vault = default
    if getattr(args, "vault", None) is not None:
        bind_vault(args.vault)
    explicit_state = getattr(args, "state_file", None)
    if explicit_state is not None:
        configure_state_file(explicit_state)


def load_schedule_config() -> dict[str, str]:
    """Load build/lint schedule config from sessions_config.json.

    Returns a dict with at minimum ``build`` and ``lint`` keys, each
    one of ``on-sync``, ``daily``, ``weekly``, ``manual``, or ``never``.
    Defaults are ``build: on-sync, lint: manual`` when the config file
    is missing or malformed.
    """
    data = _load_sessions_config()
    schedule = data.get("schedule", {})
    return {
        "build": schedule.get("build", "on-sync"),
        "lint": schedule.get("lint", "manual"),
    }


def should_run_after_sync(schedule: str) -> bool:
    """Return True if the schedule value indicates running after sync.

    Accepted values: ``on-sync``, ``daily``, ``weekly``, ``manual``,
    ``never``. Only ``on-sync`` triggers from cmd_sync. ``daily`` /
    ``weekly`` run from a scheduled task; ``manual`` and ``never``
    never auto-run.
    """
    return schedule.lower() == "on-sync"


def load_synthesis_backend(config_path: Path | None = None) -> str:
    """Return ``synthesis.backend`` from sessions config (default: ``dummy``)."""
    data = _load_sessions_config(config_path)
    synthesis = data.get("synthesis", {})
    if not isinstance(synthesis, dict):
        return "dummy"
    backend = synthesis.get("backend", "dummy")
    return str(backend) if backend else "dummy"


def synthesis_status_hint(backend: str | None = None) -> str | None:
    """One-line hint for ``sync --status`` when wiki/sources/ may stay empty."""
    name = (backend or load_synthesis_backend()).strip().lower()
    if name == "dummy":
        return (
            "Synthesis backend: dummy — wiki/sources/ stays stub-only until you set "
            "synthesis.backend to ollama (or agent-delegate) in "
            "examples/sessions_config.json and run `llmwiki synth`, or use "
            "`llmwiki all` after configuring a real backend."
        )
    return (
        f"Synthesis backend: {name} — run `llmwiki synth` to fill wiki/sources/ "
        "(and harvest candidates), "
        "or `llmwiki all` to chain synthesis before build."
    )
