"""Home dashboard layout — pipeline freshness, metrics, automation (#321)."""

from __future__ import annotations

from pathlib import Path

from llmwiki.build import render_automation_details, render_automation_notice
from llmwiki.raw_docs_site import render_dashboard_body
from llmwiki.viz_wiki_value import render_home_metrics_strip


def test_home_metrics_missing_tokens_not_zero():
    """Missing token telemetry shows em dash, not a measured zero."""
    html = render_home_metrics_strip({}, wiki_page_count=3, metas_by_project={})
    assert "Session tokens" in html
    assert "—" in html
    assert "No recorded session tokens yet" in html
    assert "Payoff / page" in html


def test_home_metrics_payoff_matches_value_summary():
    usage = {
        "total_calls": 4,
        "per_tool": {
            "wiki_search": {"calls": 6, "items_returned": 0, "zero_hits": 0},
        },
    }
    html = render_home_metrics_strip(usage, wiki_page_count=3)
    assert "2.00" in html
    assert "analytics.html" in html


def test_automation_notice_when_unconfigured(tmp_path: Path):
    notice = render_automation_notice(tmp_path)
    assert "No automation configured" in notice
    assert "install-automation" in notice
    assert render_automation_details(tmp_path) == ""


def test_dashboard_automation_details_in_template_not_above_pipeline(tmp_path: Path):
    body = render_dashboard_body(
        [],
        0,
        automation_notice_html=render_automation_notice(tmp_path),
        automation_details_html="<ul><li>Daily job</li></ul>",
        home_metrics_html=render_home_metrics_strip({}, wiki_page_count=0),
    )
    assert body.index("Pipeline state") < body.index("llmwiki-automation-details")
    assert "automation-panel" not in body
    assert '<template id="llmwiki-automation-details">' in body
