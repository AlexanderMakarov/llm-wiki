"""``llmwiki synth`` handler contracts (``cmd_synthesize``).

# @layer: unit
# @spec: 280-shrink-test-suite
# @regression

Parser-only checks live here as supplements. Post-parse branches assert exit
code plus distinctive stderr/stdout or a harvest/config side effect
(CODING_STANDARDS CLI handlers).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from llmwiki.cli import SYNTH_BACKEND_CHOICES, build_parser, cmd_synthesize
from llmwiki.synth.pipeline import MAX_SYNTH_CONCURRENCY


def _seed_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "raw" / "sessions").mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki" / "sources").mkdir(parents=True)
    (vault / "llmwiki-state.json").write_text("{}", encoding="utf-8")
    return vault


def _ok_summary() -> dict[str, Any]:
    return {
        "total_scanned": 1,
        "new_files": 1,
        "synthesized": 1,
        "skipped": 0,
        "errors": [],
    }


def _available_backend(*, name: str = "dummy") -> MagicMock:
    backend = MagicMock()
    backend.name = name
    backend.is_available.return_value = True
    return backend


def test_synth_subcommand_is_registered() -> None:
    """``llmwiki synth`` must be a parser subcommand wired to ``cmd_synthesize``."""
    parser = build_parser()
    sub = next(a for a in parser._actions if getattr(a, "choices", None))
    assert "synth" in sub.choices
    args = parser.parse_args(["synth", "--check"])
    assert args.func is cmd_synthesize


def test_synth_parser_accepts_documented_backends() -> None:
    """Every documented ``--backend`` choice must parse; omitting the flag leaves it unset."""
    for name in SYNTH_BACKEND_CHOICES:
        args = build_parser().parse_args(["synth", "--backend", name])
        assert args.backend == name
    assert build_parser().parse_args(["synth"]).backend is None


def test_synth_parser_rejects_unknown_backend() -> None:
    """An unknown ``--backend`` name must fail at parse time with exit 2."""
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["synth", "--backend", "nope"])
    assert excinfo.value.code == 2


def test_sources_only_and_candidates_only_rejected_by_parser() -> None:
    """Argparse must refuse combining ``--sources-only`` with ``--candidates-only``."""
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["synth", "--sources-only", "--candidates-only"])
    assert excinfo.value.code == 2


def test_handler_still_refuses_sources_only_with_candidates_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """If both mode flags are set on the namespace, ``cmd_synthesize`` must exit 2 with the mutex error (not only argparse)."""
    vault = _seed_vault(tmp_path)
    args = build_parser().parse_args(
        ["synth", "--sources-only", "--vault", str(vault)]
    )
    args.candidates_only = True
    rc = cmd_synthesize(args)
    err = capsys.readouterr().err
    assert rc == 2
    assert "--sources-only and --candidates-only are mutually exclusive" in err


def test_concurrency_out_of_range_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--concurrency`` outside 1..MAX must exit 2 and name the illegal value."""
    vault = _seed_vault(tmp_path)
    args = build_parser().parse_args(
        ["synth", "--concurrency", "0", "--vault", str(vault)]
    )
    rc = cmd_synthesize(args)
    err = capsys.readouterr().err
    assert rc == 2
    assert f"--concurrency must be between 1 and {MAX_SYNTH_CONCURRENCY}" in err
    assert "(got 0)" in err


def test_unavailable_backend_exits_1_without_synthesizing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unreachable backend must print an error, skip synthesize, and exit 1."""
    vault = _seed_vault(tmp_path)
    backend = MagicMock()
    backend.name = "claude-cli"
    backend.is_available.return_value = False
    with (
        patch("llmwiki.cli.resolve_backend", return_value=backend),
        patch("llmwiki.cli.synthesize_new_sessions") as synth,
    ):
        rc = cmd_synthesize(
            build_parser().parse_args(["synth", "--vault", str(vault)])
        )
    err = capsys.readouterr().err
    assert rc == 1
    assert "backend claude-cli is not available" in err
    synth.assert_not_called()


def test_check_prints_backend_and_availability(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``synth --check`` must print Backend and Available lines and exit 0 when reachable."""
    vault = _seed_vault(tmp_path)
    with patch("llmwiki.cli.resolve_backend", return_value=_available_backend(name="dummy")):
        rc = cmd_synthesize(
            build_parser().parse_args(
                ["synth", "--check", "--vault", str(vault)]
            )
        )
    out = capsys.readouterr().out
    assert rc == 0
    assert "Backend: dummy" in out
    assert "Available: True" in out


def test_backend_override_does_not_write_config_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A one-shot ``--backend`` override must not persist into ``config.json`` on disk."""
    vault = _seed_vault(tmp_path)
    writes: list[Path] = []
    pinned = {"synthesis": {"backend": "ollama"}}

    class _Dummy:
        name = "dummy"

        def is_available(self) -> bool:
            return True

    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend",
        lambda cfg: _Dummy() if cfg["synthesis"]["backend"] == "dummy" else None,
    )
    monkeypatch.setattr(
        "llmwiki.cli.synthesize_new_sessions",
        lambda **kwargs: _ok_summary(),
    )
    monkeypatch.setattr("llmwiki.cli.run_harvest", lambda *a, **k: 0)
    monkeypatch.setattr("llmwiki.cli._refresh_review_counts", lambda *a, **k: None)
    monkeypatch.setattr("llmwiki.cli.stamp_last_synth_at", lambda: None)

    real_write = Path.write_text

    def _spy_write(self: Path, *a, **k):
        writes.append(self)
        return real_write(self, *a, **k)

    monkeypatch.setattr(Path, "write_text", _spy_write)

    args = build_parser().parse_args([
        "synth", "--backend", "dummy", "--sources-only", "--vault", str(vault),
    ])
    assert cmd_synthesize(args) == 0
    assert pinned["synthesis"]["backend"] == "ollama"
    assert not any(p.name == "config.json" for p in writes)


@pytest.mark.parametrize("override", ["claude", "cursor_cli", "dummy", "ollama"])
def test_check_backend_overlay_is_process_local(
    override: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``synth --check --backend`` must use the override for this process and leave the pinned config dict unchanged."""
    vault = _seed_vault(tmp_path)
    pinned = {"synthesis": {"backend": "dummy" if override != "dummy" else "ollama"}}
    seen: dict[str, Any] = {}

    class _Stub:
        name = override

        def is_available(self) -> bool:
            return True

    def _resolve(cfg: dict[str, Any]):
        seen["cfg"] = cfg
        return _Stub()

    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)
    monkeypatch.setattr("llmwiki.cli.resolve_backend", _resolve)

    rc = cmd_synthesize(
        build_parser().parse_args([
            "synth", "--check", "--backend", override, "--vault", str(vault),
        ])
    )
    assert rc == 0
    assert seen["cfg"]["synthesis"]["backend"] == override
    if override != "dummy":
        assert pinned["synthesis"]["backend"] == "dummy"
    else:
        assert pinned["synthesis"]["backend"] == "ollama"
    out = capsys.readouterr().out
    assert f"Backend: {override}" in out
    assert "Available: True" in out


def test_default_synth_harvests_then_prints_run_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Bare ``synth`` must harvest after sources, then print Synthesized and Duration."""
    vault = _seed_vault(tmp_path)
    with (
        patch("llmwiki.cli.resolve_backend", return_value=_available_backend()),
        patch("llmwiki.cli.synthesize_new_sessions", return_value=_ok_summary()),
        patch("llmwiki.cli.run_harvest", return_value=0) as harvest,
        patch("llmwiki.cli._refresh_review_counts") as refresh,
        patch("llmwiki.cli.stamp_last_synth_at"),
    ):
        rc = cmd_synthesize(
            build_parser().parse_args(["synth", "--vault", str(vault)])
        )
    out = capsys.readouterr().out
    assert rc == 0
    harvest.assert_called_once()
    assert harvest.call_args.kwargs.get("require_sources") is False
    refresh.assert_called_once()
    assert "Synthesized: 1" in out
    assert "Duration:" in out


def test_sources_only_skips_harvest_but_still_prints_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--sources-only`` must not harvest and must still print the end-of-run summary."""
    vault = _seed_vault(tmp_path)
    with (
        patch("llmwiki.cli.resolve_backend", return_value=_available_backend()),
        patch("llmwiki.cli.synthesize_new_sessions", return_value=_ok_summary()),
        patch("llmwiki.cli.run_harvest") as harvest,
        patch("llmwiki.cli.stamp_last_synth_at"),
    ):
        rc = cmd_synthesize(
            build_parser().parse_args(
                ["synth", "--sources-only", "--vault", str(vault)]
            )
        )
    out = capsys.readouterr().out
    assert rc == 0
    harvest.assert_not_called()
    assert "Synthesized: 1" in out
    assert "Duration:" in out


def test_harvest_failure_returns_harvest_rc_without_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When harvest returns non-zero, ``synth`` must return that code and skip the success summary."""
    vault = _seed_vault(tmp_path)
    with (
        patch("llmwiki.cli.resolve_backend", return_value=_available_backend()),
        patch("llmwiki.cli.synthesize_new_sessions", return_value=_ok_summary()),
        patch("llmwiki.cli.run_harvest", return_value=1),
        patch("llmwiki.cli._refresh_review_counts") as refresh,
        patch("llmwiki.cli.stamp_last_synth_at"),
    ):
        rc = cmd_synthesize(
            build_parser().parse_args(["synth", "--vault", str(vault)])
        )
    out = capsys.readouterr().out
    assert rc == 1
    refresh.assert_not_called()
    assert "Synthesized:" not in out


@pytest.mark.parametrize(
    ("backend_key", "nested", "expected_model"),
    [
        ("cursor_cli", {"cursor_cli": {"model": "composer-2.5"}}, "composer-2.5"),
        ("claude", {"claude": {"model": "haiku"}, "claude_model": "sonnet"}, "haiku"),
        ("claude", {"claude_model": "sonnet"}, "sonnet"),
    ],
    ids=["cursor_nested", "claude_nested_wins", "claude_flat"],
)
def test_estimate_honors_backend_model_and_does_not_persist_override(
    backend_key: str,
    nested: dict[str, Any],
    expected_model: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``synth --estimate --backend`` must print that backend's execution model and leave pinned config unchanged."""
    vault = _seed_vault(tmp_path)
    pinned = {"synthesis": {"backend": "dummy", **nested}}
    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)
    monkeypatch.setattr("llmwiki.cli._discover_raw_sessions", lambda raw_dir=None: [])
    monkeypatch.setattr("llmwiki.cli._load_state", lambda _p=None: {})
    monkeypatch.setattr("llmwiki.synth.pipeline._discover_raw_sessions", lambda raw_dir=None: [])
    monkeypatch.setattr("llmwiki.synth.pipeline._load_state", lambda _p=None: {})

    rc = cmd_synthesize(
        build_parser().parse_args([
            "synth", "--estimate", "--backend", backend_key, "--vault", str(vault),
        ])
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert pinned["synthesis"]["backend"] == "dummy"
    assert f"Execution model: {expected_model}" in out
