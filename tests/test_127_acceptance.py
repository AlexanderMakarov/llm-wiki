"""Whole-feature acceptance tests for #127: external graph viewer assets.

# @layer: integration
# @spec: 007-graph-viewer-external-assets
# @regression

This file verifies the feature's acceptance criteria end-to-end against
functional-spec.md.  Implementation is already on this branch; the tests are
written so that they would have failed on main (no companion files emitted,
CDN dependency, no changelog entry).

AC coverage matrix (FR<n>-AC<n>, in functional-spec.md bullet order):

    FR2-AC2  → test_emitted_graph_html_has_no_external_cdn_urls
               test_emitted_graph_viewer_js_has_no_external_cdn_urls
               test_vendored_vis_network_is_a_real_js_bundle
    FR4-AC1  → test_standalone_build_emits_graph_viewer_js_companion
               test_standalone_build_emits_vis_network_companion
    FR4-AC2  → test_full_site_build_emits_graph_viewer_js_companion
               test_full_site_build_emits_vis_network_companion
    FR5-AC1  → test_graph_viewer_js_size_budget_standalone
    FR6-AC1  → test_changelog_unreleased_has_external_assets_entry
    extra    → test_write_html_emits_graph_viewer_js_companion
               test_offline_notice_names_companion_files
               test_emitted_graph_html_references_both_companions_as_relative_src
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import llmwiki.graph as graph_mod
from llmwiki.graph import (
    VIS_NETWORK_VENDOR,
    build_and_report,
    build_graph,
    copy_to_site,
    write_html,
)
from llmwiki.render.graph_viewer import GRAPH_VIEWER_JS

# ─── Shared fixture ────────────────────────────────────────────────────


def _seed_wiki(tmp_path: Path) -> Path:
    """Minimal wiki with one entity so build paths produce non-empty graphs."""
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "Alpha.md").write_text(
        '---\ntitle: "Alpha"\ntype: entity\n---\n\nAlpha links to [[Beta]].\n',
        encoding="utf-8",
    )
    (wiki / "entities" / "Beta.md").write_text(
        '---\ntitle: "Beta"\ntype: entity\n---\n\nBeta body.\n',
        encoding="utf-8",
    )
    return wiki


@pytest.fixture()
def wiki(tmp_path: Path):
    return _seed_wiki(tmp_path)


@pytest.fixture()
def seeded_graph(tmp_path: Path, monkeypatch):
    wiki = _seed_wiki(tmp_path)
    monkeypatch.setattr(graph_mod, "WIKI_DIR", wiki)
    monkeypatch.setattr(graph_mod, "REPO_ROOT", tmp_path)
    return build_graph()


# ─── FR2-AC2 — no CDN fetch needed at view time ────────────────────────


def test_emitted_graph_html_has_no_external_cdn_urls(tmp_path: Path, seeded_graph):
    # @regression
    """graph.html must not load any script from an external CDN.

    Before #127 the template fetched vis-network from unpkg.  A freshly
    emitted graph.html on this branch must contain no http/https script
    sources pointing outside the site.
    """
    out = tmp_path / "graph.html"
    write_html(seeded_graph, out)
    html = out.read_text(encoding="utf-8")
    # Any <script src="http…"> or <script src="https…"> would be a CDN fetch.
    cdn_pattern = re.compile(r'<script\b[^>]*\bsrc\s*=\s*["\']https?://', re.IGNORECASE)
    assert not cdn_pattern.search(html), (
        "graph.html contains a CDN script reference — offline / file:// use will break"
    )
    # Specifically ensure unpkg (the old source) is gone.
    assert "unpkg.com" not in html, (
        "graph.html still references unpkg.com — it must use the local companion instead"
    )


def test_emitted_graph_viewer_js_has_no_external_cdn_urls(tmp_path: Path, seeded_graph):
    # @regression
    """graph-viewer.js must not fetch any external URL at runtime."""
    out = tmp_path / "graph.html"
    write_html(seeded_graph, out)
    viewer_js = (tmp_path / "graph-viewer.js").read_text(encoding="utf-8")
    assert "unpkg.com" not in viewer_js
    assert "cdn.jsdelivr.net" not in viewer_js
    # No bare http/https load calls in the viewer JS itself.
    assert "https://unpkg" not in viewer_js


def test_vendored_vis_network_is_a_real_js_bundle():
    # @regression
    """The vendored vis-network.min.js must be a non-trivial JavaScript bundle.

    Before #127 no vendor file existed.  After #127 it must be ≥ 100 kB
    (the real 9.1.9 UMD build is ~550 kB), ensuring the committed file is
    the actual library and not an empty placeholder.
    """
    assert VIS_NETWORK_VENDOR.is_file(), (
        "llmwiki/vendor/vis-network.min.js not found — vendored file missing"
    )
    size = VIS_NETWORK_VENDOR.stat().st_size
    assert size >= 100_000, (
        f"vendor/vis-network.min.js is only {size} bytes — this is not the real library"
    )
    content = VIS_NETWORK_VENDOR.read_text(encoding="utf-8", errors="replace")
    # A valid UMD bundle for vis-network defines a `Network` constructor.
    assert "Network" in content, "vendor file does not appear to be a vis-network bundle"


# ─── FR4-AC1 — standalone `llmwiki graph` emits companion files ────────


def test_standalone_build_emits_graph_viewer_js_companion(tmp_path: Path, monkeypatch):
    # @regression
    """build_and_report() (the standalone `llmwiki graph` path) must emit
    graph-viewer.js beside graph.html.

    Before #127 the viewer was an inline <script> block; no companion was
    ever written by the standalone command.
    """
    wiki = _seed_wiki(tmp_path)
    graph_dir = tmp_path / "graph"
    monkeypatch.setattr(graph_mod, "WIKI_DIR", wiki)
    monkeypatch.setattr(graph_mod, "REPO_ROOT", tmp_path)
    rc = build_and_report(graph_dir=graph_dir)
    assert rc == 0
    companion = graph_dir / "graph-viewer.js"
    assert companion.is_file(), (
        "standalone llmwiki graph did not emit graph-viewer.js — offline use will break"
    )
    assert companion.stat().st_size > 0


def test_standalone_build_emits_vis_network_companion(tmp_path: Path, monkeypatch):
    # @regression
    """build_and_report() must emit vis-network.min.js beside graph.html."""
    wiki = _seed_wiki(tmp_path)
    graph_dir = tmp_path / "graph"
    monkeypatch.setattr(graph_mod, "WIKI_DIR", wiki)
    monkeypatch.setattr(graph_mod, "REPO_ROOT", tmp_path)
    rc = build_and_report(graph_dir=graph_dir)
    assert rc == 0
    vendor = graph_dir / "vis-network.min.js"
    assert vendor.is_file(), (
        "standalone llmwiki graph did not emit vis-network.min.js — offline use will break"
    )
    assert vendor.stat().st_size > 0


# ─── FR4-AC2 — full site build emits companion files ──────────────────


def test_full_site_build_emits_graph_viewer_js_companion(tmp_path: Path, monkeypatch):
    # @regression
    """copy_to_site() (called by `llmwiki build`) must emit graph-viewer.js
    beside site/graph.html.

    The existing test_copy_to_site_writes_graph_html only checked the HTML
    and vis-network.min.js; graph-viewer.js was not verified.
    """
    wiki = _seed_wiki(tmp_path)
    monkeypatch.setattr(graph_mod, "WIKI_DIR", wiki)
    monkeypatch.setattr(graph_mod, "REPO_ROOT", tmp_path)
    site = tmp_path / "site"
    site.mkdir()
    out = copy_to_site(site)
    assert out is not None
    companion = site / "graph-viewer.js"
    assert companion.is_file(), (
        "full site build did not emit graph-viewer.js beside site/graph.html"
    )
    assert companion.stat().st_size > 0


def test_full_site_build_emits_vis_network_companion(tmp_path: Path, monkeypatch):
    # @regression
    """copy_to_site() must emit vis-network.min.js beside site/graph.html."""
    wiki = _seed_wiki(tmp_path)
    monkeypatch.setattr(graph_mod, "WIKI_DIR", wiki)
    monkeypatch.setattr(graph_mod, "REPO_ROOT", tmp_path)
    site = tmp_path / "site"
    site.mkdir()
    out = copy_to_site(site)
    assert out is not None
    vendor = site / "vis-network.min.js"
    assert vendor.is_file(), (
        "full site build did not emit vis-network.min.js beside site/graph.html"
    )
    assert vendor.stat().st_size > 0


# ─── FR5-AC1 — size guardrail on extracted viewer script ──────────────


def test_graph_viewer_js_size_budget_standalone():
    # @regression
    """The extracted graph-viewer.js must stay within 32 kB.

    FR5: contributors are stopped from quietly ballooning the viewer.
    This test would have been vacuous before #127 because GRAPH_VIEWER_JS
    did not exist as a separate asset — everything was inline and the
    budget was checked against a larger HTML template.
    """
    size = len(GRAPH_VIEWER_JS.encode("utf-8"))
    assert size < 32_000, (
        f"graph-viewer.js is {size} bytes (UTF-8) — trim or split the viewer "
        "instead of raising this ceiling without discussion (#127)"
    )


# ─── FR6-AC1 — changelog entry ────────────────────────────────────────


def test_changelog_unreleased_has_external_assets_entry():
    # @regression
    """CHANGELOG.md's [Unreleased] section must record that the graph now
    loads from companion assets and works offline.

    FR6: release notes document the user-visible effect.
    """
    changelog = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
    assert changelog.is_file(), "CHANGELOG.md not found"
    text = changelog.read_text(encoding="utf-8")
    # Find the [Unreleased] block (everything up to the next versioned heading).
    unreleased_match = re.search(r"## \[Unreleased\](.*?)(?=\n## \[)", text, re.DOTALL)
    assert unreleased_match, "[Unreleased] section not found in CHANGELOG.md"
    unreleased = unreleased_match.group(1)
    assert "#127" in unreleased, (
        "No #127 entry in [Unreleased] — FR6 requires a changelog entry"
    )
    assert "offline" in unreleased.lower(), (
        "CHANGELOG [Unreleased] entry for #127 must mention offline use"
    )
    assert "companion" in unreleased.lower() or "vis-network" in unreleased.lower(), (
        "CHANGELOG [Unreleased] entry for #127 must describe the companion assets"
    )


# ─── Additional structural guarantees ─────────────────────────────────


def test_write_html_emits_graph_viewer_js_companion(tmp_path: Path, seeded_graph):
    # @regression
    """write_html() must emit graph-viewer.js alongside graph.html.

    Ensures the core writer (called by both build paths) emits the companion.
    """
    out = tmp_path / "graph.html"
    write_html(seeded_graph, out)
    companion = tmp_path / "graph-viewer.js"
    assert companion.is_file(), "write_html() did not emit graph-viewer.js"
    assert companion.stat().st_size > 0


def test_offline_notice_names_companion_files(tmp_path: Path, seeded_graph):
    # @regression
    """The offline notice in the emitted HTML must name the companion files
    so a reader who removes them knows what is missing.
    """
    out = tmp_path / "graph.html"
    write_html(seeded_graph, out)
    html = out.read_text(encoding="utf-8")
    notice_pattern = re.compile(
        r'id="offline-notice"[^>]*>.*?</div>', re.DOTALL
    )
    match = notice_pattern.search(html)
    assert match, 'No #offline-notice element found in emitted graph.html'
    notice_text = match.group(0)
    assert "graph-viewer.js" in notice_text, (
        "offline-notice must name graph-viewer.js so users know what is missing"
    )
    assert "vis-network.min.js" in notice_text, (
        "offline-notice must name vis-network.min.js so users know what is missing"
    )


def test_emitted_graph_html_references_both_companions_as_relative_src(
    tmp_path: Path, seeded_graph
):
    # @regression
    """The emitted graph.html must load both companions via relative <script src>.

    This confirms the page works from disk (file://) and from any static host
    root without path-prefix configuration: both script tags use bare filenames.
    """
    out = tmp_path / "graph.html"
    write_html(seeded_graph, out)
    html = out.read_text(encoding="utf-8")
    assert 'src="vis-network.min.js"' in html, (
        'graph.html must have <script src="vis-network.min.js"> (relative, no prefix)'
    )
    assert 'src="graph-viewer.js"' in html, (
        'graph.html must have <script src="graph-viewer.js"> (relative, no prefix)'
    )


def test_emitted_graph_html_has_html_side_offline_detection(tmp_path: Path, seeded_graph):
    # @regression
    """Missing graph-viewer.js must surface #offline-notice without relying on that file."""
    out = tmp_path / "graph.html"
    write_html(seeded_graph, out)
    html = out.read_text(encoding="utf-8")
    assert "__llmwikiShowGraphOfflineNotice" in html
    assert 'src="graph-viewer.js" onerror="__llmwikiShowGraphOfflineNotice()"' in html
    assert "if (!window.__llmwikiGraphViewerLoaded)" in html
