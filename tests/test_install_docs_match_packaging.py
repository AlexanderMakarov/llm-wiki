"""Primary install guidance must name the published distribution (#210).

Live install entry points must tell users (or CI) to install the name in
``pyproject.toml`` / ``llmwiki.install_hint.DIST_NAME``. Pinning exact commands
on the files that teach install is real coverage; a repo-wide "≥ N matches"
grep is not.
"""

from __future__ import annotations

import re
import tomllib

import pytest

from llmwiki import REPO_ROOT
from llmwiki.install_hint import DIST_NAME, pip_install_command

#: Markdown / prose that teach a human how to `pip install` this project.
DOC_INSTALL_FILES = (
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "docs/tutorials/01-installation.md",
)


def _pyproject_name() -> str:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["name"]


def test_dist_name_matches_pyproject():
    assert DIST_NAME == _pyproject_name()


@pytest.mark.parametrize("rel", DOC_INSTALL_FILES)
def test_doc_install_entry_points_use_pip_install_command(rel: str):
    text = (REPO_ROOT / rel).read_text(encoding="utf-8")
    bare = pip_install_command()
    assert bare in text, f"{rel} missing exact `{bare}` from pip_install_command()"


def test_installation_tutorial_is_one_install_step_with_options():
    text = (REPO_ROOT / "docs/tutorials/01-installation.md").read_text(encoding="utf-8")
    assert "## Step 2 — Install (pick one)" in text
    assert "### Option A — PyPI" in text
    assert "### Option B — Homebrew" in text
    assert "### Option C — Clone" in text
    # Must not reintroduce parallel "Step N — Install from …" siblings.
    assert not re.search(r"^## Step \d+ — Install from ", text, re.MULTILINE)


def test_action_defaults_package_input_to_dist_name():
    text = (REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    assert f'default: "{DIST_NAME}"' in text
    assert 'PACKAGE: ${{ inputs.package }}' in text
    assert 'pip install "$PACKAGE"' in text


def test_release_smoke_reads_dist_name_from_pyproject():
    text = (REPO_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    smoke_start = text.index("\n  smoke:")
    smoke = text[smoke_start : text.index("\n  sign:", smoke_start)]
    assert "tomllib" in smoke
    assert '["project"]["name"]' in smoke
    assert "${dist}==${version}" in smoke


def test_upstream_llm_notebook_is_not_offered_in_doc_install_files():
    notebook_install = re.compile(
        r"""pip \s+ install \s+
            (?:(?:-U|--upgrade|--quiet|-q)\s+)*
            ['\"]?llm-notebook(?:\[[^\]]*\])?['\"]?
        """,
        re.VERBOSE,
    )
    offenders: list[str] = []
    for rel in DOC_INSTALL_FILES:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if notebook_install.search(line):
                offenders.append(f"{rel}:{lineno}")
    assert not offenders, (
        "install docs still offer upstream `llm-notebook`: " + ", ".join(offenders)
    )
