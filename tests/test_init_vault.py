"""`llmwiki init` must scaffold into the configured vault, not the clone (#29).

Problem 1 of #29: setup.sh ran `llmwiki init`, which hard-coded REPO_ROOT
and grew raw/ wiki/ site/ inside the git checkout. init has to honor the
vault so personal data lands outside the repo.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _no_personal_vault_config(monkeypatch):
    import llmwiki.config_schedule as config_schedule_mod

    monkeypatch.setattr(config_schedule_mod, "load_default_vault_path", lambda: None)


def test_init_scaffolds_into_vault(tmp_path: Path):
    from llmwiki.cli import cmd_init

    vault = tmp_path / "vault"
    vault.mkdir()
    rc = cmd_init(argparse.Namespace(vault=vault))

    assert rc == 0
    assert (vault / "raw" / "sessions").is_dir()
    assert (vault / "wiki" / "index.md").is_file()
    assert (vault / "site").is_dir()
    # The seed content lands in the vault, not the repo.
    assert "# Wiki Index" in (vault / "wiki" / "index.md").read_text(encoding="utf-8")
