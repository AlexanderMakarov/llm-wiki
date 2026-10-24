"""Point a test at a throwaway checkout instead of the clone it runs from (#367).

``install-automation`` and ``configure-sources`` read and write the operator
``config.json`` and record the checkout the scheduled job runs from. A test
that redirects only one of the two lets the other reach the developer's real
files, or makes a "nothing was written" assertion look at a path the code no
longer writes.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def redirect_checkout(root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Make ``root`` the CLI's checkout and its ``config.json`` the operator config; return that config path."""
    config = root / "config.json"
    monkeypatch.setattr("llmwiki.cli.REPO_ROOT", root)
    monkeypatch.setattr("llmwiki.config_schedule._USER_CONFIG", config)
    return config
