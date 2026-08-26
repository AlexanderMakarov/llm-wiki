"""Tests for v0.3 additions — i18n docs, pyproject (eval framework never shipped; #154)."""

from __future__ import annotations

import re

import pytest

from llmwiki import __version__
from llmwiki.cli import build_parser
from tests.conftest import REPO_ROOT

# ─── version bump ────────────────────────────────────────────────────────


def test_version_is_at_least_v03():
    """v0.3 introduced pyproject. Any version >= 0.3 must continue to work."""
    major, minor, *_ = __version__.split(".")
    assert int(major) > 0 or int(minor) >= 3, f"expected >= 0.3, got {__version__}"


# ─── pyproject.toml ──────────────────────────────────────────────────────


def test_pyproject_exists():
    p = REPO_ROOT / "pyproject.toml"
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    # Minimal sanity
    # Distribution name is `llm-wiki` (fork of upstream llm-notebook).
    # Python module + CLI command remain `llmwiki`.
    assert 'name = "llm-wiki"' in content
    assert 'requires-python = ">=3.12"' in content
    # Accept any valid semver — bumped to 1.0 in v1.0.0 release
    assert re.search(r'version = "\d+\.\d+\.\d+', content), "missing version string"
    assert "markdown" in content
    assert "[project.scripts]" in content


def test_pyproject_declares_optional_deps():
    p = REPO_ROOT / "pyproject.toml"
    content = p.read_text(encoding="utf-8")
    # optional-dependencies section
    assert "[project.optional-dependencies]" in content
    # `pdf` extra was removed in the simplification sweep alongside the
    # PDF adapter. The remaining optional groups must stay declared.
    for opt in ("highlight", "dev", "all"):
        assert f"{opt} =" in content, f"missing optional dep group: {opt}"
    assert "pdf =" not in content, (
        "pdf optional dep was removed in the simplification sweep; "
        "don't reintroduce it"
    )


# ─── i18n docs ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("lang", ["es", "zh-CN", "ja"])
def test_i18n_getting_started_exists(lang: str):
    p = REPO_ROOT / "docs" / "i18n" / lang / "getting-started.md"
    assert p.exists(), f"missing {lang} translation of getting-started.md"
    content = p.read_text(encoding="utf-8")
    # Each translation should link back to the English master
    assert "docs/getting-started.md" in content or "../../getting-started.md" in content


def test_i18n_readme_lists_all_languages():
    p = REPO_ROOT / "docs" / "i18n" / "README.md"
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    for lang in ("es", "zh-CN", "ja"):
        assert lang in content, f"i18n README doesn't list {lang}"


# ─── CLI subcommand ──────────────────────────────────────────────────────


def test_eval_framework_never_shipped_docs_stay_honest():  # @regression
    """#154: docs must not resurrect false claims that ``llmwiki eval`` shipped."""
    slash_ref = REPO_ROOT / "docs" / "reference" / "slash-commands.md"
    slash_text = slash_ref.read_text(encoding="utf-8")
    assert "llmwiki eval" not in slash_text, (
        "slash-commands.md must not document a non-existent `llmwiki eval` "
        "subcommand — use `llmwiki lint` / `/wiki-lint` for wiki quality"
    )

    demo_slash = (
        REPO_ROOT
        / "demo/raw/docs/slash-commands-reference/slash-commands-reference-01.md"
    )
    if demo_slash.exists():
        assert "llmwiki eval" not in demo_slash.read_text(encoding="utf-8"), (
            "demo slash-commands mirror must not advertise `llmwiki eval`"
        )

    upgrading = (REPO_ROOT / "docs" / "UPGRADING.md").read_text(encoding="utf-8")
    assert "never a live CLI" in upgrading or "never shipped" in upgrading.lower(), (
        "UPGRADING.md must clarify that `llmwiki eval` never shipped"
    )
    for line in upgrading.splitlines():
        if "llmwiki eval" in line:
            assert re.search(r"(?i)never|removed|lint", line), (
                f"UPGRADING.md must only mention `llmwiki eval` in a "
                f"never/removed/lint context: {line!r}"
            )

    matrix = (REPO_ROOT / "docs" / "feature-matrix.md").read_text(encoding="utf-8")
    i4_rows = [ln for ln in matrix.splitlines() if ln.startswith("| I4 |")]
    assert len(i4_rows) == 1, "feature-matrix.md should have exactly one I4 row"
    i4 = i4_rows[0]
    assert "#154" in i4 or "declined" in i4.lower(), (
        "I4 row must cite #154 or mark eval as declined"
    )
    phase = i4.rstrip("|").split("|")[-1].strip()
    assert phase != "v0.3", (
        f"I4 phase must not be bare v0.3 (implies shipped eval); got {phase!r}"
    )

    parser = build_parser()
    for action in parser._actions:
        if hasattr(action, "choices") and action.choices:
            assert "eval" not in action.choices, (
                "CLI must not register an `eval` subcommand that never shipped"
            )
            break
    else:
        raise AssertionError("no subparsers found on the CLI parser")


