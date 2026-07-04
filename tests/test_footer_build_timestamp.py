"""Tests for the build datetime shown in the site footer (#15).

``page_foot`` should render the build's UTC timestamp — sourced from the
module-level ``_BUILD_NOW`` cache set by ``render_freshness`` — so a page
records when the static site was generated. When ``_BUILD_NOW`` hasn't been
populated yet (e.g. ``page_foot`` called before any freshness badge render),
the fragment must be omitted rather than crash.
"""

from __future__ import annotations

from datetime import datetime

from llmwiki import build as build_mod
from llmwiki.build import page_foot


def test_page_foot_includes_build_timestamp(monkeypatch):
    monkeypatch.setattr(build_mod, "_BUILD_NOW", datetime(2026, 7, 4, 12, 34, 56))
    html = page_foot(js_prefix="")
    assert "built 2026-07-04 12:34 UTC" in html


def test_page_foot_omits_timestamp_when_build_now_unset(monkeypatch):
    monkeypatch.setattr(build_mod, "_BUILD_NOW", None)
    html = page_foot(js_prefix="")
    assert "built" not in html
