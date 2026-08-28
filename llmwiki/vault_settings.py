"""Per-vault settings carried inside the wiki itself (#150).

``<vault-root>/llmwiki.json`` is a sibling of the per-vault
``llmwiki-state.json`` and holds the choices that belong to *the wiki*
rather than to this install — today, the lint rules that cannot apply to
it.  Copying, sharing, or committing the vault carries the file along,
which is why it is not the clone's gitignored ``config.json`` and why it
is not hidden under a dot-directory: a committed file a reviewer is meant
to read should be visible.

Read at the CLI border only.  Nothing under ``llmwiki/lint/rules/`` may
import this module: a rule receives pages and options and returns issues,
and never learns that a vault exists.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_MIN_REFS",
    "VAULT_SETTINGS_FILENAME",
    "VaultSettingsError",
    "disabled_lint_rules",
    "load_vault_settings",
    "vault_settings_path",
]

#: Name of the per-vault settings file, resolved against the content root.
VAULT_SETTINGS_FILENAME = "llmwiki.json"

#: Default significance threshold for candidate harvest and ``link_integrity``.
#: A wikilink target must be named by this many distinct source pages before
#: harvest materializes a stub and before lint treats an unresolved link as a
#: defect. Lives here (not in the harvest or lint packages) to avoid import
#: cycles — ``candidates_harvest`` already imports from ``link_integrity``.
DEFAULT_MIN_REFS = 3


class VaultSettingsError(RuntimeError):
    """Raised when a vault's ``llmwiki.json`` exists but cannot be used.

    Always a hard error the CLI turns into exit 2, never a silent ``{}``.
    A settings file nobody can parse might be switching every check off,
    so reporting the vault as clean would be a guess dressed up as a
    result — the same reasoning that makes an unknown rule name fatal.
    """


def vault_settings_path(root: Path) -> Path:
    """Return the settings file a content root would carry."""
    return Path(root) / VAULT_SETTINGS_FILENAME


def load_vault_settings(root: Path) -> dict[str, Any]:
    """Read and parse ``<root>/llmwiki.json``.

    A missing file is the normal case and yields ``{}`` — a vault that
    declares nothing behaves exactly as it did before this file existed.
    An unreadable, unparseable, or non-object file raises
    :class:`VaultSettingsError`.
    """
    path = vault_settings_path(root)
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise VaultSettingsError(f"{path}: cannot be read ({exc})") from exc
    try:
        settings = json.loads(text)
    except json.JSONDecodeError as exc:
        raise VaultSettingsError(
            f"{path}: is not valid JSON — {exc.msg} (line {exc.lineno}, column {exc.colno})"
        ) from exc
    if not isinstance(settings, dict):
        raise VaultSettingsError(
            f"{path}: top level must be a JSON object, got {type(settings).__name__}"
        )
    return settings


def disabled_lint_rules(settings: dict[str, Any]) -> dict[str, str]:
    """Extract ``lint.disabled_rules`` as ``{rule name: reason}``.

    Both declared shapes are accepted and normalised:

    ==========================================  ==========================
    ``{"lint": {"disabled_rules": ["a"]}}``     ``{"a": ""}``
    ``{"lint": {"disabled_rules": {"a": "r"}}}``  ``{"a": "r"}``
    ==========================================  ==========================

    Rule *names* are not validated here — that is
    :func:`llmwiki.lint.run_lint`'s job, which owns the registry and
    raises ``UnknownRuleError``.  A malformed *shape* is fatal for the
    same reason malformed JSON is: a declaration nobody can read must not
    quietly leave a check switched on.
    """
    lint = settings.get("lint")
    if lint is None:
        return {}
    if not isinstance(lint, dict):
        raise VaultSettingsError(
            f'"lint" must be a JSON object, got {type(lint).__name__}'
        )
    declared = lint.get("disabled_rules")
    if declared is None:
        return {}
    if isinstance(declared, dict):
        disabled: dict[str, str] = {}
        for name, reason in declared.items():
            if not isinstance(name, str):
                raise VaultSettingsError(
                    f'"lint.disabled_rules" keys must be rule names, got {name!r}'
                )
            disabled[name] = "" if reason is None else str(reason)
        return disabled
    if isinstance(declared, list):
        for name in declared:
            if not isinstance(name, str):
                raise VaultSettingsError(
                    f'"lint.disabled_rules" entries must be rule names, got {name!r}'
                )
        return dict.fromkeys(declared, "")
    raise VaultSettingsError(
        '"lint.disabled_rules" must be a list of rule names or an object '
        f"mapping rule names to reasons, got {type(declared).__name__}"
    )
