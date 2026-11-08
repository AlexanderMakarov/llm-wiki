"""Gemini CLI adapter.

Reads conversation history from Google's Gemini CLI.

Status: v0.3 initial implementation. Gemini CLI stores sessions under
~/.gemini/ (exact layout TBC against a real install). The adapter detects
the directory and discovers .jsonl / .json files inside.

Registers as "available" if any of the known Gemini CLI paths exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter


@register("gemini_cli")
class GeminiCliAdapter(BaseAdapter):
    """Gemini CLI — reads ~/.gemini/ session history"""

    SUPPORTED_SCHEMA_VERSIONS = ["v1"]

    @classmethod
    def default_roots(cls) -> list[Path]:
        return [
            # macOS / Linux / Windows (dot-dir works everywhere)
            Path.home() / ".gemini",
            # Linux (XDG)
            Path.home() / ".config" / "gemini",
            Path.home() / ".local" / "share" / "gemini",
            # Windows (%APPDATA%)
            Path.home() / "AppData" / "Roaming" / "gemini",
        ]

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        ad_cfg = (self.config or {}).get("adapters", {}).get("gemini_cli", {})
        paths = ad_cfg.get("roots") or []
        self._configured_roots: list[Path] | None = (
            [Path(p).expanduser() for p in paths] if paths else None
        )
        self._default_roots: list[Path] | None = None

    @property
    def roots(self) -> list[Path]:
        return self.session_store_path

    @property
    def session_store_path(self):  # type: ignore[override]
        if self._configured_roots is not None:
            return self._configured_roots
        if self._default_roots is None:
            self._default_roots = list(self.default_roots())
        return self._default_roots

    # #496: is_available() inherited from BaseAdapter — temp
    # instance reads self.session_store_path through the @property.

    def discover_sessions(self) -> list[Path]:
        out: list[Path] = []
        stores = self.session_store_path
        if isinstance(stores, Path):
            stores = [stores]
        for root in stores:
            root = Path(root).expanduser()
            if not root.exists():
                continue
            # Look for both .jsonl and .json (Gemini CLI format TBC)
            out.extend(sorted(root.rglob("*.jsonl")))
            out.extend(sorted(root.rglob("chat-*.json")))
            out.extend(sorted(root.rglob("session-*.json")))
        return out

    def derive_project_slug(self, path: Path) -> str:
        # Gemini CLI doesn't have an obvious project encoding yet; use the
        # parent directory name
        stores = self.session_store_path
        if isinstance(stores, Path):
            stores = [stores]
        for root in stores:
            root = Path(root).expanduser()
            try:
                rel = path.relative_to(root)
                return f"gemini-{rel.parts[0].lower()}" if rel.parts else "gemini-root"
            except ValueError:
                continue
        return f"gemini-{path.parent.name.lower()}"

    def is_headless_session(self, records: list[dict[str, Any]]) -> bool:
        """Always False — Gemini CLI store layout / markers still TBC (#180).

        Scaffold adapter: no in-repo fixtures and no local ``~/.gemini``
        sessions to verify automation launches against.
        """
        return False
