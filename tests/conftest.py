"""Pytest config for llmwiki tests.

Makes sure the `llmwiki` package is importable regardless of where pytest is
invoked from, and that tests never write into the developer's real vault or
inherit gitignored root ``config.json`` settings (``vault.default_path``,
``synthesis.concurrency``, convert filters, …).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from llmwiki.state_store import configure_state_file

# Autouse guard (#91): fails any test that leaves a tracked file modified.
# Imported for its side effect of registering the fixture.
from tests.tracked_files import tracked_file_guard  # noqa: F401

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

    Also points ``config_schedule._USER_CONFIG`` and ``convert.USER_CONFIG_FILE``
    at a path that does not exist (#142) so ``_load_sessions_config`` /
    ``convert_all`` never merge the developer's gitignored root ``config.json``.
    Opt-in merge tests re-point those names at a fixture file themselves.
    """
    isolated = tmp_path_factory.mktemp("llmwiki-default-vault")
    (isolated / "raw" / "sessions").mkdir(parents=True)
    (isolated / "raw" / "docs").mkdir(parents=True)
    (isolated / "wiki" / "sources").mkdir(parents=True)

    # Missing file → merge skips the user overlay (is_file() is False).
    missing_user_config = isolated / "no-user-config.json"
    monkeypatch.setattr("llmwiki.config_schedule._USER_CONFIG", missing_user_config)
    monkeypatch.setattr("llmwiki.convert.USER_CONFIG_FILE", missing_user_config)

    monkeypatch.setattr(
        "llmwiki.config_schedule.load_default_vault_path",
        lambda: isolated,
    )

    configure_state_file(isolated)
    yield isolated
