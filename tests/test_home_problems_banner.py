"""Home problems banner: one red banner at the top of Home for every current problem.

Runs the page's own banner functions under ``node`` with a stub DOM (skipped
when node is absent), so the assertions cover what a reader sees, not the
shape of the JS source.

# @spec: 374-no-silent-automation-failure
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from llmwiki.raw_docs_site import render_dashboard_body
from llmwiki.render import js

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")

_NOW_MS = 1_793_000_000_000  # a fixed browser clock for every run

_DOM_STUB = """
function mkEl(tag) {
  return {
    tag: tag, className: "", textContent: "", hidden: false, attrs: {}, children: [],
    setAttribute: function (k, v) { this.attrs[k] = String(v); },
    appendChild: function (c) { this.children.push(c); return c; },
    removeChild: function (c) { this.children.splice(this.children.indexOf(c), 1); return c; },
    get firstChild() { return this.children[0] || null; }
  };
}
var document = { createElement: mkEl };
var REPORTED = [];
var window = { __llmwikiReportError: function (ctx, e) { REPORTED.push(ctx + ": " + e.message); } };
function formatTs(ts) { return ts ? ts : "never"; }
function flatten(el) {
  return {
    hidden: el.hidden,
    entries: (el.children[1] ? el.children[1].children : []).map(function (li) {
      return {
        part: li.attrs["data-part"],
        lines: li.children.map(function (c) { return c.className + "=" + c.textContent; })
      };
    }),
    title: el.children[0] ? el.children[0].textContent : null
  };
}
"""


def _js_block(source: str, marker: str) -> str:
    """The declaration starting at `marker`, up to its balanced closing brace."""
    start = source.index(marker)
    depth = 0
    for i in range(start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
    raise AssertionError(f"unbalanced braces after {marker!r}")


def _js_line(source: str, marker: str) -> str:
    """The single source line starting at `marker`."""
    start = source.index(marker)
    return source[start:source.index("\n", start)]


def _banner_functions() -> str:
    return "\n".join([
        _js_line(js.JS, "var PROBLEM_DETAIL_MAX_LINES ="),
        _js_line(js.JS, "var PROBLEM_PARTS ="),
        _js_block(js.JS, "function clipLines(text, max) {"),
        _js_block(js.JS, "function isoSeconds(ms) {"),
        _js_block(js.JS, "function scheduleOverdue(scheduled, nowMs) {"),
        _js_block(js.JS, "function problemEntries(snapshot, nowMs) {"),
        _js_block(js.JS, "function renderProblemsBanner(root, snapshot, nowMs) {"),
    ])


def _render(snapshot_js: str, tmp_path: Path, now_ms: int = _NOW_MS) -> dict:
    """Render the banner for a snapshot (a JS expression) at a browser clock and return what it shows."""
    script = tmp_path / "banner.js"
    script.write_text(
        "\n".join([
            _DOM_STUB,
            _banner_functions(),
            "var root = mkEl('div'); root.hidden = true;",
            f"renderProblemsBanner(root, {snapshot_js}, {now_ms});",
            "console.log(JSON.stringify({view: flatten(root), reported: REPORTED}));",
        ]),
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(script)], capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def _snapshot(**ops: str) -> str:
    return json.dumps({"ops": ops})


def test_banner_mount_is_the_first_thing_in_the_home_widget():
    """The banner sits above the Automation panel and the pipeline tables, hidden until filled."""
    body = render_dashboard_body([], 0, automation_html='<div class="automation-panel"></div>')
    mount = body.index('id="llmwiki-problems"')
    assert body.index('class="queue-widget"') < mount < body.index('class="automation-panel"')
    assert mount < body.index("Pipeline state")
    tag = body[body.rindex("<", 0, mount):body.index(">", mount)]
    assert 'role="alert"' in tag
    assert "hidden" in tag


@needs_node
def test_lint_errors_show_as_a_lint_entry_in_the_banner(tmp_path):
    note = "252 issues: 2 errors\n  [error] concepts/A.md: broken wikilink [[B]]"
    out = _render(_snapshot(last_lint_error=note, last_lint_run_at="2026-10-31T05:34:00Z"), tmp_path)
    view = out["view"]
    assert view["hidden"] is False
    assert view["title"] == "1 problem needs attention"
    [entry] = view["entries"]
    assert entry["part"] == "lint"
    assert entry["lines"][0] == "problems-head=Lint — wiki checks found errors"
    assert "2026-10-31T05:34:00Z" in entry["lines"][1]
    assert entry["lines"][2] == "problems-detail=" + note


@needs_node
def test_warnings_only_lint_note_leaves_the_banner_hidden(tmp_path):
    """#256: a fail-on-warnings note without [error] lines is not red."""
    out = _render(_snapshot(last_lint_error="3 issues: 0 errors\n  [warning] x.md: stale"), tmp_path)
    assert out["view"] == {"hidden": True, "entries": [], "title": None}


@needs_node
def test_no_problems_leaves_the_banner_hidden(tmp_path):
    out = _render(_snapshot(), tmp_path)
    assert out["view"]["hidden"] is True
    assert out["view"]["entries"] == []


@needs_node
def test_long_detail_shows_ten_lines_then_ellipsis(tmp_path):
    note = "\n".join(["[error] head"] + [f"line {i}" for i in range(1, 30)])
    out = _render(_snapshot(last_lint_error=note), tmp_path)
    detail = out["view"]["entries"][0]["lines"][-1].removeprefix("problems-detail=")
    assert detail.split("\n") == note.split("\n")[:10] + ["…"]


@needs_node
def test_error_text_is_shown_as_text_not_markup(tmp_path):
    note = '[error] <img src=x onerror="alert(1)"> & <b>bold</b>'
    out = _render(_snapshot(last_lint_error=note), tmp_path)
    assert out["view"]["entries"][0]["lines"][-1] == "problems-detail=" + note
    assert "innerHTML" not in _js_block(js.JS, "function renderProblemsBanner(root, snapshot, nowMs) {")


@needs_node
def test_unreadable_snapshot_is_reported_on_the_page(tmp_path):
    """A malformed snapshot surfaces through the site error bar instead of failing silently."""
    out = _render("{ get ops() { throw new Error('bad ops'); } }", tmp_path)
    assert out["view"]["hidden"] is True
    assert out["reported"] == ["Home problems banner unavailable: bad ops"]


@needs_node
def test_failed_parts_show_in_order_with_summary_time_and_log(tmp_path):
    snapshot = {
        "outcomes": {"parts": {
            "build": {"scope": "entire", "summary": "failed", "at": "2026-10-31T05:04:00Z",
                      "detail": "OSError: disk full", "log_path": "/v/.llmwiki/last-automation.log"},
            "synth": {"scope": "entire", "summary": "did not run: backend claude-cli is not available",
                      "at": "2026-10-31T05:02:00Z", "detail": "claude was not found on PATH",
                      "log_path": "/v/.llmwiki/last-automation.log"},
        }},
        "ops": {"last_lint_error": "[error] a.md: broken"},
    }
    out = _render(json.dumps(snapshot), tmp_path)
    view = out["view"]
    assert view["title"] == "3 problems need attention"
    assert [e["part"] for e in view["entries"]] == ["synth", "build", "lint"]
    synth = view["entries"][0]["lines"]
    assert synth[0] == "problems-head=Synth — did not run: backend claude-cli is not available"
    assert synth[1] == "problems-meta=2026-10-31T05:02:00Z · log: /v/.llmwiki/last-automation.log"
    assert synth[2] == "problems-detail=claude was not found on PATH"


# ─── Schedule entries ─────────────────────────────────────────────────────

_DAY_MS = 86_400_000
_HOUR_MS = 3_600_000


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _scheduled(*, last_run_ms: int | None, installed_ms: int = _NOW_MS - 10 * _DAY_MS) -> str:
    return json.dumps({"outcomes": {"scheduled": {
        "marker": 1, "interval_s": 86400, "grace_s": 7200,
        "installed_at": _iso(installed_ms),
        "last_run_at": _iso(last_run_ms) if last_run_ms is not None else None,
        "exit_code": 0, "log_path": "/v/.llmwiki/last-automation.log",
    }}})


@needs_node
def test_a_scheduled_run_two_days_old_is_overdue(tmp_path):
    last = _NOW_MS - 2 * _DAY_MS
    [entry] = _render(_scheduled(last_run_ms=last), tmp_path)["view"]["entries"]
    assert entry["part"] == "schedule"
    assert entry["lines"][0] == "problems-head=Schedule — overdue"
    detail = entry["lines"][-1]
    assert f"Last scheduled run: {_iso(last)}" in detail
    assert f"Expected by: {_iso(last + _DAY_MS + 2 * _HOUR_MS)}" in detail


@needs_node
def test_a_run_within_one_interval_and_the_grace_is_not_overdue(tmp_path):
    out = _render(_scheduled(last_run_ms=_NOW_MS - _DAY_MS - _HOUR_MS), tmp_path)
    assert out["view"]["hidden"] is True


@needs_node
def test_a_schedule_that_never_ran_counts_from_its_install(tmp_path):
    out = _render(_scheduled(last_run_ms=None, installed_ms=_NOW_MS - 3 * _DAY_MS), tmp_path)
    [entry] = out["view"]["entries"]
    assert "No scheduled run since setup at" in entry["lines"][-1]


@needs_node
def test_an_open_page_turns_overdue_when_the_clock_passes_the_deadline(tmp_path):
    """The minute re-check re-renders the same snapshot with a later clock."""
    snapshot = _scheduled(last_run_ms=_NOW_MS - _DAY_MS)
    assert _render(snapshot, tmp_path)["view"]["hidden"] is True
    later = _render(snapshot, tmp_path, now_ms=_NOW_MS + 3 * _HOUR_MS)
    assert [e["part"] for e in later["view"]["entries"]] == ["schedule"]
    load_handler = _js_block(js.JS, 'document.addEventListener("DOMContentLoaded", function () {\n    renderQueueTrace();')
    assert "setInterval(" in load_handler
    assert "renderProblemsBanner(problemsMount, window.LLMWIKI_STATE_SNAPSHOT, Date.now())" in load_handler
    assert "60000" in load_handler


@needs_node
def test_a_schedule_without_the_marker_is_never_called_overdue(tmp_path):
    snapshot = json.dumps({"outcomes": {"scheduled": {"last_run_at": _iso(_NOW_MS - 9 * _DAY_MS)}}})
    assert _render(snapshot, tmp_path)["view"]["hidden"] is True


@needs_node
def test_an_outdated_setup_asks_to_rerun_install_automation(tmp_path):
    snapshot = json.dumps({"outcomes": {"setup_outdated": {
        "at": "2026-10-31T05:01:00Z", "detail": "Re-run `llmwiki install-automation` once."}}})
    [entry] = _render(snapshot, tmp_path)["view"]["entries"]
    assert entry["lines"][0] == "problems-head=Schedule — setup outdated: re-run llmwiki install-automation"
