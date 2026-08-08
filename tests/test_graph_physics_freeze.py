"""Regression tests for issue #9 — graph.html shakes on open + dim search.

Two contracts on the viewer:

1. The barnesHut force simulation must be switched OFF once vis-network
   fires ``stabilizationIterationsDone``, and the viewport fitted to the
   settled layout. Leaving physics on keeps perturbing node positions
   live, which reads as "shaking" every time the page opens.
2. Search matches must light up in a dedicated red (``--g-search-match``)
   instead of keeping their base palette color — blue-ish node colors on
   the blue-ish background are too dim to spot.

Like tests/test_graph_viewer.py, we verify HTML structure in
``HTML_TEMPLATE`` and viewer logic in ``GRAPH_VIEWER_JS``.
"""

from __future__ import annotations

from llmwiki.graph import HTML_TEMPLATE
from llmwiki.render.graph_viewer import GRAPH_VIEWER_JS

# ─── 1. Physics freeze after stabilization ────────────────────────────


def test_physics_disabled_after_stabilization():
    assert "stabilizationIterationsDone" in GRAPH_VIEWER_JS, (
        "viewer must hook vis-network's stabilizationIterationsDone event"
    )
    assert "physics: false" in GRAPH_VIEWER_JS, (
        "the handler must turn the live simulation off"
    )


def test_viewport_fitted_to_settled_layout():
    # The stabilization handler frames the settled graph so the user
    # lands on the final layout, not wherever the camera started.
    assert "network.fit()" in GRAPH_VIEWER_JS


def test_freeze_handler_registered_once():
    # `once`, not `on` — dragging or clustering later must not re-trigger
    # a fit that yanks the camera away from the user.
    assert "network.once('stabilizationIterationsDone'" in GRAPH_VIEWER_JS


def test_edges_use_static_curved_smoothing():
    # #21: 'continuous' rendered edges as near-straight lines. 'cubicBezier'
    # is a STATIC curve type whose curvature survives the physics freeze
    # (unlike 'dynamic', which needs live physics and conflicts with the #9
    # freeze).
    assert "cubicBezier" in GRAPH_VIEWER_JS
    assert "'dynamic'" not in GRAPH_VIEWER_JS


def test_forceatlas2_solver_used():
    # #21: forceAtlas2Based spreads hub-heavy graphs far more evenly than
    # barnesHut, which let the dominant hub collapse everything inward.
    assert "forceAtlas2Based" in GRAPH_VIEWER_JS


def test_layout_density_selector_present():
    # #21: a user-switchable layout-density control lives next to the
    # cluster toggle — 'sparse' (default) and 'tight'.
    assert 'id="layout-select"' in HTML_TEMPLATE
    assert 'value="sparse"' in HTML_TEMPLATE
    assert 'value="tight"' in HTML_TEMPLATE


def test_layout_switch_refreezes():
    # Switching layout must re-run the simulation and re-freeze — otherwise
    # the new layout would either never settle or keep shaking (#9).
    assert "applyLayout" in GRAPH_VIEWER_JS


# ─── 2. Search matches highlighted red ────────────────────────────────


def test_search_match_color_defined_for_both_themes():
    assert HTML_TEMPLATE.count("--g-search-match:") == 2, (
        "--g-search-match must be defined in both the dark and light palettes"
    )


def test_search_filter_paints_matches_with_search_color():
    # applyFilter must color matching nodes with the dedicated search
    # var rather than leaving them at their (dim) base colors.
    assert "cssVar('--g-search-match')" in GRAPH_VIEWER_JS
