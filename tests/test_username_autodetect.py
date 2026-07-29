"""Tests for #489 — auto-detected `real_username` must not over-match
on Windows or stripped containers.

The bug: `load_config` fell back to `os.environ["USER"] or
Path.home().name`. Two failure modes hit users in the wild:

1. **Windows** uses `USERNAME` not `USER` → env lookup empty →
   fallback to `Path.home().name` returns the actual short name,
   which the redactor then substring-matched into unrelated path
   tokens.
2. **Stripped Docker / CI images** have `USER` unset and
   `Path.home()` = `/root` → fallback returns `"root"` → every
   `/Users/root/`, `/home/root/` path got mass-rewritten to
   `/Users/USER/`.

Fix: prefer `USER` → `USERNAME` → `Path.home().name` only when
it's ≥3 chars AND not in the generic-container set.
"""

from __future__ import annotations

import json
from pathlib import Path

from llmwiki import convert as convert_mod
from llmwiki.convert import (
    DEFAULT_CONFIG_FILE,
    _ensure_real_username,
    _overlay_config_file,
    load_config,
)


def _config_path(tmp_path: Path) -> Path:
    """A non-existent path so load_config skips file-merge and only
    runs the auto-detect branch we want to test."""
    return tmp_path / "no-such-config.json"


def test_unix_user_env_var_wins(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("USER", "alice")
    monkeypatch.delenv("USERNAME", raising=False)
    cfg = load_config(_config_path(tmp_path))
    assert cfg["redaction"]["real_username"] == "alice"


def test_windows_username_env_var_used_when_USER_missing(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.setenv("USERNAME", "alice-win")
    cfg = load_config(_config_path(tmp_path))
    assert cfg["redaction"]["real_username"] == "alice-win"


def test_USER_takes_precedence_over_USERNAME(tmp_path: Path, monkeypatch):
    """Unix-style env wins over Windows-style if both happen to be set
    (e.g. on Cygwin or WSL)."""
    monkeypatch.setenv("USER", "unix-user")
    monkeypatch.setenv("USERNAME", "win-user")
    cfg = load_config(_config_path(tmp_path))
    assert cfg["redaction"]["real_username"] == "unix-user"


def test_root_homedir_does_not_leak_as_username(tmp_path: Path, monkeypatch):
    """The original bug: stripped container with USER unset →
    Path.home().name was 'root' → every /home/root/ path got
    rewritten. Must now leave field empty so the redactor stays a
    no-op until user opts in."""
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("USERNAME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/root")))
    cfg = load_config(_config_path(tmp_path))
    assert cfg["redaction"]["real_username"] == ""


def test_generic_user_homedir_does_not_leak(tmp_path: Path, monkeypatch):
    """Same protection for `user`, `ubuntu`, `home` etc."""
    for generic in ("user", "User", "USER", "ubuntu", "home", "users"):
        monkeypatch.delenv("USER", raising=False)
        monkeypatch.delenv("USERNAME", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls, g=generic: Path(f"/home/{g}")))
        cfg = load_config(_config_path(tmp_path))
        assert cfg["redaction"]["real_username"] == "", generic


def test_short_homedir_name_skipped(tmp_path: Path, monkeypatch):
    """Names <3 chars are too risky as substring rewrite targets."""
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("USERNAME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/ab")))
    cfg = load_config(_config_path(tmp_path))
    assert cfg["redaction"]["real_username"] == ""


def test_long_specific_homedir_used(tmp_path: Path, monkeypatch):
    """Real user names (≥3 chars, not generic) ARE trusted as fallback."""
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("USERNAME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/pratiyush")))
    cfg = load_config(_config_path(tmp_path))
    assert cfg["redaction"]["real_username"] == "pratiyush"


def test_explicit_config_value_overrides_autodetect(tmp_path: Path, monkeypatch):
    """If the user wrote `real_username` into config, never auto-overwrite."""
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(
        json.dumps({"redaction": {"real_username": "explicitly-mine"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("USER", "should-be-ignored")
    cfg = load_config(cfg_path)
    assert cfg["redaction"]["real_username"] == "explicitly-mine"


def test_empty_real_username_in_overlay_does_not_wipe_autodetect(
    tmp_path: Path, monkeypatch
):
    """#56: config.json copied from examples often has ``"real_username": ""``
    meaning "auto-detect". Overlaying that empty string must not erase the
    username ``load_config`` already filled from ``$USER`` — otherwise
    ``restore_local_path`` no-ops and projects/index mixes ``/Users/USER/``
    with never-redacted real paths.
    """


    monkeypatch.setenv("USER", "alice")
    monkeypatch.delenv("USERNAME", raising=False)

    cfg = load_config(DEFAULT_CONFIG_FILE)
    assert cfg["redaction"]["real_username"] == "alice"

    overlay = tmp_path / "config.json"
    overlay.write_text(
        json.dumps({"redaction": {"real_username": "", "replacement_username": "USER"}}),
        encoding="utf-8",
    )
    _overlay_config_file(cfg, overlay)
    _ensure_real_username(cfg)
    assert cfg["redaction"]["real_username"] == "alice"


def test_resolve_convert_config_recovers_from_empty_overlay(
    tmp_path: Path, monkeypatch
):
    """End-to-end: ``_resolve_convert_config`` must still autodetect after
    a user config that carries the examples placeholder empty string."""


    monkeypatch.setenv("USER", "alice")
    monkeypatch.delenv("USERNAME", raising=False)

    examples = tmp_path / "examples.json"
    examples.write_text("{}", encoding="utf-8")
    user = tmp_path / "config.json"
    user.write_text(
        json.dumps({"redaction": {"real_username": ""}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(convert_mod, "DEFAULT_CONFIG_FILE", examples)
    monkeypatch.setattr(convert_mod, "USER_CONFIG_FILE", user)

    cfg = convert_mod._resolve_convert_config(None)
    assert cfg["redaction"]["real_username"] == "alice"
