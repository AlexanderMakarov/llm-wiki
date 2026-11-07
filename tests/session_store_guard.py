"""Fail tests that list or open paths under the developer's real session stores.

Session adapters used to freeze ``Path.home()`` at import time (#369), so
pointing ``HOME`` at the per-test sandbox did not isolate filesystem access.
Default paths are now resolved lazily; this guard ensures no code path still
walks, stats, or reads the contributor's real agent stores during pytest.

Uses ``REAL_HOME`` from ``tests.tracked_files`` (captured before the sandbox).
"""

from __future__ import annotations

import builtins
import os
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.tracked_files import REAL_HOME

#: Path segments (under ``REAL_HOME``) that match default adapter session stores
#: or the dirs the watch mtime code scans — not e.g. ``.claude/settings.json``.
_FORBIDDEN_REL_PREFIXES: tuple[tuple[str, ...], ...] = (
    (".claude", "projects"),
    (".codex",),
    (".cursor", "chats"),
    (".cursor", "projects"),  # legacy / tooling layouts
    (".openclaw",),
    (".gemini",),
    (".copilot",),
    (".config", "Cursor"),
    (".config", "gemini"),
    (".config", "opencode"),
    (".config", "openclaw"),
    (".config", "Code"),
    (".config", "Code - Insiders"),
    (".config", "VSCodium"),
    (".local", "share", "gemini"),
    ("Library", "Application Support", "Cursor"),
    ("Library", "Application Support", "Code"),
    ("Library", "Application Support", "Code - Insiders"),
    ("Library", "Application Support", "VSCodium"),
    ("Library", "Application Support", "opencode"),
    ("Library", "Application Support", "openclaw"),
    ("AppData", "Roaming", "Cursor"),
    ("AppData", "Roaming", "Code"),
    ("AppData", "Roaming", "Code - Insiders"),
    ("AppData", "Roaming", "VSCodium"),
    ("AppData", "Roaming", "gemini"),
    ("AppData", "Roaming", "opencode"),
    ("AppData", "Roaming", "openclaw"),
    ("AppData", "Local", "Obsidian"),
    ("Documents", "Obsidian Vault"),
    ("Obsidian",),
    ("Downloads", "chatgpt-export"),
)


_REAL_HOME_ABS: Path | None = None


def _resolved_home() -> Path:
    """Absolute real home without ``Path.resolve()`` (patched ``os.stat`` would recurse)."""
    global _REAL_HOME_ABS
    if _REAL_HOME_ABS is None:
        _REAL_HOME_ABS = Path(os.path.abspath(os.fspath(REAL_HOME)))
    return _REAL_HOME_ABS


def _path_from_open_arg(file: Any) -> Path | None:
    if isinstance(file, int):
        return None
    if isinstance(file, (str, bytes)):
        s = os.fsdecode(file) if isinstance(file, bytes) else file
        if not s or s[0] == "|":
            return None
        # SQLite URI etc.
        if s.startswith("file:"):
            s = s[5:]
            if s.startswith("//"):
                s = s[2:]
        try:
            return Path(s)
        except ValueError:
            return None
    if isinstance(file, Path):
        return file
    return None


def _rel_under_real_home(path: Path) -> tuple[str, ...] | None:
    """Home-relative parts without ``Path.resolve()`` (would recurse into patched ``os.stat``)."""
    try:
        home = _resolved_home()
        path_abs = Path(os.path.abspath(os.fspath(path)))
        home_abs = Path(os.path.abspath(os.fspath(home)))
        rel = path_abs.relative_to(home_abs)
    except (ValueError, OSError):
        return None
    return rel.parts


def _forbidden_reason(path: Path) -> str | None:
    parts = _rel_under_real_home(path)
    if not parts:
        return None
    for prefix in _FORBIDDEN_REL_PREFIXES:
        if len(parts) >= len(prefix) and parts[: len(prefix)] == prefix:
            return f"session-store path touches real home: {path}"
    return None


def _wrap_scandir(
    real: Callable[..., Any],
) -> Callable[..., Any]:
    def wrapper(path: str | Path | bytes | int = ".", *a: Any, **kw: Any) -> Any:
        if isinstance(path, int):
            return real(path, *a, **kw)
        p = Path(os.fsdecode(path)) if isinstance(path, bytes) else Path(path)
        reason = _forbidden_reason(p)
        if reason:
            pytest.fail(reason)
        return real(path, *a, **kw)

    return wrapper


def _wrap_open(real_open: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(file: Any, *args: Any, **kwargs: Any) -> Any:
        p = _path_from_open_arg(file)
        if p is not None:
            reason = _forbidden_reason(p)
            if reason:
                pytest.fail(reason)
        return real_open(file, *args, **kwargs)

    return wrapper


def _wrap_sqlite_connect(real: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(database: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(database, sqlite3.Connection):
            return real(database, *args, **kwargs)
        s: str
        if isinstance(database, bytes):
            s = os.fsdecode(database)
        elif isinstance(database, str):
            s = database
        else:
            return real(database, *args, **kwargs)
        if s.startswith("file:"):
            s = s[5:]
            if s.startswith("//"):
                s = s[2:]
            q = s.find("?")
            if q >= 0:
                s = s[:q]
        p = Path(s)
        reason = _forbidden_reason(p)
        if reason:
            pytest.fail(reason)
        return real(database, *args, **kwargs)

    return wrapper


def _wrap_os_stat(real: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(path: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(path, (int, os.stat_result)):
            return real(path, *args, **kwargs)
        p = Path(os.fsdecode(path)) if isinstance(path, bytes) else Path(path)
        reason = _forbidden_reason(p)
        if reason:
            pytest.fail(reason)
        return real(path, *args, **kwargs)

    return wrapper


def install_session_store_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch I/O used to walk, stat, or open real session-store paths."""
    monkeypatch.setattr(builtins, "open", _wrap_open(builtins.open))
    monkeypatch.setattr(os, "scandir", _wrap_scandir(os.scandir))
    monkeypatch.setattr(os, "stat", _wrap_os_stat(os.stat))
    monkeypatch.setattr(os, "lstat", _wrap_os_stat(os.lstat))
    monkeypatch.setattr(sqlite3, "connect", _wrap_sqlite_connect(sqlite3.connect))
