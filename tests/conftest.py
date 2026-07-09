"""Pytest config for llmwiki tests.

Makes sure the `llmwiki` package is importable regardless of where pytest is
invoked from, and that tests never write into the developer's real vault
(``config.json`` ``vault.default_path``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

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
    state_file = isolated / "llmwiki-state.json"

    monkeypatch.setattr(
        "llmwiki.config_schedule.load_default_vault_path",
        lambda: isolated,
    )
    from llmwiki.state_store import configure_state_file

    configure_state_file(isolated)
    yield isolated
