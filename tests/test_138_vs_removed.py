"""#138 — auto-generated /vs/ model-comparison surface is removed.

Locks the product cut: compare.py is gone, build exposes no
render_vs_section, and a real build does not emit site/vs/.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_compare_module_is_gone() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("llmwiki.compare")
    assert not (REPO_ROOT / "llmwiki" / "compare.py").exists()


def test_build_has_no_render_vs_section() -> None:
    build = importlib.import_module("llmwiki.build")
    assert not hasattr(build, "render_vs_section")


def test_cli_build_does_not_emit_vs(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    site = vault / "site"
    subprocess.run(
        [sys.executable, "-m", "llmwiki", "init", "--vault", str(vault)],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    session = vault / "raw" / "sessions" / "2026-08-01T12-00-demo-session.md"
    session.parent.mkdir(parents=True, exist_ok=True)
    session.write_text(
        "---\n"
        'title: "Demo session"\n'
        "type: source\n"
        "date: 2026-08-01\n"
        "project: demo\n"
        "slug: demo-session\n"
        "---\n\n# Demo\n\nhello\n",
        encoding="utf-8",
    )
    entities = vault / "wiki" / "entities"
    entities.mkdir(parents=True, exist_ok=True)
    for name, provider in (("ModelA.md", "A"), ("ModelB.md", "B")):
        (entities / name).write_text(
            "---\n"
            f'title: "{name.removesuffix(".md")}"\n'
            "type: entity\n"
            "entity_kind: ai-model\n"
            f"provider: {provider}\n"
            'model: {"context_window": 100000, "license": "proprietary"}\n'
            'pricing: {"input_per_1m": 1.0, "output_per_1m": 2.0}\n'
            'benchmarks: {"mmlu": 0.8, "swe_bench": 0.5}\n'
            "---\n\n# model\n",
            encoding="utf-8",
        )
    cp = subprocess.run(
        [
            sys.executable,
            "-m",
            "llmwiki",
            "build",
            "--vault",
            str(vault),
            "--out",
            str(site),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0, cp.stderr or cp.stdout
    assert not (site / "vs").exists()
    assert not (site / "vs" / "index.html").exists()
