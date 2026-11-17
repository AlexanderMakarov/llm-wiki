"""Shared repo-root path for mirrored test packages under ``tests/``."""

from __future__ import annotations

from pathlib import Path

# tests/_paths.py → parents[1] is the repository root.
REPO_ROOT = Path(__file__).resolve().parents[1]
