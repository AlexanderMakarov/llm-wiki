"""Whole-feature acceptance tests for #273: MCP Add as CLI Add Proxy.

# @layer: integration
# @spec: 273-mcp-wiki-add-cli-proxy
# @regression

Per-slice suites (``test_add_doc.py``, ``test_cli.py``, ``test_mcp_wiki_add.py``)
already cover individual mechanics: piped provenance, chunking, CLI flag inversion,
MCP registration and schema.

This file drives the acceptance criteria from the functional spec as a whole,
checking properties that only hold once every slice is wired together:

* MCP Add and CLI add produce identical provenance for the same input mode
* Long ``content`` via MCP → multiple raw chunks, all with ``source: piped``
* URL route records the exact URL as source, never a temp path
* Default invocation (no flags): raw written, site rebuilt, no synth
* ``no_build=True`` with no synthesize still runs ``refresh_synth_pending`` bookkeeping
* ``synthesize=True`` produces wiki/sources pages for MCP and CLI alike
* Tool description documents the proxy model and source-layer guardrail
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import llmwiki.add_doc as add_mod
import llmwiki.add_pipeline as pipe
from llmwiki._frontmatter import parse_frontmatter
from llmwiki.add_doc import ConvertedDoc
from llmwiki.add_pipeline import run_add
from llmwiki.mcp.server import TOOLS, tool_wiki_add

# ── helpers ──────────────────────────────────────────────────────────

def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "raw" / "sessions").mkdir(parents=True, exist_ok=True)
    (vault / "wiki").mkdir()
    return vault


def _result_text(result: dict) -> str:
    return result["content"][0]["text"]


def _result_json(result: dict):
    return json.loads(_result_text(result))


def _noop_build(**kw):
    return 0


# ── AC1 / AC8: URL route records the exact URL, never a temp path ─────────────

def test_wiki_add_url_provenance_is_exact_url(tmp_path: Path, monkeypatch):
    """MCP url route: ``source:`` in frontmatter equals the URL, not a /tmp path.

    Functional-spec §2 AC:
      "Given a path or URL, when raw files are written, then the recorded
       origin is that exact path or URL."
    """
    vault = _vault(tmp_path)
    monkeypatch.setattr(pipe, "build_site", _noop_build)

    target_url = "https://example.com/docs/guide"

    # Stub convert_url to avoid real network call; preserve source_label=URL.
    def _fake_convert_url(url, *args, **kwargs):
        return ConvertedDoc(
            markdown="# Guide\n\nContent of the guide. " * 10,
            title="Guide",
            source_label=url,
            path_name=None,
            url=url,
        )

    monkeypatch.setattr(add_mod, "convert_url", _fake_convert_url)

    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_add({"url": target_url, "no_build": True})

    assert result["isError"] is False, _result_text(result)
    rel = _result_json(result)["written"][0]
    text = (vault / rel).read_text(encoding="utf-8")
    meta, _ = parse_frontmatter(text)
    assert meta["source"] == target_url, (
        f"Expected source='{target_url}', got source='{meta['source']}'"
    )
    assert "/tmp/" not in meta["source"]
    assert "piped" not in meta["source"]


# ── AC5+AC6: Long MCP content → multiple chunks, all with piped provenance ────

def test_wiki_add_long_content_produces_multiple_chunks_all_piped(tmp_path: Path, monkeypatch):
    """Long MCP content splits into multiple raw files via CLI add logic only.

    Functional-spec §2 AC:
      "Given a source longer than the usual chunk size (~7,000 chars), when Add
       runs (CLI or MCP proxy), then multiple raw pieces come from CLI add logic only."
      "MCP does not implement a separate splitter."
      Each piece must carry ``source: piped``.
    """
    vault = _vault(tmp_path)
    monkeypatch.setattr(pipe, "build_site", _noop_build)

    # Build a body that will definitely exceed 7,000 chars across multiple sections.
    sections = "".join(
        f"## Section {i}\n\n" + ("word " * 500) + "\n\n"
        for i in range(1, 6)
    )
    long_body = "# Long MCP Document\n\n" + sections  # ~15,000 chars

    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_add({
            "content": long_body,
            "no_build": True,
        })

    assert result["isError"] is False, _result_text(result)
    payload = _result_json(result)
    written = payload["written"]

    # Must produce more than one chunk.
    assert len(written) > 1, (
        f"Expected multiple chunks for ~15k-char document, got {len(written)}: {written}"
    )

    # Every chunk must carry ``source: piped``.
    for rel in written:
        text = (vault / rel).read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(text)
        assert meta.get("source") == "piped", (
            f"Chunk {rel!r} has source={meta.get('source')!r}, expected 'piped'"
        )
        assert "/tmp/" not in text


# ── AC1 parity: MCP content ↔ CLI add – same default behavior ─────────────────

def test_mcp_and_cli_add_default_behavior_matches(tmp_path: Path, monkeypatch):
    """MCP Add with no extra flags and CLI add with no extra flags produce
    identical raw file counts and piped provenance.

    Functional-spec §2 AC:
      "Given the same path, URL, or text and the same synthesize/build choices,
       when I add via MCP or CLI, then raw files, synthesis, and site build
       outcomes match."
    """
    monkeypatch.setattr(pipe, "build_site", _noop_build)
    monkeypatch.setattr(pipe, "synthesize_new_sessions", lambda **kw: {
        "synthesized": 0, "skipped": 0, "errors": [],
    })

    body = "# Parity Check\n\n" + "body paragraph. " * 20 + "\n"

    # MCP path
    mcp_vault = _vault(tmp_path / "mcp_vault")
    with patch("llmwiki.mcp.server.REPO_ROOT", mcp_vault):
        mcp_result = tool_wiki_add({"content": body})
    assert mcp_result["isError"] is False, _result_text(mcp_result)
    mcp_payload = _result_json(mcp_result)
    assert len(mcp_payload["written"]) == 1

    # CLI / run_add path
    cli_vault = _vault(tmp_path / "cli_vault")
    cli_result = run_add(
        ["-"],
        cli_vault / "raw" / "docs",
        vault_root=cli_vault,
        build=True,
        synthesize=False,
        stdin_text=body,
    )
    assert cli_result["exit_code"] == 0
    assert len(cli_result["written"]) == 1

    # Both must be piped
    mcp_text = (mcp_vault / mcp_payload["written"][0]).read_text(encoding="utf-8")
    cli_text = cli_result["written"][0].read_text(encoding="utf-8")
    for label, text in [("MCP", mcp_text), ("CLI", cli_text)]:
        assert "source: \"piped\"" in text or "source: piped" in text, (
            f"{label}: expected piped provenance, got text snippet: {text[:200]}"
        )
        assert "/tmp/" not in text


# ── AC2: Default = raw + site rebuild, NO synthesis ────────────────────────────

def test_default_mcp_add_writes_raw_and_builds_site_no_synth(tmp_path: Path, monkeypatch):
    """Explicit regression for the product default flip: synth is OFF, build is ON.

    Functional-spec §2 AC:
      "Given MCP Add or CLI add with no extra flags, when it completes
       successfully, then raw document file(s) exist, the site has been
       rebuilt to include them, and no new synthesized wiki source pages
       were produced by that add."
    """
    vault = _vault(tmp_path)
    build_calls: list[dict] = []
    synth_calls: list[dict] = []

    def _track_build(**kw):
        build_calls.append(kw)
        return 0

    def _track_synth(**kw):
        synth_calls.append(kw)
        return {"synthesized": 0, "skipped": 0, "errors": []}

    monkeypatch.setattr(pipe, "build_site", _track_build)
    monkeypatch.setattr(pipe, "synthesize_new_sessions", _track_synth)

    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_add({"content": "# Default Test\n\nsome body\n"})

    assert result["isError"] is False, _result_text(result)

    # Site rebuild must happen once.
    assert len(build_calls) == 1, f"Expected 1 build call, got {len(build_calls)}"

    # Synthesis must NOT be called.
    assert len(synth_calls) == 0, (
        f"Expected 0 synth calls (default is no-synth), got {len(synth_calls)}"
    )

    # No wiki/sources pages created.
    sources_dir = vault / "wiki" / "sources"
    if sources_dir.exists():
        pages = list(sources_dir.rglob("*.md"))
        assert pages == [], f"Expected no wiki/sources pages, found: {pages}"


# ── AC3: synthesize opt-in: MCP and CLI both produce wiki/sources ───────────────

def test_synthesize_opt_in_mcp_matches_cli_opt_in(tmp_path: Path, monkeypatch):
    """``synthesize=True`` (MCP) / ``--synthesize`` (CLI): both run synthesis.

    Functional-spec §2 AC:
      "Given add with synthesis explicitly enabled, when it completes
       successfully, then synthesized wiki pages for the new raw docs are produced."
    """
    # Counter tracking synth invocations for MCP and CLI paths.
    mcp_synth = {"n": 0}
    cli_synth = {"n": 0}

    class _FakeBackend:
        name = "fake"

        def is_available(self):
            return True

    def _make_fake_synth(counter):
        def _synth(**kwargs):
            counter["n"] += 1
            return {"total_scanned": 1, "new_files": 1, "synthesized": 1, "skipped": 0, "errors": [], "backend": "fake"}
        return _synth

    def _fake_expected_page(raw_path, sources_dir):
        """Create a placeholder wiki page so run_add doesn't roll back."""
        p = Path(sources_dir) / "docs" / "synth-test.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# Synth Test\n", encoding="utf-8")
        return p

    monkeypatch.setattr(pipe, "_load_sessions_config", lambda: {"synthesis": {"backend": "fake"}})
    monkeypatch.setattr(pipe, "resolve_backend", lambda _cfg: _FakeBackend())
    monkeypatch.setattr(pipe, "expected_source_page", _fake_expected_page)
    monkeypatch.setattr(pipe, "build_site", _noop_build)

    # MCP opt-in
    mcp_vault = _vault(tmp_path / "mcp_v")
    monkeypatch.setattr(pipe, "synthesize_new_sessions", _make_fake_synth(mcp_synth))
    with patch("llmwiki.mcp.server.REPO_ROOT", mcp_vault):
        mcp_r = tool_wiki_add({"content": "# Synth Test\n\nbody\n", "synthesize": True, "no_build": True})
    assert mcp_r["isError"] is False, _result_text(mcp_r)
    assert mcp_synth["n"] == 1, "MCP synthesize=True must invoke synthesize_new_sessions"

    # CLI opt-in
    cli_vault = _vault(tmp_path / "cli_v")
    monkeypatch.setattr(pipe, "synthesize_new_sessions", _make_fake_synth(cli_synth))
    cli_result = run_add(
        ["-"],
        cli_vault / "raw" / "docs",
        vault_root=cli_vault,
        build=False,
        synthesize=True,
        stdin_text="# Synth Test\n\nbody\n",
    )
    assert cli_result["exit_code"] == 0
    assert cli_synth["n"] == 1, "CLI synthesize=True must invoke synthesize_new_sessions"


# ── AC4: no_build + no synth → refresh_synth_pending still runs ────────────────

def test_no_build_no_synth_still_runs_refresh_synth_pending(tmp_path: Path, monkeypatch):
    """``no_build=True`` with default (no synth) still calls ``refresh_synth_pending``
    to keep bookkeeping consistent.

    Functional-spec §2 AC:
      "Given add with site rebuild skipped, when it completes, then raw docs
       are written and the site is not rebuilt by that invocation; when synthesis
       was also off, bookkeeping for later synthesis matches the existing
       raw-only pending behavior."
    """
    vault = _vault(tmp_path)
    build_calls: list[dict] = []
    pending_calls: list[dict] = []

    monkeypatch.setattr(pipe, "build_site", lambda **kw: (build_calls.append(kw) or 0))
    monkeypatch.setattr(
        pipe,
        "refresh_synth_pending",
        lambda **kw: pending_calls.append(kw),
    )

    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_add({
            "content": "# Pending Bookkeeping\n\nbody\n",
            "no_build": True,
        })

    assert result["isError"] is False, _result_text(result)

    # Site NOT rebuilt.
    assert build_calls == [], f"Expected no build calls with no_build=True, got {build_calls}"

    # Pending refresh MUST still run.
    assert len(pending_calls) >= 1, (
        "refresh_synth_pending must be called even when build is skipped "
        "(AC4: bookkeeping for later synthesis)"
    )


# ── Negative: content route must never leave a /tmp artefact as source ─────────

def test_content_route_never_records_tmp_path_in_any_chunk(tmp_path: Path, monkeypatch):
    """No chunk from MCP content add should record a /tmp path in source frontmatter.

    Functional-spec §2 AC:
      "Given text on stdin (or equivalent text input) to CLI add, when raw
       files are written, then they succeed and the recorded origin identifies
       piped/pasted input (e.g. 'piped'), not a /tmp/… path."
    """
    vault = _vault(tmp_path)
    monkeypatch.setattr(pipe, "build_site", _noop_build)

    body = "# Temp Path Guard\n\n" + "content sentence. " * 10

    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_add({"content": body, "no_build": True})

    assert result["isError"] is False, _result_text(result)
    for rel in _result_json(result)["written"]:
        text = (vault / rel).read_text(encoding="utf-8")
        assert "/tmp/" not in text, f"Found /tmp/ in {rel}: {text[:300]}"
        assert "wiki-add-content-" not in text, f"Found temp artefact in {rel}"


# ── Negative: CLI add - without stdin_text must fail gracefully ─────────────────

def test_cli_add_dash_with_empty_stdin_produces_error(tmp_path: Path, monkeypatch):
    """CLI ``add -`` with empty stdin should produce an error (empty document).

    Negative case for the stdin sentinel path — empty text must not silently
    write a blank raw doc.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    # Provide an empty stdin so pytest's capture doesn't intercept it.
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    result = run_add(
        ["-"],
        docs,
        vault_root=tmp_path,
        build=False,
        synthesize=False,
        stdin_text=None,  # Must read from sys.stdin
    )
    # Empty stdin → empty document → should error.
    assert result.get("exit_code") != 0 or result.get("errors"), (
        "Expected an error when add - receives empty stdin"
    )


# ── AC10: Tool description documents proxy model and guardrail ────────────────

def test_tool_description_documents_proxy_model_and_guardrail():
    """MCP tool description must document the proxy model, defaults, and guardrail.

    Functional-spec §2 AC:
      "Given the MCP Add description, when an agent reads it, then it states:
       same as CLI add by default (raw add + site rebuild, no synthesis unless
       requested); optional skip of rebuild / opt-in synthesis; long docs may
       become multiple raw pieces via add; use exact path/URL/text — do not
       reconstruct from wiki pages unless the user asked."
    """
    tool = next(t for t in TOOLS if t["name"] == "wiki_add")
    desc = tool["description"].lower()

    # Default proxy model: raw + build, no synth
    assert "proxy" in desc or "same as cli" in desc, "Description must describe proxy model"
    assert "synth" in desc, "Description must mention synthesis opt-in behavior"
    assert "no_build" in desc or "rebuild" in desc or "build" in desc, (
        "Description must mention site rebuild control"
    )

    # Source guardrail
    assert "do not reconstruct" in desc or "unless the user asked" in desc, (
        "Description must include source-layer guardrail against reconstructing input"
    )

    # Piped provenance
    assert "piped" in desc, "Description must mention piped provenance for content"
