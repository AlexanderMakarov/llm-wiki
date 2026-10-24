"""Per-test settings sandbox: every test gets its own home directory and operator config.

llmwiki keeps settings in two places: the operator ``config.json`` in the
checkout it runs from, and files under the user's home directory (agent hook
settings, scheduler units). The autouse ``settings_sandbox`` fixture in
``tests/conftest.py`` points both at a throwaway directory for every test.
Tests prepare and inspect settings through the fixture instead of patching
module paths or ``HOME`` themselves.
"""

from __future__ import annotations

import json
import site
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

#: Where Python finds user-installed packages, read before any test moves
#: ``HOME``: child processes derive it from ``HOME`` unless it is pinned.
_REAL_USER_BASE = site.getuserbase()


@dataclass(frozen=True)
class SettingsSandbox:
    """The throwaway settings locations one test runs against."""

    root: Path
    home: Path
    xdg_state: Path
    operator_config: Path

    def write_operator(self, data: Mapping[str, Any]) -> Path:
        """Write ``data`` as the operator ``config.json`` and return its path."""
        self.operator_config.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return self.operator_config

    def read_operator(self) -> dict[str, Any]:
        """Return the operator ``config.json`` the code under test wrote."""
        return json.loads(self.operator_config.read_text(encoding="utf-8"))


def install_sandbox(root: Path, monkeypatch: pytest.MonkeyPatch) -> SettingsSandbox:
    """Point the home directory, XDG config/state and the operator config at ``root``."""
    home = root / "home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    xdg_state = home / ".local" / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(xdg_state))
    monkeypatch.setenv("PYTHONUSERBASE", _REAL_USER_BASE)
    operator_config = root / "config.json"
    monkeypatch.setattr("llmwiki.config_schedule._USER_CONFIG", operator_config)
    return SettingsSandbox(root=root, home=home, xdg_state=xdg_state, operator_config=operator_config)
