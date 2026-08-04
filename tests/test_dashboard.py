"""Tests for the Dataview dashboard template (v1.0, #153)."""

from __future__ import annotations

import argparse
from pathlib import Path

from llmwiki import REPO_ROOT
from llmwiki.cli import cmd_init

DASHBOARD_TEMPLATE = REPO_ROOT / "examples" / "wiki_dashboard.md"


def test_dashboard_template_exists():
    assert DASHBOARD_TEMPLATE.is_file()


def test_dashboard_has_frontmatter():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert 'type: navigation' in text


def test_dashboard_has_recently_updated():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    assert "Recently Updated" in text


def test_dashboard_has_confidence_sections():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    assert "High confidence" in text
    assert "Low confidence" in text


def test_dashboard_has_all_lifecycle_states():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    for state in ["Draft", "Reviewed", "Verified", "Stale", "Archived"]:
        assert state in text, f"missing lifecycle section: {state}"


def test_dashboard_has_by_project():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    assert "By Project" in text


def test_dashboard_has_page_kind_breakdown():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    assert "By Page Kind" in text
    assert "GROUP BY type" in text


def test_dashboard_does_not_group_by_entity_type():
    """#102: the entity-type taxonomy is gone — the dashboard must not teach it."""
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    assert "entity_type" not in text


def test_dashboard_has_open_questions():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    assert "Open Questions" in text


def test_dashboard_has_dataview_blocks():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    # At least 8 dataview code blocks expected
    count = text.count("```dataview")
    assert count >= 8


def test_dashboard_has_connections_section():
    text = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
    assert "## Connections" in text


def test_cmd_init_seeds_dashboard(tmp_path: Path, monkeypatch):
    """cmd_init should copy the dashboard template to wiki/dashboard.md."""
    # #29: cmd_init now honors config.json vault.default_path like sync/build.
    # Isolate from a dev machine's real vault so this exercises the
    # no-vault (REPO_ROOT) path.
    monkeypatch.setattr(
        "llmwiki.config_schedule.load_default_vault_path", lambda: None
    )
    monkeypatch.setattr("llmwiki.cli.REPO_ROOT", tmp_path)
    # Copy the template into the tmp REPO_ROOT
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "wiki_dashboard.md").write_text(
        "---\ntitle: Test\n---\n# Test Dashboard\n", encoding="utf-8"
    )


    args = argparse.Namespace()
    rc = cmd_init(args)
    assert rc == 0
    dashboard = tmp_path / "wiki" / "dashboard.md"
    assert dashboard.is_file()
    assert "Test Dashboard" in dashboard.read_text(encoding="utf-8")
