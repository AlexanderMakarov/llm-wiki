"""Tests for the Homebrew tap kit (v1.1.0 · #102).

The formula gets copied into a separate `homebrew-tap` repo that the
maintainer owns — we can't reach that from CI. What we CAN test:

- The formula in this repo stays syntactically + semantically sound.
- The bump script is executable and enforces its input contract.
- The auto-bump workflow stays aligned with the bump script + docs.
- The setup doc documents every user-facing command it mentions.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT

FORMULA = REPO_ROOT / "homebrew" / "llmwiki.rb"
BUMP_SCRIPT = REPO_ROOT / "scripts" / "bump-homebrew-formula.sh"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "homebrew-bump.yml"
DOC = REPO_ROOT / "docs" / "deploy" / "homebrew-setup.md"


@pytest.fixture(scope="module")
def formula() -> str:
    return FORMULA.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def bump_script() -> str:
    return BUMP_SCRIPT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def doc() -> str:
    return DOC.read_text(encoding="utf-8")


# ─── Formula shape ────────────────────────────────────────────────────


def test_formula_class_name_matches_filename(formula: str):
    # Homebrew derives the Ruby class name from the formula's filename.
    # `llmwiki.rb` → `class Llmwiki`.
    assert re.search(r"^class Llmwiki < Formula", formula, re.MULTILINE), (
        "formula class must be `Llmwiki` (camelcase of the filename)"
    )


def test_formula_has_required_fields(formula: str):
    for field in ("desc ", "homepage ", "url ", "sha256 ", "license "):
        assert field in formula, f"formula missing `{field.strip()}`"


def test_formula_url_points_at_llm_wiki_release_tarball(formula: str):
    m = re.search(r'^  url "([^"]+)"', formula, re.MULTILINE)
    assert m, "formula has no url line"
    url = m.group(1)
    assert url.startswith(
        "https://github.com/Pratiyush/llm-wiki/archive/refs/tags/v"
    ), f"unexpected url {url!r}; bump-homebrew-formula.sh rewrites this"
    assert url.endswith(".tar.gz"), "formula url must be the .tar.gz archive"


def test_formula_sha_is_64_hex_or_placeholder(formula: str):
    m = re.search(r'^  sha256 "([^"]+)"', formula, re.MULTILINE)
    assert m, "formula has no sha256 line"
    sha = m.group(1)
    # Two acceptable states: real 64-hex digest (after bump) or the
    # documented placeholder (before a tag ships).
    assert re.fullmatch(r"[0-9a-f]{64}", sha) or "PLACEHOLDER" in sha, (
        f"sha256 value {sha!r} is neither a 64-hex digest nor the "
        "documented PLACEHOLDER — check the bump script output"
    )


def test_formula_test_block_runs_llmwiki_commands(formula: str):
    # Homebrew runs the `test do ... end` block on install. We exercise
    # the subcommands that matter to users — `--version` and `adapters`.
    assert 'system bin/"llmwiki", "--version"' in formula
    assert 'system bin/"llmwiki", "adapters"' in formula


def test_formula_depends_on_python_312(formula: str):
    assert 'depends_on "python@3.12"' in formula


# ─── Bump script ──────────────────────────────────────────────────────


def test_bump_script_is_executable():
    assert BUMP_SCRIPT.is_file()
    assert os.access(BUMP_SCRIPT, os.X_OK), (
        "scripts/bump-homebrew-formula.sh must be executable; "
        "run `chmod +x scripts/bump-homebrew-formula.sh`"
    )


def test_bump_script_rejects_missing_argument(tmp_path: Path):
    result = subprocess.run(
        [str(BUMP_SCRIPT)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode != 0
    assert "usage" in result.stderr.lower()


def test_bump_script_rejects_non_semver_tag(tmp_path: Path):
    result = subprocess.run(
        [str(BUMP_SCRIPT), "not-a-version"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode != 0
    assert "semver" in result.stderr.lower()


def test_bump_script_uses_right_tarball_url(bump_script: str):
    # Must match the URL pattern the formula test guards.
    assert (
        "https://github.com/Pratiyush/llm-wiki/archive/refs/tags/${tag}.tar.gz"
        in bump_script
    )


def test_bump_script_handles_macos_and_linux_sed(bump_script: str):
    # macOS/BSD sed needs `-i ''`, GNU sed needs `-i` without the arg.
    # Both branches must exist so the script runs on devs' machines
    # (macOS) and CI (Linux).
    assert "Darwin" in bump_script
    assert "sed -i ''" in bump_script
    assert re.search(r"sed -i -E", bump_script)


# ─── Auto-bump workflow ───────────────────────────────────────────────


def test_workflow_triggers_on_version_tags(workflow: str):
    assert 'tags:' in workflow
    assert '"v*.*.*"' in workflow or "'v*.*.*'" in workflow


def test_workflow_supports_manual_dispatch(workflow: str):
    assert "workflow_dispatch:" in workflow


def test_workflow_calls_bump_script(workflow: str):
    assert "scripts/bump-homebrew-formula.sh" in workflow


def test_workflow_gracefully_handles_missing_secret(workflow: str):
    # When HOMEBREW_TAP_TOKEN isn't set, the job must still succeed —
    # otherwise every release tag turns the workflow red.
    assert "has_token" in workflow
    assert "HOMEBREW_TAP_TOKEN" in workflow
    # Conditional push step
    assert "if: steps.check_token.outputs.has_token == 'true'" in workflow


def test_workflow_targets_homebrew_tap_repo(workflow: str):
    assert "Pratiyush/homebrew-tap" in workflow


# ─── Setup doc ────────────────────────────────────────────────────────


def test_doc_covers_tap_repo_creation(doc: str):
    # Must mention the literal repo name and the `homebrew-` prefix rule.
    assert "homebrew-tap" in doc
    # The prefix is load-bearing: Homebrew requires the repo name to
    # start with `homebrew-` for `brew tap` to accept it.
    assert re.search(
        r"start with.*homebrew-|name.*must.*homebrew-|homebrew-.*must",
        doc,
        re.IGNORECASE,
    ), "doc should flag that the tap repo name must start with `homebrew-`"


def test_doc_covers_on_every_release_flow(doc: str):
    assert "On every new release" in doc
    assert "bump-homebrew-formula.sh" in doc


def test_doc_covers_auto_bump_optional_path(doc: str):
    assert "HOMEBREW_TAP_TOKEN" in doc
    assert "gh secret set" in doc


def test_doc_covers_troubleshooting(doc: str):
    assert "Troubleshooting" in doc
    # Three documented failure modes
    for k in ("404", "brew test", "class name"):
        assert k in doc, f"doc missing troubleshooting section for {k!r}"


def test_doc_cross_links_pypi_sibling(doc: str):
    # Both deploy docs should cross-reference each other so users
    # discover the PyPI path from the Homebrew doc and vice versa.
    assert "docs/deploy/pypi-publishing.md" in doc or "pypi-publishing" in doc
