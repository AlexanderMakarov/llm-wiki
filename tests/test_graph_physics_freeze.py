"""Regression tests for issue #9 — graph.html shakes on open + dim search.

Two contracts on the viewer template:

1. The barnesHut force simulation must be switched OFF once vis-network
   fires ``stabilizationIterationsDone``, and the viewport fitted to the
   settled layout. Leaving physics on keeps perturbing node positions
   live, which reads as "shaking" every time the page opens.
2. Search matches must light up in a dedicated red (``--g-search-match``)
   instead of keeping their base palette color — blue-ish node colors on
   the blue-ish background are too dim to spot.

Like tests/test_graph_viewer.py, the template is HTML/JS so we verify it
from the outside with string assertions on HTML_TEMPLATE.
"""

from __future__ import annotations

from llmwiki.graph import HTML_TEMPLATE


# ─── 1. Physics freeze after stabilization ────────────────────────────


def test_physics_disabled_after_stabilization():
    assert "stabilizationIterationsDone" in HTML_TEMPLATE, (
        "template must hook vis-network's stabilizationIterationsDone event"
    )
    assert "physics: false" in HTML_TEMPLATE, (
        "the handler must turn the live simulation off"
    )


def test_viewport_fitted_to_settled_layout():
    # The stabilization handler frames the settled graph so the user
    # lands on the final layout, not wherever the camera started.
    assert "network.fit()" in HTML_TEMPLATE


def test_freeze_handler_registered_once():
    # `once`, not `on` — dragging or clustering later must not re-trigger
    # a fit that yanks the camera away from the user.
    assert "network.once('stabilizationIterationsDone'" in HTML_TEMPLATE


def test_edges_use_continuous_smoothing():
    # 'dynamic' smoothing adds live per-frame recomputation via helper
    # nodes; 'continuous' is the cheap static variant.
    assert "'continuous'" in HTML_TEMPLATE
    assert "'dynamic'" not in HTML_TEMPLATE


# ─── 2. Search matches highlighted red ────────────────────────────────


def test_search_match_color_defined_for_both_themes():
    assert HTML_TEMPLATE.count("--g-search-match:") == 2, (
        "--g-search-match must be defined in both the dark and light palettes"
    )


def test_search_filter_paints_matches_with_search_color():
    # applyFilter must color matching nodes with the dedicated search
    # var rather than leaving them at their (dim) base colors.
    assert "cssVar('--g-search-match')" in HTML_TEMPLATE
