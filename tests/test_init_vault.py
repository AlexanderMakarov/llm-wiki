"""`llmwiki init` must scaffold into the configured vault, not the clone (#29).

Problem 1 of #29: setup.sh ran `llmwiki init`, which hard-coded REPO_ROOT
and grew raw/ wiki/ site/ inside the git checkout. init has to honor the
vault so personal data lands outside the repo.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
import llmwiki.config_schedule as config_schedule_mod
from llmwiki.cli import cmd_init



@pytest.fixture(autouse=True)
def _no_personal_vault_config(monkeypatch):

    monkeypatch.setattr(config_schedule_mod, "load_default_vault_path", lambda: None)


def test_init_scaffolds_into_vault(tmp_path: Path):

    vault = tmp_path / "vault"
    vault.mkdir()
    rc = cmd_init(argparse.Namespace(vault=vault))

    assert rc == 0
    assert (vault / "raw" / "sessions").is_dir()
    assert (vault / "wiki" / "index.md").is_file()
    assert (vault / "site").is_dir()
    # The seed content lands in the vault, not the repo.
    assert "# Wiki Index" in (vault / "wiki" / "index.md").read_text(encoding="utf-8")


def test_init_bootstraps_a_missing_vault_dir(tmp_path: Path):
    # `init` is the command that creates the structure — if the configured
    # vault dir doesn't exist yet, it should create it, not error out (#29
    # review). Prevents the "set a vault path, run init, get exit 2" trap.

    vault = tmp_path / "not-yet-created"
    assert not vault.exists()
    rc = cmd_init(argparse.Namespace(vault=vault))

    assert rc == 0
    assert (vault / "raw" / "sessions").is_dir()
    assert (vault / "wiki" / "index.md").is_file()
