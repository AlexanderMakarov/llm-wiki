"""Tests for #108 FR7 — the map's side panel says what the topic page says.

`showTopicPanel()` used to show session and connection counts only, so
triaging a bubble meant opening its page. It now names the topic's kind and
its freshness, with activity (session-derived) kept distinct from review (the
backing page's own date), each freshness row dropped when the node lacks its
field, and the kind row always present — naming the unclassified state when no
wiki page describes the topic.

The rows are built by JS at click time, so a substring assertion on
`graph-viewer.js` would prove the code is present, not that it renders. These
tests lift the panel helpers out of the generated file and run them under
`node`, asserting on the rows they actually produce. They skip when `node` is
absent; the label-parity test below is pure Python and always runs.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from llmwiki.graph import write_html
from llmwiki.topics import KIND_OTHER, TOPIC_KIND_FOLDERS
from llmwiki.topics_page import KIND_OTHER_LABEL, kind_label

needs_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="node not on PATH"
)

_STAT_RE = re.compile(r'<div class="stat"><span>(.*?)</span><b>(.*?)</b></div>')


@pytest.fixture(scope="module")
def viewer_js(tmp_path_factory: pytest.TempPathFactory) -> str:
    """The generated `graph-viewer.js` for an empty graph."""
    out = tmp_path_factory.mktemp("graph") / "graph.html"
    write_html({"nodes": [], "edges": [], "stats": {}}, out)
    return (out.parent / "graph-viewer.js").read_text(encoding="utf-8")


def _js_block(js: str, marker: str) -> str:
    """The declaration starting at `marker`, up to its balanced closing brace."""
    start = js.index(marker)
    depth = 0
    for i in range(start, len(js)):
        if js[i] == "{":
            depth += 1
        elif js[i] == "}":
            depth -= 1
            if depth == 0:
                return js[start : i + 1]
    raise AssertionError(f"unbalanced braces after {marker!r}")


def _panel_rows(viewer_js: str, nodes: list[dict], tmp_path: Path) -> list[list[tuple]]:
    """Run the panel's row builder over `nodes`, returning `(label, value)` rows."""
    parts = [
        _js_block(viewer_js, "const KIND_LABELS = {"),
        _js_block(viewer_js, "const kindLabelOne = k => {"),
        _js_block(viewer_js, "function escapeHtml(s) {"),
        _js_block(viewer_js, "function statRow(label, value) {"),
        _js_block(viewer_js, "function topicActivity(node) {"),
        _js_block(viewer_js, "function topicIdentityRows(node) {"),
        re.search(r"const kindLabel = .*?;", viewer_js).group(0),
        f"console.log(JSON.stringify({json.dumps(nodes)}.map(topicIdentityRows)));",
    ]
    script = tmp_path / "panel.js"
    script.write_text("\n".join(parts), encoding="utf-8")
    proc = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, check=True
    )
    return [_STAT_RE.findall(html) for html in json.loads(proc.stdout)]


@needs_node
def test_panel_names_the_kind_and_both_freshness_facts(viewer_js: str, tmp_path: Path):
    node = {
        "id": "Ruff",
        "kind": "entities",
        "first_seen": "2026-01-02",
        "last_seen": "2026-03-04",
        "last_updated": "2026-03-09",
    }
    (rows,) = _panel_rows(viewer_js, [node], tmp_path)
    assert rows == [
        ("Kind", "Entity"),
        ("Active", "2026-01-02 – 2026-03-04"),
        ("Reviewed", "2026-03-09"),
    ]


@needs_node
def test_a_topic_seen_once_shows_a_single_date_not_a_range(
    viewer_js: str, tmp_path: Path
):
    node = {"kind": "concepts", "first_seen": "2026-02-02", "last_seen": "2026-02-02"}
    (rows,) = _panel_rows(viewer_js, [node], tmp_path)
    assert rows == [("Kind", "Concept"), ("Active", "2026-02-02")]


@needs_node
def test_a_topic_no_page_describes_is_labelled_unclassified(
    viewer_js: str, tmp_path: Path
):
    """The panel names the unclassified state as the topic page's chip does.

    Dropping the row would leave a reader unable to tell an unclassified topic
    from a panel that failed to render its kind (FR7).
    """
    node = {"kind": KIND_OTHER, "first_seen": "2026-01-02", "last_seen": "2026-01-02"}
    (rows,) = _panel_rows(viewer_js, [node], tmp_path)
    assert rows == [("Kind", KIND_OTHER_LABEL), ("Active", "2026-01-02")]


@needs_node
def test_each_freshness_row_is_omitted_independently(viewer_js: str, tmp_path: Path):
    nodes = [
        {"kind": "projects", "last_updated": "2026-04-01"},  # no session dates
        {"kind": "projects", "first_seen": "2026-01-01", "last_seen": "2026-02-01"},
        {"kind": "projects"},
        {"kind": KIND_OTHER},
    ]
    reviewed_only, active_only, kind_only, unclassified = _panel_rows(
        viewer_js, nodes, tmp_path
    )
    assert [label for label, _ in reviewed_only] == ["Kind", "Reviewed"]
    assert [label for label, _ in active_only] == ["Kind", "Active"]
    assert [label for label, _ in kind_only] == ["Kind"]
    # Kind survives every freshness field going missing — only the dates drop.
    assert unclassified == [("Kind", KIND_OTHER_LABEL)]


@needs_node
def test_panel_values_are_escaped(viewer_js: str, tmp_path: Path):
    node = {"kind": "entities", "last_updated": '<img src=x onerror="1">'}
    (rows,) = _panel_rows(viewer_js, [node], tmp_path)
    assert ("Reviewed", "&lt;img src=x onerror=&quot;1&quot;&gt;") in rows


@needs_node
def test_panel_kind_labels_match_the_static_topic_page(viewer_js: str, tmp_path: Path):
    """The panel and the page must name a kind identically (FR7).

    The viewer derives its singular labels from the legend's plural ones, so
    this pins the derivation against `topics_page.kind_label()` — the static
    page's authority — for every kind a node can carry.
    """
    kinds = sorted(TOPIC_KIND_FOLDERS | {KIND_OTHER})
    rows = _panel_rows(viewer_js, [{"kind": k} for k in kinds], tmp_path)
    got = {k: (r[0][1] if r else "") for k, r in zip(kinds, rows, strict=True)}
    assert got == {k: kind_label(k) for k in kinds}


def test_freshness_fields_survive_the_vis_node_mapping(viewer_js: str):
    """The panel reads the vis node, not the raw graph node.

    `GRAPH.nodes` is mapped onto vis's own node objects and only the keys named
    in that mapping survive, so a freshness field missing there renders nothing
    however correct the panel code is.
    """
    mapping = _js_block(viewer_js, "const nodes = new vis.DataSet(")
    topic_branch = mapping[mapping.index("if (TOPIC) {") : mapping.index("const isOrphan")]
    for key in ("first_seen", "last_seen", "last_updated"):
        assert f"{key}: n.{key}," in topic_branch


def test_the_panel_row_shape_matches_the_existing_stats(viewer_js: str):
    """New rows reuse the panel's `.stat` markup rather than inventing one."""
    assert '<div class="stat"><span>' in _js_block(
        viewer_js, "function statRow(label, value) {"
    )


def test_panel_detail_failures_surface_on_the_page(viewer_js: str):
    """CONTRIBUTING: a viewer failure must reach `__llmwikiReportError`."""
    panel = _js_block(viewer_js, "function showTopicPanel(node) {")
    assert "topicIdentityRows(node)" in panel
    assert "reportGraphError(" in panel
