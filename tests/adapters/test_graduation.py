"""Tests for graduated adapters — Cursor, Gemini CLI (v0.5 · #37, #38).

Verifies each adapter's contract: SUPPORTED_SCHEMA_VERSIONS,
session_store_path, discover_sessions, derive_project_slug,
and graceful degradation (no crash on bad input).

# @spec: 416-adapter-tests-consolidate (#317)
"""

from __future__ import annotations

from pathlib import Path

from llmwiki.adapters.contrib.cursor_ide import CursorAdapter
from llmwiki.adapters.contrib.gemini_cli import GeminiCliAdapter

# ═══════════════════════════════════════════════════════════════════════
# CURSOR ADAPTER
# ═══════════════════════════════════════════════════════════════════════


class TestCursorAdapterContract:
    def test_has_supported_schema_versions(self):
        """Adapter declares at least one supported schema version."""
        assert hasattr(CursorAdapter, "SUPPORTED_SCHEMA_VERSIONS")
        assert len(CursorAdapter.SUPPORTED_SCHEMA_VERSIONS) >= 1

    def test_derive_project_slug(self):
        """derive_project_slug returns a non-empty string for a workspace DB path."""
        adapter = CursorAdapter()
        slug = adapter.derive_project_slug(Path("/tmp/workspace-abc123/state.vscdb"))
        assert isinstance(slug, str)
        assert len(slug) > 0

    def test_discover_returns_list(self):
        """discover_sessions returns a list even when the store is empty or missing."""
        adapter = CursorAdapter()
        result = adapter.discover_sessions()
        assert isinstance(result, list)

    def test_instantiate_with_no_config(self):
        """Adapter constructs with no config argument."""
        adapter = CursorAdapter()
        assert adapter is not None

    def test_instantiate_with_empty_config(self):
        """Adapter constructs with an empty config dict."""
        adapter = CursorAdapter(config={})
        assert adapter is not None


# ═══════════════════════════════════════════════════════════════════════
# GEMINI CLI ADAPTER
# ═══════════════════════════════════════════════════════════════════════


class TestGeminiCliAdapterContract:
    def test_has_supported_schema_versions(self):
        """Adapter declares at least one supported schema version."""
        assert hasattr(GeminiCliAdapter, "SUPPORTED_SCHEMA_VERSIONS")
        assert len(GeminiCliAdapter.SUPPORTED_SCHEMA_VERSIONS) >= 1

    def test_session_store_path_exists(self):
        adapter = GeminiCliAdapter()
        paths = adapter.session_store_path
        assert paths is not None

    def test_derive_project_slug(self):
        adapter = GeminiCliAdapter()
        slug = adapter.derive_project_slug(Path("/tmp/gemini/session.jsonl"))
        assert isinstance(slug, str)
        assert len(slug) > 0

    def test_discover_returns_list(self):
        """discover_sessions returns a list even when the store is empty or missing."""
        adapter = GeminiCliAdapter()
        result = adapter.discover_sessions()
        assert isinstance(result, list)

    def test_instantiate_with_no_config(self):
        """Adapter constructs with no config argument."""
        adapter = GeminiCliAdapter()
        assert adapter is not None


# ═══════════════════════════════════════════════════════════════════════
# CROSS-ADAPTER
# ═══════════════════════════════════════════════════════════════════════


class TestCrossAdapterGracefulDegradation:
    def test_all_adapters_handle_empty_config(self):
        """Graduated adapters construct with empty config without raising."""
        for cls in [CursorAdapter, GeminiCliAdapter]:
            adapter = cls(config={})
            assert adapter is not None
            sessions = adapter.discover_sessions()
            assert isinstance(sessions, list)
