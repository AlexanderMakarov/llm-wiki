"""Search must work when the built site is opened over ``file://`` (#20).

Browsers block ``fetch``/XHR against ``file://`` URLs, so the runtime search
data has to reach the page by a channel that ``file://`` does allow:
``<script src>`` execution. These tests pin the build-side contract (a ``.js``
sidecar next to every search ``.json``) and the client-side contract (the
loader injects script tags rather than calling ``fetch``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from llmwiki.build import build_search_index


def _build(tmp_path: Path, projects: dict[str, list[str]] | None = None) -> Path:
    """Run build_search_index over a tiny synthetic corpus, return site dir."""
    projects = projects or {"demo": ["one", "two"]}
    out = tmp_path / "site"
    out.mkdir()

    sources = []
    for project, slugs in projects.items():
        for slug in slugs:
            src_path = tmp_path / "sessions" / project / f"{slug}.md"
            src_path.parent.mkdir(parents=True, exist_ok=True)
            body = f"# {slug}\n## Section\n### Deep\nsome body text\n"
            src_path.write_text(body, encoding="utf-8")
            sources.append(
                (src_path, {"project": project, "slug": slug, "date": "2026-04-19"}, body)
            )

    groups: dict[str, list] = {}
    for entry in sources:
        groups.setdefault(entry[1]["project"], []).append(entry)

    build_search_index(sources, groups, out)
    return out


# ─── build side: .js sidecars exist next to the .json ──────────────────────


def test_index_js_sidecar_is_written(tmp_path: Path):
    out = _build(tmp_path)
    assert (out / "search-index.json").exists(), "JSON stays for external consumers"
    assert (out / "search-index.js").exists(), "JS sidecar is what file:// loads"


def test_every_chunk_has_a_js_sidecar(tmp_path: Path):
    out = _build(tmp_path, {"alpha": ["a1"], "beta": ["b1"]})
    manifest = json.loads((out / "search-index.json").read_text())["_chunks"]
    assert manifest, "corpus should produce at least one chunk"
    for rel in manifest:
        assert (out / rel).exists(), f"{rel} (json) missing"
        js_rel = rel[:-len(".json")] + ".js"
        assert (out / js_rel).exists(), f"{js_rel} (js sidecar) missing"


def test_index_js_payload_matches_the_json_exactly(tmp_path: Path):
    """The sidecar must carry the same data — not a stale or trimmed copy."""
    out = _build(tmp_path)
    expected = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
    js = (out / "search-index.js").read_text(encoding="utf-8")

    m = re.search(r'window\.llmwikiData\["search-index"\]\s*=\s*(.*);\s*$', js, re.S)
    assert m, f"unexpected sidecar shape: {js[:200]!r}"
    assert json.loads(m.group(1)) == expected


def test_chunk_js_payload_matches_the_json_exactly(tmp_path: Path):
    out = _build(tmp_path)
    rel = json.loads((out / "search-index.json").read_text())["_chunks"][0]
    expected = json.loads((out / rel).read_text(encoding="utf-8"))
    js = (out / (rel[:-len(".json")] + ".js")).read_text(encoding="utf-8")

    m = re.search(r"window\.llmwikiData\[(.*?)\]\s*=\s*(.*);\s*$", js, re.S)
    assert m, f"unexpected sidecar shape: {js[:200]!r}"
    # Keyed by its manifest path so the client needs no key derivation rules.
    assert json.loads(m.group(1)) == rel
    assert json.loads(m.group(2)) == expected


def test_sidecar_initialises_the_namespace_before_assigning(tmp_path: Path):
    """Chunks load in arbitrary order, so each file must be self-sufficient."""
    out = _build(tmp_path)
    for name in ["search-index.js"] + [
        r[:-len(".json")] + ".js"
        for r in json.loads((out / "search-index.json").read_text())["_chunks"]
    ]:
        js = (out / name).read_text(encoding="utf-8")
        assert "window.llmwikiData = window.llmwikiData || {}" in js, name


def test_sidecar_escapes_line_and_paragraph_separators(tmp_path: Path):
    """U+2028/U+2029 are legal in JSON strings and were illegal in JS string
    literals before ES2019 — escape them so old engines don't choke."""
    from llmwiki.build import write_js_sidecar

    payload = json.dumps(["a b", "c d"], ensure_ascii=False)
    js_path = write_js_sidecar(tmp_path / "data.json", "data", payload)
    js = js_path.read_text(encoding="utf-8")

    assert " " not in js and " " not in js
    # Escaped, not dropped — the decoded value is unchanged.
    m = re.search(r"window\.llmwikiData\[.*?\]\s*=\s*(.*);\s*$", js, re.S)
    assert json.loads(m.group(1)) == ["a b", "c d"]


def test_sidecar_path_preserves_dotted_names(tmp_path: Path):
    """A project slug containing dots must not lose part of its name."""
    from llmwiki.build import write_js_sidecar

    js_path = write_js_sidecar(tmp_path / "my.proj.v2.json", "k", "[]")
    assert js_path.name == "my.proj.v2.js"


# ─── client side: the loader must not depend on fetch ──────────────────────


def test_search_loader_injects_script_tags_instead_of_fetching():
    from llmwiki.render.js import JS

    assert "__llmwikiLoadData" in JS, "shared script-injection loader missing"
    assert 'createElement("script")' in JS


def test_no_fetch_of_search_data_remains():
    """Every former search fetch site must be gone — a single surviving one
    silently empties the index over file:// (the original bug)."""
    from llmwiki.render.js import JS

    offenders = [
        line.strip()
        for line in JS.splitlines()
        if "fetch(" in line and ("search-index" in line or "search-chunk" in line)
    ]
    assert not offenders, f"fetch() still used for search data: {offenders}"


def test_loader_derives_js_url_from_the_json_url():
    from llmwiki.render.js import JS

    # Falls back to rewriting the .json URL when no explicit JS url is set,
    # so a site built before this change still resolves a sensible path.
    assert "LLMWIKI_INDEX_JS_URL" in JS
    assert re.search(r'replace\(\s*/\\\.json\$?/', JS) or ".json$" in JS


def test_build_emits_the_js_url_global():
    """The page must tell the loader where the sidecar lives."""
    import inspect

    from llmwiki import build

    src = inspect.getsource(build)
    assert "LLMWIKI_INDEX_JS_URL" in src


def test_build_drops_the_inert_json_script_tag():
    """`<script src="*.json" type="application/json">` neither executes nor
    exposes anything — it read like a file:// fix while doing nothing."""
    import inspect

    from llmwiki import build

    assert 'type="application/json"' not in inspect.getsource(build)


# ─── runtime errors must be visible, not swallowed ─────────────────────────


def test_error_reporter_exists_and_renders_to_the_page():
    from llmwiki.render.js import JS

    assert "__llmwikiReportError" in JS
    assert 'role", "alert"' in JS or "role='alert'" in JS or 'setAttribute("role", "alert")' in JS
    assert "console.error" in JS, "errors should reach the console as well as the DOM"


def test_every_search_failure_path_reports():
    """Each rejection handler on a search load path must call the reporter —
    a bare `.catch(() => [])` is what made #20 invisible for so long."""
    from llmwiki.render.js import JS

    # Handlers that swallow to an empty value without telling anyone.
    silent = re.findall(r"\.catch\(function \([^)]*\) \{ (?:idx = \[\]; )?return \[?\]?;?", JS)
    assert not silent, f"silent catch handlers remain: {silent}"


def test_palette_distinguishes_broken_index_from_empty_corpus():
    from llmwiki.render.js import JS

    assert "idxFailed" in JS and "idxPartial" in JS
    assert "palette-note" in JS


# ─── the search button must open something on every page that shows it ─────


def test_graph_page_ships_the_palette_it_advertises():
    """graph.html renders the nav's search button and loads script.js, but
    carried no dialog for them to open — Cmd+K and the button both no-opped."""
    from llmwiki.graph import HTML_TEMPLATE

    assert "__SITE_PALETTE__" in HTML_TEMPLATE


def test_graph_html_renders_palette_and_index_globals(tmp_path: Path):
    from llmwiki.graph import write_html

    out = tmp_path / "graph.html"
    write_html({"nodes": [{"id": "a", "label": "A", "type": "topic"}], "edges": []}, out)
    html = out.read_text(encoding="utf-8")

    for probe in ['id="palette"', 'id="palette-input"', 'id="palette-results"',
                  'id="open-palette"', "LLMWIKI_INDEX_JS_URL"]:
        assert probe in html, f"graph.html missing {probe}"
    assert "__SITE_PALETTE__" not in html, "placeholder left unsubstituted"


def test_graph_html_does_not_double_load_script_js(tmp_path: Path):
    """Two <script src="script.js"> tags would double-bind every listener."""
    from llmwiki.graph import write_html

    out = tmp_path / "graph.html"
    write_html({"nodes": [{"id": "a", "label": "A", "type": "topic"}], "edges": []}, out)
    assert out.read_text(encoding="utf-8").count('src="script.js"') == 1


def test_palette_markup_is_shared_not_duplicated():
    """One source for the dialog, so the two pages can't drift apart."""
    from llmwiki.build import page_foot, search_palette_markup

    assert search_palette_markup("") in page_foot("")


def test_palette_note_is_styled():
    """The note must be visible, not inherit a result-row layout."""
    from llmwiki.render.css import CSS

    assert "palette-note" in CSS
