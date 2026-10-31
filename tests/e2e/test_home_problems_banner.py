"""Home problems banner in a real browser: entries, refresh without rebuild, overdue, themes.

Works on a copy of the session's built site so rewriting its state sidecar
cannot leak into other scenarios.

# @spec: 374-no-silent-automation-failure
# @regression
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_NOW = datetime(2026, 10, 31, 9, 0, tzinfo=UTC)


def _iso(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture()
def site(site_root: Path, tmp_path: Path) -> Path:
    copy = tmp_path / "site"
    shutil.copytree(site_root, copy)
    return copy


def _write_snapshot(site: Path, snapshot: dict) -> None:
    (site / "llmwiki-state.js").write_text(
        "window.LLMWIKI_STATE_SNAPSHOT = " + json.dumps(snapshot) + ";\n", encoding="utf-8"
    )


def _heads(page) -> list[str]:  # type: ignore[no-untyped-def]
    return page.locator("#llmwiki-problems .problems-head").all_inner_texts()


def _scheduled(last_run: datetime | None) -> dict:
    return {
        "marker": 1, "interval_s": 86400, "grace_s": 7200,
        "installed_at": _iso(_NOW - timedelta(days=10)),
        "last_run_at": _iso(last_run) if last_run else None,
        "exit_code": 0, "log_path": "/vault/.llmwiki/last-automation.log",
    }


def test_banner_lists_run_failures_and_lint_at_the_top_of_home(page, site: Path) -> None:  # type: ignore[no-untyped-def]
    _write_snapshot(site, {
        "outcomes": {"parts": {"synth": {
            "scope": "entire", "summary": "did not run: backend claude-cli is not available",
            "detail": "backend claude-cli is not available: <path> does not exist",
            "at": _iso(_NOW), "log_path": "/vault/.llmwiki/last-automation.log",
        }}},
        "ops": {"last_lint_error": "3 issues: 1 errors\n  [error] concepts/A.md: broken wikilink"},
    })
    page.goto((site / "index.html").as_uri())
    banner = page.locator("#llmwiki-problems")
    assert banner.is_visible()
    assert _heads(page) == [
        "Synth — did not run: backend claude-cli is not available",
        "Lint — wiki checks found errors",
    ]
    first = page.evaluate("() => document.querySelector('.queue-widget').firstElementChild.id")
    assert first == "llmwiki-problems"
    assert page.locator(".state-knowledge-table ~ .error-banner").count() == 0


def test_a_new_problem_shows_after_a_refresh_without_a_rebuild(page, site: Path) -> None:  # type: ignore[no-untyped-def]
    _write_snapshot(site, {"outcomes": {"parts": {}}})
    page.goto((site / "index.html").as_uri())
    assert not page.locator("#llmwiki-problems").is_visible()
    _write_snapshot(site, {"outcomes": {"parts": {"build": {
        "scope": "entire", "summary": "failed", "detail": "OSError: No space left on device",
        "at": _iso(_NOW), "log_path": "",
    }}}})
    page.reload()
    assert _heads(page) == ["Build — failed"]


def test_an_open_page_turns_overdue_when_the_deadline_passes(page, site: Path) -> None:  # type: ignore[no-untyped-def]
    _write_snapshot(site, {"outcomes": {"parts": {}, "scheduled": _scheduled(_NOW - timedelta(hours=25))}})
    page.clock.install(time=_NOW)
    page.goto((site / "index.html").as_uri())
    assert not page.locator("#llmwiki-problems").is_visible()
    page.clock.run_for(2 * 3600 * 1000)
    assert _heads(page) == ["Schedule — overdue"]
    detail = page.locator("#llmwiki-problems .problems-detail").inner_text()
    assert f"Expected by: {_iso(_NOW + timedelta(hours=1))}" in detail


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_banner_text_is_readable_in_both_themes(page, site: Path, scheme: str) -> None:  # type: ignore[no-untyped-def]
    _write_snapshot(site, {"outcomes": {"parts": {"build": {
        "scope": "entire", "summary": "failed", "at": _iso(_NOW)}}}})
    page.emulate_media(color_scheme=scheme)
    page.goto((site / "index.html").as_uri())
    colour = page.evaluate("() => getComputedStyle(document.getElementById('llmwiki-problems')).color")
    assert colour == ("rgb(185, 28, 28)" if scheme == "light" else "rgb(248, 113, 113)")
