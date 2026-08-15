"""The llmwiki source checkout refuses to be used as a knowledge vault (#109).

A clone carries ``.llmwiki-source-checkout`` at its root. Commands that write
vault content and were given no vault would resolve their content root to that
directory and scatter ``raw/`` / ``wiki/`` / ``site/`` across the source tree,
so they stop instead. An installed distribution has no marker beside the
package, and naming a vault always bypasses the guard.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from llmwiki import cli
from llmwiki.source_checkout import (
    SOURCE_CHECKOUT_MARKER,
    SourceCheckoutError,
    ensure_not_source_checkout,
    is_source_checkout,
)

#: Commands the guard covers — every one writes vault content into whatever
#: content root it resolves — paired with the smallest argv that parses.
GUARDED = (
    ("init", ["init"]),
    ("sync", ["sync"]),
    ("synth", ["synth"]),
    ("synthesize", ["synthesize"]),
    ("add", ["add", "some-document.md"]),
    ("build", ["build"]),
    ("all", ["all"]),
    ("watch", ["watch"]),
)


@pytest.fixture(autouse=True)
def _no_configured_vault(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise the dev checkout's gitignored ``config.json``.

    It points ``vault.default_path`` at a real vault, which would satisfy the
    guard and make every refusal assertion here vacuous.
    """
    monkeypatch.setattr("llmwiki.config_schedule.load_default_vault_path", lambda: None)


def _mark(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / SOURCE_CHECKOUT_MARKER).write_text("source checkout\n", encoding="utf-8")
    return root


# ─── Marker detection ─────────────────────────────────────────────────


def test_marker_is_detected(tmp_path: Path) -> None:
    assert is_source_checkout(_mark(tmp_path))


def test_directory_without_the_marker_is_not_a_checkout(tmp_path: Path) -> None:
    assert not is_source_checkout(tmp_path)


def test_a_directory_named_like_the_marker_is_not_a_marker(tmp_path: Path) -> None:
    """Only a file counts — a stray directory of that name must not trip it."""
    (tmp_path / SOURCE_CHECKOUT_MARKER).mkdir()
    assert not is_source_checkout(tmp_path)


def test_ensure_raises_with_actionable_text(tmp_path: Path) -> None:
    with pytest.raises(SourceCheckoutError) as excinfo:
        ensure_not_source_checkout(_mark(tmp_path), "build")

    message = str(excinfo.value)
    assert "--vault" in message
    assert "demo" in message
    assert "llmwiki build" in message


def test_ensure_passes_on_an_ordinary_directory(tmp_path: Path) -> None:
    ensure_not_source_checkout(tmp_path, "build")


# ─── CLI refusal ──────────────────────────────────────────────────────


@pytest.mark.parametrize(("command", "argv"), GUARDED, ids=[c for c, _ in GUARDED])
def test_command_refuses_inside_a_marked_checkout(
    command: str,
    argv: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "REPO_ROOT", _mark(tmp_path))

    with pytest.raises(SystemExit) as excinfo:
        cli.main(argv)

    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "--vault" in err
    assert "demo" in err
    assert f"llmwiki {command} --vault" in err


def test_refusal_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "REPO_ROOT", _mark(tmp_path))

    with pytest.raises(SystemExit):
        cli.main(["init"])

    assert [p.name for p in tmp_path.iterdir()] == [SOURCE_CHECKOUT_MARKER]


def test_init_proceeds_without_the_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)

    assert cli.main(["init"]) == 0
    assert (tmp_path / "wiki" / "index.md").is_file()
    assert (tmp_path / "raw" / "sessions").is_dir()


def test_explicit_vault_wins_inside_a_marked_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = _mark(tmp_path / "checkout")
    monkeypatch.setattr(cli, "REPO_ROOT", checkout)
    vault = tmp_path / "vault"

    assert cli.main(["init", "--vault", str(vault)]) == 0
    assert (vault / "wiki" / "index.md").is_file()
    assert not (checkout / "wiki").exists()


def test_configured_vault_wins_inside_a_marked_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``vault.default_path`` in config.json bypasses the guard too."""
    checkout = _mark(tmp_path / "checkout")
    vault = tmp_path / "configured"
    vault.mkdir()
    monkeypatch.setattr(cli, "REPO_ROOT", checkout)
    monkeypatch.setattr(
        "llmwiki.config_schedule.load_default_vault_path", lambda: vault
    )

    assert cli.main(["init"]) == 0
    assert (vault / "wiki" / "index.md").is_file()
    assert not (checkout / "wiki").exists()


# ─── Scope ────────────────────────────────────────────────────────────


def test_reporting_commands_are_not_guarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only vault-writing commands stop; ``lint`` and friends still read."""
    monkeypatch.setattr(cli, "REPO_ROOT", _mark(tmp_path))

    cli._apply_default_vault(
        argparse.Namespace(vault=None, cmd="lint", state_file=None)
    )


def test_direct_library_calls_are_not_guarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard is a CLI-border check keyed on the parsed subcommand.

    A caller building its own ``Namespace`` has chosen its content root
    deliberately and is left alone.
    """
    monkeypatch.setattr(cli, "REPO_ROOT", _mark(tmp_path))

    cli._apply_default_vault(argparse.Namespace(vault=None, state_file=None))
