"""Pytest config for llmwiki tests.

Makes sure the `llmwiki` package is importable regardless of where pytest is
invoked from, and that tests never touch the developer's real vault or real
settings: every test gets its own home directory and operator ``config.json``
(``settings_sandbox``), and a pytest run that changes the real ones, or a
tracked file, fails (``tests/tracked_files.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from llmwiki.automation_units import DiscoveryResult
from llmwiki.state_store import configure_state_file
from tests.settings_sandbox import SettingsSandbox, install_sandbox

# Session hooks that fail a run which changed a tracked file or a real settings
# file. Imported so pytest registers them from this conftest.
from tests.tracked_files import pytest_sessionfinish, pytest_sessionstart  # noqa: F401

# Ensure the repo root (which contains the `llmwiki/` package dir) is on
# sys.path when pytest is run from anywhere.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
SNAPSHOTS_DIR = REPO_ROOT / "tests" / "snapshots"


@pytest.fixture(autouse=True)
def _isolate_default_vault(tmp_path_factory, monkeypatch):
    """Redirect config-driven vault/state defaults away from a real vault.

    Without this, any test that calls ``resolve_state_file()``,
    ``synthesize_new_sessions()`` without ``state_file=``, or
    ``llmwiki synthesize --estimate`` without ``--vault`` will read/write
    ``config.json``'s ``vault.default_path`` (e.g. an Obsidian vault) and
    can wipe ``llmwiki-state.json``.
    """
    isolated = tmp_path_factory.mktemp("llmwiki-default-vault")
    (isolated / "raw" / "sessions").mkdir(parents=True)
    (isolated / "raw" / "docs").mkdir(parents=True)
    (isolated / "wiki" / "sources").mkdir(parents=True)

    monkeypatch.setattr(
        "llmwiki.config_schedule.load_default_vault_path",
        lambda: isolated,
    )

    configure_state_file(isolated)
    yield isolated


@pytest.fixture(autouse=True)
def settings_sandbox(tmp_path_factory, monkeypatch) -> SettingsSandbox:
    """Give every test its own home directory and operator ``config.json``.

    Request the fixture by name to prepare or inspect settings: the operator
    config through ``write_operator`` / ``read_operator``, files under the home
    directory through ``home``.
    """
    return install_sandbox(tmp_path_factory.mktemp("settings"), monkeypatch)


@pytest.fixture(autouse=True)
def _no_real_scheduler_discovery(monkeypatch):
    """Keep ``install-automation``'s guard and doctor's automation checks off the real scheduler.

    Tests that exercise either re-point ``discover_local_units`` themselves or
    pass ``discovery=`` explicitly.
    """
    monkeypatch.setattr(
        "llmwiki.automation_units.discover_local_units",
        lambda **_: DiscoveryResult(units=(), unavailable=None),
    )
