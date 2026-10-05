"""Documents sidebar quick filter (#305 Slice 4).

Lifts the DOM-free ``LLMWIKI_DOCTREE_FILTER`` block from
``llmwiki/render/js.py`` and runs it under ``node`` — same harness pattern as
``test_248_palette_match.py``. Covers starts-with-then-contains order, ancestor
retention, substring highlight, and the empty-state copy.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from llmwiki.render.css import CSS
from llmwiki.render.js import JS

_BEGIN = "// ─── Documents tree filter (#305) ── BEGIN"
_END = "// ─── Documents tree filter (#305) ── END"

_DRIVER = """const fs = require("fs");
const F = require("./filter.cjs");
const input = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const op = input.op;
let out;
if (op === "matchKind") {
  out = F.matchKind(input.label, input.queryLower);
} else if (op === "highlight") {
  out = F.highlightLabel(input.label, input.queryLower);
} else if (op === "filter") {
  out = F.filterNode(input.tree, input.queryLower);
} else if (op === "render") {
  out = F.renderFiltered(input.tree, input.prefix || "", input.activeRel || "", input.query);
} else if (op === "emptyCopy") {
  out = F.EMPTY_COPY;
} else {
  throw new Error("unknown op: " + op);
}
process.stdout.write(JSON.stringify(out));
"""

_SAMPLE_TREE = {
    "folders": [
        {
            "name": "notes",
            "folders": [
                {
                    "name": "deep",
                    "folders": [],
                    "files": [
                        {
                            "label": "Alpha Plan",
                            "href": "raw/notes/deep/alpha-plan.html",
                            "rel": "notes/deep/alpha-plan.md",
                            "id": "doc:notes/deep/alpha-plan",
                        },
                        {
                            "label": "Other",
                            "href": "raw/notes/deep/other.html",
                            "rel": "notes/deep/other.md",
                            "id": "doc:notes/deep/other",
                        },
                    ],
                }
            ],
            "files": [
                {
                    "label": "xAlpha memo",
                    "href": "raw/notes/xalpha.html",
                    "rel": "notes/xalpha.md",
                    "id": "doc:notes/xalpha",
                },
                {
                    "label": "Beta",
                    "href": "raw/notes/beta.html",
                    "rel": "notes/beta.md",
                    "id": "doc:notes/beta",
                },
            ],
        },
        {
            "name": "emptyish",
            "folders": [],
            "files": [
                {
                    "label": "Zeta",
                    "href": "raw/emptyish/zeta.html",
                    "rel": "emptyish/zeta.md",
                    "id": "doc:emptyish/zeta",
                }
            ],
        },
    ],
    "files": [
        {
            "label": "Alpha root",
            "href": "raw/alpha-root.html",
            "rel": "alpha-root.md",
            "id": "doc:alpha-root",
        },
        {
            "label": "Gamma",
            "href": "raw/gamma.html",
            "rel": "gamma.md",
            "id": "doc:gamma",
        },
    ],
}


def _filter_source() -> str:
    start = JS.index(_BEGIN)
    end = JS.index(_END)
    return JS[start:end]


@pytest.fixture(scope="module")
def node_runner(tmp_path_factory: pytest.TempPathFactory):
    node = shutil.which("node")
    if node is None:  # pragma: no cover - environment-dependent
        pytest.skip("node is not installed — doctree filter JS cannot be exercised")
    work = tmp_path_factory.mktemp("doctree_filter")
    (work / "filter.cjs").write_text(
        _filter_source() + "\nmodule.exports = LLMWIKI_DOCTREE_FILTER;\n",
        encoding="utf-8",
    )
    (work / "driver.cjs").write_text(_DRIVER, encoding="utf-8")
    counter = {"n": 0}

    def run(payload: dict):
        counter["n"] += 1
        arg = work / f"in-{counter['n']}.json"
        arg.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run(
            [node, str(work / "driver.cjs"), str(arg)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)

    return run


def test_empty_copy_exact(node_runner) -> None:
    assert node_runner({"op": "emptyCopy"}) == "No documents match"


def test_match_kind_starts_contains_none(node_runner) -> None:
    assert node_runner({"op": "matchKind", "label": "Alpha Plan", "queryLower": "alpha"}) == "starts"
    assert node_runner({"op": "matchKind", "label": "xAlpha", "queryLower": "alpha"}) == "contains"
    assert node_runner({"op": "matchKind", "label": "Beta", "queryLower": "alpha"}) is None


def test_filter_order_starts_before_contains(node_runner) -> None:
    """Root files: starts-with match before contains-only when sorted."""
    # Put both at the same folder level to assert sibling order.
    tree = {
        "folders": [],
        "files": [
            {"label": "xAlpha late", "href": "a.html", "rel": "a.md", "id": "a"},
            {"label": "Alpha early", "href": "b.html", "rel": "b.md", "id": "b"},
            {"label": "something Alpha mid", "href": "c.html", "rel": "c.md", "id": "c"},
            {"label": "Alpha again", "href": "d.html", "rel": "d.md", "id": "d"},
            {"label": "Nope", "href": "e.html", "rel": "e.md", "id": "e"},
        ],
    }
    out = node_runner({"op": "filter", "tree": tree, "queryLower": "alpha"})
    labels = [f["label"] for f in out["files"]]
    assert labels == ["Alpha early", "Alpha again", "xAlpha late", "something Alpha mid"]


def test_filter_keeps_ancestors_hides_non_matches(node_runner) -> None:
    out = node_runner({"op": "filter", "tree": _SAMPLE_TREE, "queryLower": "alpha plan"})
    # Only the notes → deep path to Alpha Plan; emptyish and sibling Other gone.
    assert [f["name"] for f in out["folders"]] == ["notes"]
    notes = out["folders"][0]
    assert notes["files"] == []  # xAlpha / Beta do not match "alpha plan"
    assert [f["name"] for f in notes["folders"]] == ["deep"]
    deep = notes["folders"][0]
    assert [f["label"] for f in deep["files"]] == ["Alpha Plan"]
    assert out["files"] == []  # root Alpha root starts with "alpha" but not "alpha plan"


def test_filter_ancestor_of_nested_contains(node_runner) -> None:
    out = node_runner({"op": "filter", "tree": _SAMPLE_TREE, "queryLower": "alpha"})
    folder_names = [f["name"] for f in out["folders"]]
    assert folder_names == ["notes"]  # emptyish/Zeta dropped
    notes = out["folders"][0]
    assert [f["label"] for f in notes["files"]] == ["xAlpha memo"]
    assert [f["name"] for f in notes["folders"]] == ["deep"]
    deep_labels = [f["label"] for f in notes["folders"][0]["files"]]
    assert deep_labels == ["Alpha Plan"]
    root_labels = [f["label"] for f in out["files"]]
    assert root_labels == ["Alpha root"]  # starts-with; Gamma dropped


def test_highlight_wraps_substring(node_runner) -> None:
    html = node_runner({"op": "highlight", "label": "Alpha Plan", "queryLower": "pha"})
    assert html == 'Al<mark class="doctree-filter-hit">pha</mark> Plan'
    multi = node_runner({"op": "highlight", "label": "aa AA", "queryLower": "a"})
    assert multi.count('class="doctree-filter-hit"') == 4


def test_render_opens_ancestors_and_highlights(node_runner) -> None:
    html = node_runner(
        {
            "op": "render",
            "tree": _SAMPLE_TREE,
            "query": "Alpha",
            "prefix": "",
            "activeRel": "",
        }
    )
    assert html is not None
    assert "<details open>" in html
    assert html.count("<details open>") >= 2  # notes + deep ancestors forced open
    assert 'class="doctree-filter-hit"' in html
    assert "Zeta" not in html
    assert "Beta" not in html
    assert "alpha-root.html" in html
    assert "xalpha.html" in html
    assert "Other" not in html


def test_render_empty_returns_null(node_runner) -> None:
    assert (
        node_runner(
            {
                "op": "render",
                "tree": _SAMPLE_TREE,
                "query": "zzzz-nope",
            }
        )
        is None
    )


def test_css_has_filter_and_mark_rules() -> None:
    assert ".doctree-filter" in CSS
    assert ".doctree-filter-hit" in CSS


def test_js_ships_filter_input_wiring() -> None:
    assert 'className = "doctree-filter"' in JS
    assert "No documents match" in JS
    assert "doctree-filter-hit" in JS
