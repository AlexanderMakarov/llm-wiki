"""CLI tests for ``llmwiki synth --backend`` write isolation (#230).

Parser accept/reject, overlay-without-mutate, and estimate model resolution
live in ``test_synth_backends_shared.py``. This module keeps the
``config.json`` non-write spy, which needs a full synthesize path stub.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.cli import build_parser, cmd_synthesize


def _seed_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "raw" / "sessions").mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki" / "sources").mkdir(parents=True)
    (vault / "llmwiki-state.json").write_text("{}", encoding="utf-8")
    return vault


def test_cmd_synthesize_backend_override_not_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        lambda **kwargs: {
            "total_scanned": 0,
            "new_files": 0,
            "synthesized": 0,
            "skipped": 0,
            "errors": [],
            "backend": "dummy",
        },
    )

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
